"""The promotion rule: the single source of truth for "best model".

The comparison notebook, the Airflow retraining DAG and the API all resolve
the promoted model through these functions. If each implemented its own rule
they would drift apart silently, and the model being served would stop
matching the one the evaluation says was chosen.

The rule itself is declared in configs/model_config.yaml, before any model is
trained -- picking the winner first and the metric afterwards is not a
criterion.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import EVALUATION_DIR, load_config

COMPARISON_FILENAME = "metrics_comparison.csv"
_TIE_THRESHOLD = 0.01


class NoEligibleModelError(ValueError):
    """Raised when no candidate satisfies the promotion constraints."""


def constraint_violations(metrics: Mapping[str, Any]) -> list[str]:
    """Lists which promotion constraints one model fails.

    The comparison notebook only needs to know *whether* a model is eligible;
    the retraining quality gate also has to say *why* it rejected one, so the
    rule is expressed per model and the table filter is built on top of it.

    Args:
        metrics: Mapping carrying at least ``recall_urgente`` and
            ``latency_p95_ms``.

    Returns:
        One human-readable message per violated constraint; empty if eligible.
    """
    rules = load_config()["promotion"]
    min_recall = float(rules["min_recall_urgente"])
    max_p95 = float(rules["max_latency_p95_ms"])

    violations = []
    if float(metrics["recall_urgente"]) < min_recall:
        violations.append(
            f"recall_urgente {float(metrics['recall_urgente']):.4f} < {min_recall}"
        )
    if float(metrics["latency_p95_ms"]) > max_p95:
        violations.append(
            f"latency_p95_ms {float(metrics['latency_p95_ms']):.2f} > {max_p95}"
        )
    return violations


def eligible_models(comparison: pd.DataFrame) -> pd.DataFrame:
    """Filters candidates that satisfy both promotion constraints.

    Args:
        comparison: Table indexed by model name, carrying at least
            ``recall_urgente`` and ``latency_p95_ms`` columns.

    Returns:
        The subset of rows that are eligible for promotion.
    """
    if comparison.empty:
        return comparison
    eligible = comparison.apply(lambda row: not constraint_violations(row), axis=1)
    return comparison[eligible.astype(bool)]


def select_promoted_model(comparison: pd.DataFrame) -> str:
    """Returns the model promoted to production.

    Highest ``f1_macro`` among eligible candidates. A technical tie (within
    one percentage point of the leader) is resolved by the lower p95 latency,
    since at equivalent quality the faster model is strictly better.

    Args:
        comparison: Table indexed by model name.

    Returns:
        Name of the promoted model.

    Raises:
        NoEligibleModelError: If no candidate satisfies the constraints.
    """
    rules = load_config()["promotion"]
    metric = rules["metric"]

    eligible = eligible_models(comparison)
    if eligible.empty:
        raise NoEligibleModelError(
            "Nenhum modelo satisfaz as restricoes de promocao "
            f"(recall_urgente >= {rules['min_recall_urgente']}, "
            f"latency_p95_ms <= {rules['max_latency_p95_ms']}). "
            "Rever os limiares em configs/model_config.yaml e registrar a mudanca."
        )

    best_score = eligible[metric].max()
    contenders = eligible[eligible[metric] >= best_score - _TIE_THRESHOLD]
    return str(contenders["latency_p95_ms"].idxmin())


def promoted_model_from_csv(path: Path | None = None) -> str | None:
    """Reads the comparison table and returns the promoted model name.

    Args:
        path: Optional override for the comparison CSV location.

    Returns:
        The promoted model name, or ``None`` if the file does not exist.
    """
    csv_path = path or EVALUATION_DIR / COMPARISON_FILENAME
    if not csv_path.exists():
        return None
    comparison = pd.read_csv(csv_path, index_col="model")
    return select_promoted_model(comparison)
