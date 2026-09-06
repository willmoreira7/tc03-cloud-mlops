"""Shared routine for training and evaluating one candidate.

Notebooks 03 to 06 differ only in which candidate they pass to
``run_candidate``. Keeping the procedure here is what makes the comparison
fair: identical search, identical evaluation, identical latency protocol for
every model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.config import MODELS_DIR, load_config, set_seed
from src.data.loader import LABEL_COLUMN, TEXT_COLUMN, load_all_splits
from src.evaluation.metrics import measure_latency, quality_metrics
from src.models.pipelines import CANDIDATES, build_candidate, param_grid

SEARCH_METRIC = "f1_macro"


def search_best_params(
    candidate: str,
    train: pd.DataFrame,
    val: pd.DataFrame,
    seed: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Selects hyperparameters on the validation split.

    The test split is never touched here -- it is reserved for the final
    comparison, so that hyperparameter choice cannot leak into the reported
    result.

    Args:
        candidate: Key in ``CANDIDATES``.
        train: Training split.
        val: Validation split.
        seed: Random seed.

    Returns:
        Tuple of best parameters and the full search log.
    """
    rows = []
    for params in param_grid(candidate):
        model = build_candidate(candidate, seed, **params)
        model.fit(train[TEXT_COLUMN], train[LABEL_COLUMN])
        scores = quality_metrics(val[LABEL_COLUMN], model.predict(val[TEXT_COLUMN]))
        rows.append({"params": json.dumps(params, default=str), **scores})

    log = pd.DataFrame(rows).sort_values(SEARCH_METRIC, ascending=False)
    best = json.loads(log.iloc[0]["params"])
    return best, log.reset_index(drop=True)


def run_candidate(candidate: str, persist: bool = True) -> dict[str, Any]:
    """Trains, evaluates and persists one candidate end to end.

    Args:
        candidate: Key in ``CANDIDATES``.
        persist: Whether to write the model and metrics to ``models/``.

    Returns:
        Mapping with the fitted model, chosen parameters, search log,
        validation and test metrics, latency and output directory.
    """
    seed = set_seed()
    splits = load_all_splits()
    train, val, test = splits["train"], splits["val"], splits["test"]

    best_params, search_log = search_best_params(candidate, train, val, seed)

    model = build_candidate(candidate, seed, **best_params)
    model.fit(train[TEXT_COLUMN], train[LABEL_COLUMN])

    val_metrics = quality_metrics(val[LABEL_COLUMN], model.predict(val[TEXT_COLUMN]))
    test_pred = model.predict(test[TEXT_COLUMN])
    test_metrics = quality_metrics(test[LABEL_COLUMN], test_pred)
    latency = measure_latency(model, test[TEXT_COLUMN].tolist())

    output_dir = MODELS_DIR / candidate
    result = {
        "candidate": candidate,
        "model": model,
        "best_params": best_params,
        "search_log": search_log,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "latency": latency,
        "test_pred": test_pred,
        "output_dir": output_dir,
    }

    if persist:
        _persist(result)
    return result


def _persist(result: dict[str, Any]) -> None:
    """Writes model artefact and metrics to disk.

    Args:
        result: Output of ``run_candidate``.
    """
    output_dir: Path = result["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(result["model"], output_dir / "model.pkl")
    result["search_log"].to_csv(output_dir / "search_log.csv", index=False)

    payload = {
        "candidate": result["candidate"],
        "best_params": result["best_params"],
        "val_metrics": result["val_metrics"],
        "test_metrics": result["test_metrics"],
        "latency": result["latency"],
        "seed": load_config()["seed"],
    }
    with (output_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def load_comparison_table() -> pd.DataFrame:
    """Assembles the comparison table from the persisted candidate metrics.

    Lets the comparison notebook run without retraining anything: notebooks 03
    to 06 write ``models/<candidate>/metrics.json``, and this reads them back.

    Returns:
        Dataframe indexed by model name, with test metrics, latency and size.

    Raises:
        FileNotFoundError: If no candidate has been trained yet.
    """
    rows = []
    for candidate in CANDIDATES:
        metrics_file = MODELS_DIR / candidate / "metrics.json"
        if not metrics_file.exists():
            continue
        with metrics_file.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        model_file = MODELS_DIR / candidate / "model.pkl"
        size_mb = (
            round(model_file.stat().st_size / (1024 * 1024), 3)
            if model_file.exists()
            else 0.0
        )
        rows.append(
            {
                "model": candidate,
                **payload["test_metrics"],
                **payload["latency"],
                "model_size_mb": size_mb,
            }
        )

    if not rows:
        raise FileNotFoundError(
            "Nenhum modelo treinado encontrado em models/. "
            "Rode os notebooks 03 a 06 antes do 07."
        )
    return pd.DataFrame(rows).set_index("model")


def comparison_row(result: dict[str, Any]) -> dict[str, Any]:
    """Flattens one candidate result into a comparison table row.

    Args:
        result: Output of ``run_candidate``.

    Returns:
        Flat mapping ready to become a dataframe row.
    """
    size_mb = 0.0
    model_file = result["output_dir"] / "model.pkl"
    if model_file.exists():
        size_mb = round(model_file.stat().st_size / (1024 * 1024), 3)

    return {
        "model": result["candidate"],
        **result["test_metrics"],
        **result["latency"],
        "model_size_mb": size_mb,
    }
