"""Tests for the retraining pipeline stages.

The end-to-end test runs the real CLI in a subprocess with ``TC03_DATA_DIR``
and ``TC03_MODELS_DIR`` pointing at a temporary directory: the paths in
``src.config`` are resolved at import time, and a subprocess is the only way
to redirect them without leaking into the rest of the test session -- or
overwriting the developer's real corpus and served model.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import joblib
import pytest

from src.config import load_config
from src.pipeline import stages

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES = load_config()["promotion"]


def _staged_model(run_dir: Path, recall_urgente: float, latency_p95_ms: float) -> Path:
    """Writes a fake staged model with the given metrics."""
    model_dir = run_dir / "tfidf_logreg"
    model_dir.mkdir(parents=True)
    (model_dir / "model.pkl").write_bytes(b"artefato")
    payload = {
        "candidate": "tfidf_logreg",
        "test_metrics": {"f1_macro": 0.8, "recall_urgente": recall_urgente},
        "latency": {"latency_p95_ms": latency_p95_ms},
    }
    (model_dir / "metrics.json").write_text(json.dumps(payload), encoding="utf-8")
    return model_dir


@pytest.fixture
def isolated_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points publishing and staging at a temporary models directory."""
    models = tmp_path / "models"
    monkeypatch.setattr(stages, "MODELS_DIR", models)
    monkeypatch.setattr(stages, "STAGING_DIR", models / "_staging")
    return models


def test_staging_dir_normaliza_run_id_do_airflow() -> None:
    caminho = stages.staging_dir("manual__2026-09-14T15:30:00+00:00")
    assert caminho.name == "manual__2026-09-14T15_30_00_00_00"


def test_evaluate_aprova_modelo_elegivel(tmp_path: Path) -> None:
    model_dir = _staged_model(tmp_path / "run", recall_urgente=0.9, latency_p95_ms=1.0)
    resultado = stages.evaluate_model(model_dir)
    assert resultado["candidato"] == "tfidf_logreg"
    assert resultado["recall_urgente"] == 0.9


@pytest.mark.parametrize(
    ("recall", "p95", "motivo"),
    [
        (float(RULES["min_recall_urgente"]) - 0.1, 1.0, "recall_urgente"),
        (0.9, float(RULES["max_latency_p95_ms"]) + 1, "latency_p95_ms"),
    ],
    ids=["recall-baixo", "latencia-alta"],
)
def test_evaluate_reprova_modelo_fora_do_criterio(
    tmp_path: Path, recall: float, p95: float, motivo: str
) -> None:
    model_dir = _staged_model(
        tmp_path / "run", recall_urgente=recall, latency_p95_ms=p95
    )
    with pytest.raises(stages.QualityGateError, match=motivo):
        stages.evaluate_model(model_dir)


def test_evaluate_falha_sem_artefato(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        stages.evaluate_model(tmp_path / "inexistente")


def test_publish_move_artefato_e_limpa_staging(isolated_models: Path) -> None:
    run_dir = stages.STAGING_DIR / "run-1"
    model_dir = _staged_model(run_dir, recall_urgente=0.9, latency_p95_ms=1.0)

    resultado = stages.publish_model(model_dir, {"sha256": {"a.csv": "abc"}})

    destino = isolated_models / "tfidf_logreg"
    assert (destino / "model.pkl").read_bytes() == b"artefato"
    metricas = json.loads((destino / "metrics.json").read_text(encoding="utf-8"))
    assert metricas["run_id"] == "run-1"
    assert metricas["dataset_sha256"] == {"a.csv": "abc"}
    assert resultado["arquivos"] == ["model.pkl", "metrics.json"]
    assert not run_dir.exists()
    assert not list(destino.glob(".*.partial"))


def test_publish_substitui_modelo_anterior(isolated_models: Path) -> None:
    destino = isolated_models / "tfidf_logreg"
    destino.mkdir(parents=True)
    (destino / "model.pkl").write_bytes(b"antigo")

    model_dir = _staged_model(stages.STAGING_DIR / "run-2", 0.9, 1.0)
    stages.publish_model(model_dir)

    assert (destino / "model.pkl").read_bytes() == b"artefato"


def test_publish_fora_do_staging_nao_apaga_o_diretorio_pai(
    isolated_models: Path, tmp_path: Path
) -> None:
    """Limpeza restrita ao staging: nunca remove o pai de um caminho qualquer."""
    fora = tmp_path / "outro-lugar"
    model_dir = _staged_model(fora, 0.9, 1.0)
    stages.publish_model(model_dir)
    assert model_dir.exists()


def test_pipeline_ponta_a_ponta_com_dados_sinteticos(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "TC03_DATA_DIR": str(tmp_path / "data"),
        "TC03_MODELS_DIR": str(tmp_path / "models"),
    }

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

    gerado = run("scripts/gen_synthetic_data.py", "--rows", "800")
    assert gerado.returncode == 0, gerado.stdout + gerado.stderr

    treino = run("scripts/train_serving_model.py")
    assert treino.returncode == 0, treino.stdout + treino.stderr
    assert "aprovado no quality gate" in treino.stdout
    assert "onnx         aprovado" in treino.stdout

    publicado = tmp_path / "models" / load_config()["serving"]["model"]
    for arquivo in stages.PUBLISHED_FILES:
        assert (publicado / arquivo).exists(), arquivo
    assert not any((tmp_path / "models" / "_staging").iterdir())

    metricas = json.loads((publicado / "metrics.json").read_text(encoding="utf-8"))
    assert "medical_tc_train.csv" in metricas["dataset_sha256"]
    assert metricas["onnx"]["mismatch_rate"] <= metricas["onnx"]["max_mismatch_rate"]

    modelo = joblib.load(publicado / "model.pkl")
    predicao = modelo.predict(["paciente com isquemia e infarto ventricular agudo"])
    assert predicao[0] in load_config()["classes"]


def test_export_onnx_reprova_modelo_que_viola_promocao(monkeypatch) -> None:
    """O ONNX servido tambem precisa passar nas restricoes de promocao.

    O gate anterior julga o `.pkl`. Um ONNX equivalente dentro do limite de
    divergencia ainda pode derrubar o recall de `urgente` abaixo do minimo --
    e nesse caso nao pode ser publicado.
    """
    monkeypatch.setattr(
        stages, "export_model", lambda _dir: {"onnx_model_size_mb": 0.1}
    )
    monkeypatch.setattr(
        stages,
        "compare_artifacts",
        lambda _dir: {
            "mismatch_rate": 0.0,
            "mismatches": 0,
            "checked_predictions": 100,
            "equivalent_predictions": True,
            "onnx_quality": {"recall_urgente": 0.10},
            "onnx_latency": {"latency_p95_ms": 1.0},
        },
    )

    with pytest.raises(stages.QualityGateError, match="restricoes de promocao"):
        stages.export_onnx_model("qualquer/diretorio")
