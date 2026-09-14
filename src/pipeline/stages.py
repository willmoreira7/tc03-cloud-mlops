"""The retraining pipeline, one function per stage.

    ingest_data -> preprocess_data -> train_model -> evaluate_model -> publish_model

``scripts/train_serving_model.py`` and the Airflow DAG both call these
functions in this order. Neither carries pipeline logic of its own: if they
did, the model retrained on a schedule would drift away from the one built by
hand, and nobody would notice until the two disagreed in production.

Every stage returns a small JSON-serialisable dict. That is what Airflow
passes between tasks through XCom, so no stage may return a model or a
dataframe -- large objects travel through the filesystem instead.

Training writes to ``models/_staging/<run_id>/``, never to the path the API
loads from. Only ``publish_model`` moves an artefact there, and it only runs
after ``evaluate_model`` has accepted it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import (
    DATA_PROCESSED,
    DATA_RAW,
    MODELS_DIR,
    STAGING_DIR,
    load_config,
    set_seed,
)
from src.data.loader import dataset_hash, load_raw, raw_files_present
from src.data.preprocessing import (
    class_distribution,
    drop_degenerate,
    make_splits,
    map_urgency,
)
from src.evaluation.promotion import constraint_violations
from src.models.experiment import run_candidate

METRICS_FILENAME = "metrics.json"
MODEL_FILENAME = "model.pkl"
# Everything a published model directory carries. search_log.csv is kept for
# auditing which hyperparameters were tried.
PUBLISHED_FILES = (MODEL_FILENAME, METRICS_FILENAME, "search_log.csv")

_UNSAFE_RUN_ID = re.compile(r"[^A-Za-z0-9_.-]")


class QualityGateError(RuntimeError):
    """Raised when a retrained model fails the promotion constraints."""


def new_run_id() -> str:
    """Builds a run identifier for executions outside Airflow.

    Returns:
        UTC timestamp such as ``20260914T153000Z``.
    """
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def staging_dir(run_id: str) -> Path:
    """Returns the staging directory for one run.

    Airflow run ids carry ``:`` and ``+`` (``manual__2026-09-14T15:30:00+00:00``),
    which are not safe in every filesystem, so they are normalised here.

    Args:
        run_id: Pipeline or Airflow run identifier.

    Returns:
        Directory where that run's candidate is written.
    """
    return STAGING_DIR / _UNSAFE_RUN_ID.sub("_", run_id)


def ingest_data() -> dict[str, Any]:
    """Checks the raw corpus is present and fingerprints it.

    The hashes end up in the published metrics, which is what later answers
    "which data was the model in production trained on?".

    Returns:
        Present and missing raw files, and the SHA256 of each present one.

    Raises:
        RawDataNotFoundError: If no configured raw file exists.
    """
    present, missing = raw_files_present()
    if not present:
        # load_raw raises with the download instructions; reuse that message.
        load_raw()

    return {
        "arquivos": present,
        "ausentes": missing,
        "sha256": {name: dataset_hash(DATA_RAW / name) for name in present},
    }


def preprocess_data() -> dict[str, Any]:
    """Maps urgency, drops degenerate documents and writes the splits.

    Returns:
        Document counts before and after cleaning, per split and per class.
    """
    # Only the directory this stage writes to. ensure_dirs() would also create
    # notebooks/outputs, which does not exist where the pipeline runs (Airflow).
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    cleaned = drop_degenerate(map_urgency(raw))

    splits = make_splits(cleaned)
    for name, frame in splits.items():
        frame.to_parquet(DATA_PROCESSED / f"{name}.parquet", index=False)

    return {
        "documentos_brutos": len(raw),
        "documentos_limpos": len(cleaned),
        "splits": {name: len(frame) for name, frame in splits.items()},
        "distribuicao": {
            str(label): int(n) for label, n in class_distribution(cleaned)["n"].items()
        },
    }


def train_model(run_id: str) -> dict[str, Any]:
    """Trains the served model into the run's staging directory.

    Which model is trained comes from ``serving.model`` in the config, the same
    key the API reads -- retraining can never produce an artefact the API would
    not load.

    Args:
        run_id: Pipeline or Airflow run identifier.

    Returns:
        Candidate name, staging directory, chosen parameters and test metrics.
    """
    seed = set_seed()
    candidate = load_config()["serving"]["model"]
    output_dir = staging_dir(run_id) / candidate

    result = run_candidate(candidate, output_dir=output_dir)
    return {
        "candidato": candidate,
        "run_id": run_id,
        "seed": seed,
        "diretorio": str(output_dir),
        "best_params": result["best_params"],
        "test_metrics": result["test_metrics"],
        "latency": result["latency"],
    }


def evaluate_model(model_dir: str | Path) -> dict[str, Any]:
    """Quality gate: accepts the staged model only if it is promotable.

    Applies the same constraints the comparison notebook uses to promote a
    model (``src/evaluation/promotion.py``). A retrained model that would not
    have been promoted in the original analysis must not reach production
    either.

    Metrics are read back from disk rather than taken from the training
    stage's return value, so the gate judges exactly what would be published.

    Args:
        model_dir: Staging directory written by ``train_model``.

    Returns:
        The directory and the metrics that were checked.

    Raises:
        QualityGateError: If any promotion constraint is violated.
        FileNotFoundError: If the staged artefacts are missing.
    """
    model_dir = Path(model_dir)
    for filename in (MODEL_FILENAME, METRICS_FILENAME):
        if not (model_dir / filename).exists():
            raise FileNotFoundError(
                f"Artefato ausente no staging: {model_dir / filename}"
            )

    payload = json.loads((model_dir / METRICS_FILENAME).read_text(encoding="utf-8"))
    checked = {**payload["test_metrics"], **payload["latency"]}

    violations = constraint_violations(checked)
    if violations:
        raise QualityGateError(
            f"Modelo {payload['candidate']} reprovado no quality gate: "
            + "; ".join(violations)
            + f". O artefato continua em {model_dir} e NAO foi publicado."
        )

    return {
        "diretorio": str(model_dir),
        "candidato": payload["candidate"],
        "f1_macro": checked["f1_macro"],
        "recall_urgente": checked["recall_urgente"],
        "latency_p95_ms": checked["latency_p95_ms"],
    }


def publish_model(
    model_dir: str | Path, ingest: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Moves an accepted model to the path the API loads from.

    Each file is copied next to its destination and then renamed over it. The
    rename is atomic, so a container starting mid-publish reads either the
    previous model or the new one -- never a half-written pickle.

    Args:
        model_dir: Staging directory that passed ``evaluate_model``.
        ingest: Output of ``ingest_data``, recorded alongside the metrics so
            the published model can be traced back to its training data.

    Returns:
        Destination directory and the files published.
    """
    model_dir = Path(model_dir)
    payload = json.loads((model_dir / METRICS_FILENAME).read_text(encoding="utf-8"))
    candidate = payload["candidate"]

    payload["publicado_em"] = datetime.now(UTC).isoformat(timespec="seconds")
    payload["run_id"] = model_dir.parent.name
    if ingest is not None:
        payload["dataset_sha256"] = ingest["sha256"]
    (model_dir / METRICS_FILENAME).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    destination = MODELS_DIR / candidate
    destination.mkdir(parents=True, exist_ok=True)

    published = []
    for filename in PUBLISHED_FILES:
        source = model_dir / filename
        if not source.exists():
            continue
        partial = destination / f".{filename}.partial"
        shutil.copy2(source, partial)
        os.replace(partial, destination / filename)
        published.append(filename)

    # The run is fully published; its staging copy has no further use. A run
    # rejected by the gate never gets here, so its artefacts stay for analysis.
    # Cleanup is confined to the staging area: a caller passing some other
    # directory must never have its parent deleted.
    run_dir = model_dir.resolve().parent
    if run_dir.parent == STAGING_DIR.resolve():
        shutil.rmtree(run_dir, ignore_errors=True)

    return {"diretorio": str(destination), "arquivos": published}
