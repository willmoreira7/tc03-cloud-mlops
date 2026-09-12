"""Tests for the Prometheus instrumentation.

These verify that the /metrics endpoint is mounted, that the request counter
increments per (endpoint, status), and that the prediction counter increments
per class. They do not assert on exact metric values -- only on the presence
and growth of the series, which is what the dashboard depends on.
"""

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


def test_metrics_endpoint_exposto(client: TestClient) -> None:
    """O endpoint /metrics deve responder 200 e expor as metricas do servico."""
    resposta = client.get("/metrics")
    assert resposta.status_code == 200
    corpo = resposta.text
    assert "triagem_requests_total" in corpo
    assert "triagem_latency_seconds" in corpo
    assert "triagem_predictions_total" in corpo


def test_contador_de_requisicos_incrementa(client: TestClient) -> None:
    """Cada chamada a /predict deve incrementar o contador por endpoint e status."""
    antes = client.get("/metrics").text
    client.post("/predict", json={"texto": LAUDO_VALIDO})
    depois = client.get("/metrics").text

    linha = 'triagem_requests_total{endpoint="/predict",status="200"}'
    assert linha in antes or linha in depois
    # O contador deve crescer apos a chamada.
    valor_antes = _extrair_contador(antes, '"/predict"', '"200"')
    valor_depois = _extrair_contador(depois, '"/predict"', '"200"')
    assert valor_depois > valor_antes


def test_contador_de_predicoes_incrementa_por_classe(
    client: TestClient,
) -> None:
    """Uma predicao valida deve incrementar o contador da classe predita."""
    resposta = client.post("/predict", json={"texto": LAUDO_VALIDO})
    assert resposta.status_code == 200
    classe = resposta.json()["urgencia"]

    corpo = client.get("/metrics").text
    linha = f'triagem_predictions_total{{urgencia="{classe}"}}'
    assert linha in corpo


def test_requisicao_invalida_conta_como_422(client: TestClient) -> None:
    """Entrada malformada deve registrar status 422, nao 500."""
    client.post("/predict", json={"texto": "curto demais"})
    corpo = client.get("/metrics").text
    assert 'triagem_requests_total{endpoint="/predict",status="422"}' in corpo


def _extrair_contador(corpo: str, endpoint: str, status: str) -> float:
    """Extrai o valor atual de um contador a partir do texto do /metrics.

    Args:
        corpo: O corpo da resposta de /metrics.
        endpoint: O label endpoint a buscar.
        status: O label status a buscar.

    Returns:
        O valor do contador, ou 0.0 se a serie ainda nao existe.
    """
    for linha in corpo.splitlines():
        if linha.startswith("triagem_requests_total"):
            if f"endpoint={endpoint}" in linha and f"status={status}" in linha:
                return float(linha.split()[-1])
    return 0.0
