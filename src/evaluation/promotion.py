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

from pathlib import Path

import pandas as pd

from src.config import EVALUATION_DIR, load_config

COMPARISON_FILENAME = "metrics_comparison.csv"
_TIE_THRESHOLD = 0.01


class NoEligibleModelError(ValueError):
    """Raised when no candidate satisfies the promotion constraints."""


def eligible_models(comparison: pd.DataFrame) -> pd.DataFrame:
    """Filters candidates that satisfy both promotion constraints.

    Args:
        comparison: Table indexed by model name, carrying at least
            ``recall_urgente`` and ``latency_p95_ms`` columns.

    Returns:
        The subset of rows that are eligible for promotion.
    """
    rules = load_config()["promotion"]
    return comparison[
        (comparison["recall_urgente"] >= float(rules["min_recall_urgente"]))
        & (comparison["latency_p95_ms"] <= float(rules["max_latency_p95_ms"]))
    ]


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
