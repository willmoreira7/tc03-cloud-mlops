"""Tests for the inference API contract."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.model import get_classifier

LAUDO_VALIDO = (
    "Paciente apresenta dor toracica de inicio subito com irradiacao para o "
    "membro superior esquerdo, associada a sudorese e dispneia."
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Client that runs the app lifespan, so the model is loaded."""
    if not get_classifier().path.exists():
        pytest.skip("Artefato do modelo ausente - rode os notebooks 01 a 07")
    with TestClient(app) as test_client:
        yield test_client


def test_health_reporta_modelo_carregado(client: TestClient) -> None:
    resposta = client.get("/health")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "ok"
    assert corpo["modelo_carregado"] is True


def test_predict_retorna_classe_valida(client: TestClient) -> None:
    resposta = client.post("/predict", json={"texto": LAUDO_VALIDO})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["urgencia"] in {"normal", "atencao", "urgente"}
    assert corpo["latencia_ms"] > 0


def test_predict_retorna_probabilidades(client: TestClient) -> None:
    """O modelo servido deve expor score de confianca (ADR 10)."""
    corpo = client.post("/predict", json={"texto": LAUDO_VALIDO}).json()
    assert corpo["confianca"] is not None
    assert 0.0 <= corpo["confianca"] <= 1.0
    assert set(corpo["probabilidades"]) == {"normal", "atencao", "urgente"}
    assert corpo["probabilidades"][corpo["urgencia"]] == corpo["confianca"]
    assert sum(corpo["probabilidades"].values()) == pytest.approx(1.0, abs=0.01)


@pytest.mark.parametrize(
    "texto",
    ["", "   ", "curto demais"],
    ids=["vazio", "so-espacos", "abaixo-do-minimo"],
)
def test_predict_rejeita_texto_invalido(client: TestClient, texto: str) -> None:
    """Entrada malformada vira 422, nunca 500.

    Um 500 poluiria o painel de taxa de erro da stack de monitoramento com o
    que na verdade e erro do cliente.
    """
    resposta = client.post("/predict", json={"texto": texto})
    assert resposta.status_code == 422
    assert resposta.json()["erro"] == "Requisicao invalida"


def test_predict_exige_campo_texto(client: TestClient) -> None:
    assert client.post("/predict", json={}).status_code == 422
