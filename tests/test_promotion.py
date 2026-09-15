"""Tests for the promotion rule shared by the notebook, the API and the DAG."""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import load_config
from src.evaluation.promotion import (
    NoEligibleModelError,
    constraint_violations,
    eligible_models,
    select_promoted_model,
)

RULES = load_config()["promotion"]
MIN_RECALL = float(RULES["min_recall_urgente"])
MAX_P95 = float(RULES["max_latency_p95_ms"])


def _tabela(**modelos: tuple[float, float, float]) -> pd.DataFrame:
    """Builds a comparison table from name=(f1_macro, recall_urgente, p95)."""
    return pd.DataFrame(
        [
            {
                "model": nome,
                "f1_macro": f1,
                "recall_urgente": rec,
                "latency_p95_ms": p95,
            }
            for nome, (f1, rec, p95) in modelos.items()
        ],
        columns=["model", "f1_macro", "recall_urgente", "latency_p95_ms"],
    ).set_index("model")


def test_constraint_violations_vazio_quando_elegivel() -> None:
    assert constraint_violations({"recall_urgente": 0.9, "latency_p95_ms": 1.0}) == []


def test_constraint_violations_aceita_os_limites_exatos() -> None:
    metricas = {"recall_urgente": MIN_RECALL, "latency_p95_ms": MAX_P95}
    assert constraint_violations(metricas) == []


def test_constraint_violations_explica_cada_restricao() -> None:
    metricas = {"recall_urgente": MIN_RECALL - 0.1, "latency_p95_ms": MAX_P95 + 1}
    violacoes = constraint_violations(metricas)
    assert len(violacoes) == 2
    assert "recall_urgente" in violacoes[0]
    assert "latency_p95_ms" in violacoes[1]


def test_eligible_models_filtra_por_recall_e_latencia() -> None:
    tabela = _tabela(
        bom=(0.80, 0.90, 2.0),
        lento=(0.85, 0.90, MAX_P95 + 100),
        cego=(0.90, MIN_RECALL - 0.01, 2.0),
    )
    assert eligible_models(tabela).index.tolist() == ["bom"]


def test_eligible_models_tabela_vazia() -> None:
    assert eligible_models(_tabela()).empty


def test_select_promoted_model_escolhe_maior_f1() -> None:
    tabela = _tabela(a=(0.70, 0.9, 2.0), b=(0.80, 0.9, 3.0))
    assert select_promoted_model(tabela) == "b"


def test_select_promoted_model_desempata_por_latencia() -> None:
    """Dentro de 1 ponto de F1 do lider, vence o mais rapido."""
    tabela = _tabela(lider=(0.800, 0.9, 3.0), rapido=(0.795, 0.9, 1.0))
    assert select_promoted_model(tabela) == "rapido"


def test_select_promoted_model_ignora_inelegivel_com_f1_maior() -> None:
    tabela = _tabela(ok=(0.70, 0.9, 2.0), lento=(0.95, 0.9, MAX_P95 * 10))
    assert select_promoted_model(tabela) == "ok"


def test_select_promoted_model_sem_elegivel_falha() -> None:
    tabela = _tabela(cego=(0.9, 0.0, 1.0))
    with pytest.raises(NoEligibleModelError):
        select_promoted_model(tabela)
