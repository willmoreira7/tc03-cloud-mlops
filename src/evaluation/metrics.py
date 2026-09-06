"""Quality metrics and the inference latency protocol.

Latency is measured the way the API will experience it: one document per
call, after discarding warm-up calls. Measuring a batch and dividing by the
batch size amortises cost that a real request pays in full.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from src.config import load_config

URGENT_CLASS = "urgente"


def quality_metrics(y_true: Any, y_pred: Any) -> dict[str, float]:
    """Computes the metrics used to compare models.

    Accuracy is reported for reference only -- with an imbalanced target it
    rewards a model that ignores the minority class, which is exactly the
    class that matters here.

    Args:
        y_true: Ground-truth labels.
        y_pred: Predicted labels.

    Returns:
        Mapping of metric name to value.
    """
    classes = load_config()["classes"]
    metrics = {
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "accuracy": float((np.asarray(y_true) == np.asarray(y_pred)).mean()),
    }
    for label in classes:
        metrics[f"recall_{label}"] = recall_score(
            y_true, y_pred, labels=[label], average="macro", zero_division=0
        )
        metrics[f"precision_{label}"] = precision_score(
            y_true, y_pred, labels=[label], average="macro", zero_division=0
        )
    return metrics


def confusion(y_true: Any, y_pred: Any) -> pd.DataFrame:
    """Builds a labelled confusion matrix.

    Args:
        y_true: Ground-truth labels.
        y_pred: Predicted labels.

    Returns:
        Dataframe indexed by true class, columns by predicted class.
    """
    classes = load_config()["classes"]
    matrix = confusion_matrix(y_true, y_pred, labels=classes)
    return pd.DataFrame(
        matrix,
        index=pd.Index(classes, name="real"),
        columns=pd.Index(classes, name="predito"),
    )


def report(y_true: Any, y_pred: Any) -> str:
    """Returns the per-class scikit-learn text report.

    Args:
        y_true: Ground-truth labels.
        y_pred: Predicted labels.

    Returns:
        The formatted classification report.
    """
    return classification_report(
        y_true, y_pred, labels=load_config()["classes"], zero_division=0
    )


def measure_latency(
    model: Any,
    texts: list[str],
    warmup: int | None = None,
    calls: int | None = None,
    max_seconds: float | None = None,
) -> dict[str, float]:
    """Measures single-sample inference latency.

    Runs up to ``calls`` measurements, stopping early if ``max_seconds`` is
    exceeded -- but never below ``min_calls``. The budget exists because a slow
    model (a Random Forest over TF-IDF can sit at hundreds of milliseconds per
    call) would otherwise make the measurement alone take several minutes.

    The actual number of measurements is reported in ``latency_n_calls``: a
    percentile computed from fewer samples is noisier, particularly p99, and
    that has to be visible rather than implied.

    Args:
        model: Fitted estimator exposing ``predict``.
        texts: Pool of documents to sample calls from.
        warmup: Calls discarded before measuring; defaults to config.
        calls: Maximum measured calls; defaults to config.
        max_seconds: Wall-clock budget for the measured phase.

    Returns:
        Mapping with p50, p95, p99, mean latency in milliseconds and the
        number of calls actually measured.
    """
    config = load_config()["latency"]
    n_warmup = warmup if warmup is not None else int(config["warmup_calls"])
    n_calls = calls if calls is not None else int(config["measured_calls"])
    budget = max_seconds if max_seconds is not None else float(config["max_seconds"])
    min_calls = min(int(config["min_calls"]), n_calls)

    pool = list(texts)
    if not pool:
        raise ValueError("Lista de textos vazia - impossivel medir latencia")

    for index in range(n_warmup):
        model.predict([pool[index % len(pool)]])

    samples: list[float] = []
    deadline = time.perf_counter() + budget
    for index in range(n_calls):
        document = pool[index % len(pool)]
        start = time.perf_counter()
        model.predict([document])
        samples.append((time.perf_counter() - start) * 1000.0)
        if len(samples) >= min_calls and time.perf_counter() >= deadline:
            break

    measured = np.asarray(samples)
    return {
        "latency_p50_ms": float(np.percentile(measured, 50)),
        "latency_p95_ms": float(np.percentile(measured, 95)),
        "latency_p99_ms": float(np.percentile(measured, 99)),
        "latency_mean_ms": float(measured.mean()),
        "latency_n_calls": int(measured.size),
    }
