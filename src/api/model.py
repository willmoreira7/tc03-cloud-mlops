"""Loading and serving the classifier.

The model is loaded once, at application startup, and held in memory. Loading
it per request would dominate the response time entirely -- deserialising the
pipeline costs far more than the inference itself.

Which model is served comes from configuration, not from the promotion rule
directly: the promoted model and the served model can legitimately differ (see
ADR 10 in docs/ARQUITETURA.md), and that divergence has to be explicit rather
than accidental.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import joblib

from src.config import MODELS_DIR, load_config


class ModelNotLoadedError(RuntimeError):
    """Raised when a prediction is attempted before the model is available."""


class UrgencyClassifier:
    """Wraps the fitted pipeline with the API's serving concerns."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._pipeline: Any | None = None

    @property
    def loaded(self) -> bool:
        """Whether the underlying pipeline is in memory."""
        return self._pipeline is not None

    @property
    def path(self) -> Path:
        """Filesystem location of the serialised pipeline."""
        return MODELS_DIR / self.name / "model.pkl"

    def load(self) -> None:
        """Reads the pipeline from disk.

        Raises:
            FileNotFoundError: If the artefact is missing. Failing here, at
                startup, is deliberate: the container refuses to come up rather
                than accepting traffic it cannot serve.
        """
        if not self.path.exists():
            raise FileNotFoundError(
                f"Artefato do modelo nao encontrado em {self.path}. "
                "Rode os notebooks 01 a 07 ou monte o volume de modelos."
            )
        self._pipeline = joblib.load(self.path)

    def predict(self, texto: str) -> dict[str, Any]:
        """Classifies one report.

        Args:
            texto: The clinical report text.

        Returns:
            Mapping with the predicted class, per-class probabilities when the
            estimator supports them, and the measured inference time.

        Raises:
            ModelNotLoadedError: If called before ``load``.
        """
        if self._pipeline is None:
            raise ModelNotLoadedError("Modelo nao carregado")

        start = time.perf_counter()
        predicted = str(self._pipeline.predict([texto])[0])

        probabilidades: dict[str, float] | None = None
        confianca: float | None = None
        if hasattr(self._pipeline, "predict_proba"):
            scores = self._pipeline.predict_proba([texto])[0]
            probabilidades = {
                str(label): round(float(score), 4)
                for label, score in zip(self._pipeline.classes_, scores)
            }
            confianca = probabilidades[predicted]

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "urgencia": predicted,
            "confianca": confianca,
            "probabilidades": probabilidades,
            "latencia_ms": round(elapsed_ms, 3),
            "modelo": self.name,
        }


_classifier: UrgencyClassifier | None = None


def get_classifier() -> UrgencyClassifier:
    """Returns the process-wide classifier instance.

    Returns:
        The singleton classifier, created on first call.
    """
    global _classifier
    if _classifier is None:
        _classifier = UrgencyClassifier(load_config()["serving"]["model"])
    return _classifier
