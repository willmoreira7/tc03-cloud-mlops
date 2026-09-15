"""Tests for ONNX export and runtime equivalence."""

from __future__ import annotations

import joblib
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.optimization.onnx import (
    ONNX_FILENAME,
    ONNX_METADATA_FILENAME,
    OnnxTextClassifier,
    export_model,
)


def test_export_onnx_preserva_predicao_com_texto_acentuado(tmp_path) -> None:
    """Serving-time preprocessing must preserve sklearn predictions."""
    model_dir = tmp_path / "tfidf_logreg"
    model_dir.mkdir()
    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    strip_accents="unicode",
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    texts = [
        "infarto agudo miocardio dor toracica",
        "neoplasia tumor maligno biopsia",
        "gastrite leve inflamacao cronica",
        "convulsao neurologica recorrente",
        "exame normal sem urgencia",
        "isquemia cardiaca grave",
    ]
    labels = ["urgente", "atencao", "normal", "atencao", "normal", "urgente"]
    model.fit(texts, labels)
    joblib.dump(model, model_dir / "model.pkl")

    metadata = export_model(model_dir)
    assert metadata["preprocessing"] == ["lowercase", "strip_accents_unicode"]
    assert (model_dir / ONNX_FILENAME).exists()
    assert (model_dir / ONNX_METADATA_FILENAME).exists()

    sentence = "Paciente com infarto agudo do miocárdio e dor torácica."
    onnx_model = OnnxTextClassifier(model_dir)
    onnx_model.load()
    labels, probabilities = onnx_model.predict_with_probabilities([sentence])

    assert labels == [str(model.predict([sentence])[0])]
    assert set(probabilities[0]) == set(model.classes_)
    assert sum(probabilities[0].values()) == pytest.approx(1.0, abs=0.01)
