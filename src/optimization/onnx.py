"""ONNX export and runtime helpers for the text classifier.

The scikit-learn pipeline uses ``TfidfVectorizer(strip_accents="unicode")``.
``skl2onnx`` cannot convert that accent stripping into the ONNX graph, and
``onnxruntime`` may fail to initialise text normalisation locales in slim Linux
images. The portable option is explicit and testable: normalise text in Python,
then run an ONNX graph whose vectoriser receives already-normalised strings.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import onnxruntime as ort
import pandas as pd
from sklearn.feature_extraction.text import strip_accents_unicode

from src.data.loader import LABEL_COLUMN, TEXT_COLUMN, load_all_splits
from src.evaluation.metrics import measure_latency, quality_metrics

MODEL_FILENAME = "model.pkl"
ONNX_FILENAME = "model.onnx"
ONNX_METADATA_FILENAME = "onnx_metadata.json"
LATENCY_COMPARISON_FILENAME = "latency_comparison.csv"
TEXT_INPUT_NAME = "texto"


class OnnxTextClassifier:
    """Small runtime wrapper around the exported ONNX text classifier."""

    def __init__(self, model_dir: str | Path) -> None:
        """Stores the model directory without loading the runtime session.

        Args:
            model_dir: Directory containing ``model.onnx`` and metadata.
        """
        self.model_dir = Path(model_dir)
        self.session: ort.InferenceSession | None = None
        self.metadata: dict[str, Any] = {}

    @property
    def path(self) -> Path:
        """Filesystem path of the ONNX artefact."""
        return self.model_dir / ONNX_FILENAME

    @property
    def loaded(self) -> bool:
        """Whether the ONNX Runtime session is ready."""
        return self.session is not None

    def load(self) -> None:
        """Loads metadata and creates the ONNX Runtime session.

        Raises:
            FileNotFoundError: If the ONNX artefact or metadata file is absent.
        """
        metadata_path = self.model_dir / ONNX_METADATA_FILENAME
        if not self.path.exists():
            raise FileNotFoundError(f"Artefato ONNX nao encontrado em {self.path}")
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadados ONNX ausentes em {metadata_path}")

        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.session = ort.InferenceSession(
            str(self.path), providers=["CPUExecutionProvider"]
        )

    def predict(self, texts: list[str]) -> list[str]:
        """Predicts classes for one or more texts.

        Args:
            texts: Raw texts, before serving-time normalisation.

        Returns:
            Predicted class for each text.
        """
        labels, _ = self.predict_with_probabilities(texts)
        return labels

    def predict_with_probabilities(
        self, texts: list[str]
    ) -> tuple[list[str], list[dict[str, float]]]:
        """Predicts classes and per-class probabilities.

        Args:
            texts: Raw texts, before serving-time normalisation.

        Returns:
            Tuple with predicted labels and probability mappings.

        Raises:
            RuntimeError: If called before ``load``.
        """
        if self.session is None:
            raise RuntimeError("Sessao ONNX nao carregada")

        input_name = self.metadata.get("input_name", self.session.get_inputs()[0].name)
        normalized = np.asarray(normalize_texts(texts), dtype=object).reshape((-1, 1))
        labels, probabilities = self.session.run(None, {input_name: normalized})

        classes = [str(label) for label in self.metadata["classes"]]
        probability_rows = np.asarray(probabilities, dtype=float)
        return (
            [str(label) for label in labels],
            [
                {
                    label: round(float(score), 4)
                    for label, score in zip(classes, row, strict=True)
                }
                for row in probability_rows
            ],
        )


def normalize_texts(texts: list[str]) -> list[str]:
    """Applies the text normalisation moved out of the ONNX graph.

    Args:
        texts: Raw input texts.

    Returns:
        Lower-cased and accent-stripped texts.
    """
    return [strip_accents_unicode(text.lower()) for text in texts]


def export_model(model_dir: str | Path) -> dict[str, Any]:
    """Converts the fitted scikit-learn pipeline into ONNX.

    Args:
        model_dir: Directory containing the trained ``model.pkl``.

    Returns:
        Metadata written next to the ONNX artefact.

    Raises:
        FileNotFoundError: If the pickle artefact is absent.
    """
    model_dir = Path(model_dir)
    model_path = model_dir / MODEL_FILENAME
    if not model_path.exists():
        raise FileNotFoundError(f"Artefato sklearn ausente em {model_path}")

    pipeline = joblib.load(model_path)
    export_pipeline = copy.deepcopy(pipeline)
    vectorizer = export_pipeline.named_steps["tfidf"]
    vectorizer.lowercase = False
    vectorizer.strip_accents = None

    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import StringTensorType

    options = {id(export_pipeline.named_steps["clf"]): {"zipmap": False}}
    onnx_model = convert_sklearn(
        export_pipeline,
        initial_types=[(TEXT_INPUT_NAME, StringTensorType([None, 1]))],
        options=options,
        target_opset=17,
    )

    onnx_path = model_dir / ONNX_FILENAME
    onnx_path.write_bytes(onnx_model.SerializeToString())

    outputs = [output.name for output in onnx_model.graph.output]
    metadata = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_model": MODEL_FILENAME,
        "onnx_model": ONNX_FILENAME,
        "classes": [str(label) for label in pipeline.classes_],
        "input_name": TEXT_INPUT_NAME,
        "label_output": outputs[0],
        "probability_output": outputs[1],
        "preprocessing": ["lowercase", "strip_accents_unicode"],
        "target_opset": 17,
        "sklearn_model_size_mb": _size_mb(model_path),
        "onnx_model_size_mb": _size_mb(onnx_path),
    }
    (model_dir / ONNX_METADATA_FILENAME).write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return metadata


def compare_artifacts(model_dir: str | Path) -> dict[str, Any]:
    """Compares sklearn and ONNX predictions, latency and artefact size.

    Args:
        model_dir: Directory containing ``model.pkl`` and ``model.onnx``.

    Returns:
        Summary with equivalence, latency and size comparison.
    """
    model_dir = Path(model_dir)
    test = load_all_splits()["test"]
    texts = test[TEXT_COLUMN].tolist()
    y_true = test[LABEL_COLUMN].tolist()

    sklearn_model = joblib.load(model_dir / MODEL_FILENAME)
    onnx_model = OnnxTextClassifier(model_dir)
    onnx_model.load()

    sklearn_pred = [str(label) for label in sklearn_model.predict(texts)]
    onnx_pred = onnx_model.predict(texts)
    mismatches = sum(left != right for left, right in zip(sklearn_pred, onnx_pred))
    checked = len(texts)
    equivalent = mismatches == 0

    sklearn_latency = measure_latency(sklearn_model, texts)
    onnx_latency = measure_latency(onnx_model, texts)
    onnx_quality = quality_metrics(y_true, onnx_pred)

    rows = [
        _comparison_row("sklearn", model_dir / MODEL_FILENAME, sklearn_latency),
        _comparison_row("onnx", model_dir / ONNX_FILENAME, onnx_latency),
    ]
    comparison = pd.DataFrame(rows)
    comparison.to_csv(model_dir / LATENCY_COMPARISON_FILENAME, index=False)

    return {
        "equivalent_predictions": equivalent,
        "checked_predictions": checked,
        "mismatches": mismatches,
        "mismatch_rate": mismatches / checked if checked else 0.0,
        "sklearn_latency": sklearn_latency,
        "onnx_latency": onnx_latency,
        "onnx_quality": onnx_quality,
        "latency_comparison": rows,
    }


def _comparison_row(
    runtime: str, model_path: Path, latency: dict[str, float]
) -> dict[str, Any]:
    return {"runtime": runtime, "size_mb": _size_mb(model_path), **latency}


def _size_mb(path: Path) -> float:
    return round(path.stat().st_size / (1024 * 1024), 3)
