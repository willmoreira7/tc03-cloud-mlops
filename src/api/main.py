"""FastAPI application for urgency triage of medical reports.

Endpoints:
    POST /predict  -- classifies one report
    GET  /health   -- liveness and model status, used by the container healthcheck
    GET  /         -- service identification
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.model import ModelNotLoadedError, get_classifier
from src.api.schemas import (
    ErrorResponse,
    HealthResponse,
    PredictRequest,
    PredictResponse,
)

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Loads the model before the service accepts traffic.

    A missing artefact raises here and the application never starts. That is
    the intended behaviour: an instance that cannot classify should fail its
    health check and be replaced, not answer 500 to every request.
    """
    classifier = get_classifier()
    classifier.load()
    yield


app = FastAPI(
    title="Triagem de Laudos Medicos",
    description=(
        "Classifica o texto de um laudo medico em tres niveis de urgencia "
        "(normal, atencao, urgente) para priorizar a fila de leitura.\n\n"
        "AVISO: o rotulo de urgencia e derivado por regra e nao foi validado "
        "clinicamente. Uso academico."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Returns a uniform 422 body for schema violations."""
    detalhes = "; ".join(
        f"{'.'.join(str(p) for p in err['loc'][1:])}: {err['msg']}"
        for err in exc.errors()
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ErrorResponse(
            erro="Requisicao invalida", detalhe=detalhes
        ).model_dump(),
    )


@app.exception_handler(ModelNotLoadedError)
async def model_handler(request: Request, exc: ModelNotLoadedError) -> JSONResponse:
    """Returns 503 while the model is unavailable, never 500."""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse(
            erro="Modelo indisponivel", detalhe=str(exc)
        ).model_dump(),
    )


@app.get("/", tags=["servico"])
async def root() -> dict[str, str]:
    """Identifies the service."""
    return {
        "servico": "Triagem de Laudos Medicos",
        "versao": APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["servico"])
async def health() -> HealthResponse:
    """Reports liveness and whether the model is in memory."""
    classifier = get_classifier()
    return HealthResponse(
        status="ok" if classifier.loaded else "degradado",
        modelo=classifier.name,
        modelo_carregado=classifier.loaded,
        versao=APP_VERSION,
    )


@app.post(
    "/predict",
    response_model=PredictResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Texto invalido"},
        503: {"model": ErrorResponse, "description": "Modelo indisponivel"},
    },
    tags=["inferencia"],
)
async def predict(payload: PredictRequest) -> PredictResponse:
    """Classifies the urgency of one clinical report.

    Args:
        payload: Request carrying the report text.

    Returns:
        Predicted class, per-class probabilities and server-side latency.
    """
    resultado = get_classifier().predict(payload.texto)
    return PredictResponse(**resultado)
