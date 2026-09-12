"""Prometheus metric definitions and the middleware that records them.

The metrics follow the RED method (Rate, Errors, Duration) for the service
layer, plus a model-layer counter for the predicted urgency distribution.
That is the minimum set the Tech Challenge dashboard needs -- nothing more.

Metric naming follows the Prometheus convention: snake_case, base SI unit in
the suffix (``_seconds``), ``_total`` for counters, and dimensions in labels
rather than in the name. Cardinality is bounded: ``endpoint`` is the route
path, ``status`` is the HTTP code, and ``urgencia`` is one of three classes.
No request id, no free-text field -- those would blow up the TSDB.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, Info, make_asgi_app

# Buckets chosen for a lightweight text classifier: the interesting region is
# a few milliseconds to a few hundred. A bucket is free to compute but costs
# one time series per (bucket x label combination), so the list is short.
LATENCY_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
)

REQUESTS = Counter(
    "triagem_requests_total",
    "Requisicoes recebidas pelo servico.",
    ["endpoint", "status"],
)

LATENCY = Histogram(
    "triagem_latency_seconds",
    "Latencia ponta a ponta de cada requisicao.",
    ["endpoint"],
    buckets=LATENCY_BUCKETS,
)

PREDICTIONS = Counter(
    "triagem_predictions_total",
    "Predicoes emitidas por nivel de urgencia.",
    ["urgencia"],
)

MODEL_INFO = Info(
    "triagem_model",
    "Metadados do modelo servido em memoria.",
)


def install_metrics(app: FastAPI) -> None:
    """Wires the metrics middleware and the /metrics endpoint to the app.

    The ASGI app from ``prometheus_client`` is mounted at ``/metrics/`` (with
    trailing slash). FastAPI/Starlette redirects ``/metrics`` to ``/metrics/``
    by default, and the Prometheus scrape config points at ``/metrics/`` to
    avoid that extra redirect on every scrape.

    Args:
        app: The FastAPI application to instrument.
    """
    app.middleware("http")(_metrics_middleware)
    app.mount("/metrics", make_asgi_app())


async def _metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Records request count, status and duration for every HTTP call.

    The endpoint label is the route path (``/predict``, ``/health``) rather
    than the raw URL, so parameterised routes do not fragment the series.
    Errors raised inside the handler are re-raised after being counted, so the
    client still sees the real status code.

    Args:
        request: The incoming HTTP request.
        call_next: The next middleware or the route handler.

    Returns:
        The response produced by the handler.

    Raises:
        Exception: Whatever the handler raised, after being recorded.
    """
    endpoint = request.url.path
    # Normalises /metrics and /metrics/ to the same label so the redirect
    # does not fragment the series into two endpoints.
    if endpoint == "/metrics/":
        endpoint = "/metrics"
    start = time.perf_counter()
    status_code = "500"

    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        elapsed = time.perf_counter() - start
        REQUESTS.labels(endpoint=endpoint, status=status_code).inc()
        LATENCY.labels(endpoint=endpoint).observe(elapsed)


def record_prediction(urgencia: str) -> None:
    """Increments the per-class prediction counter.

    Args:
        urgencia: The predicted urgency class (normal, atencao or urgente).
    """
    PREDICTIONS.labels(urgencia=urgencia).inc()


def set_model_info(name: str, version: str) -> None:
    """Publishes the served model metadata as an Info metric.

    Args:
        name: The served model identifier.
        version: The application version string.
    """
    MODEL_INFO.info({"name": name, "version": version})
