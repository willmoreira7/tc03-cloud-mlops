"""Request and response contracts for the inference API.

The validation here is what turns malformed input into a 422 instead of a 500
-- which matters beyond tidiness: a 500 pollutes the error-rate panel that the
monitoring stage grades, while a 422 correctly reports a client mistake.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MIN_TEXT_CHARS = 30


class PredictRequest(BaseModel):
    """Incoming clinical report."""

    texto: str = Field(
        ...,
        description="Texto do laudo medico a ser classificado.",
        examples=["Paciente apresenta dor toracica de inicio subito com irradiacao..."],
    )

    @field_validator("texto")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Rejects blank or too-short reports.

        The same 30-character floor used when building the training splits: a
        text below it was never represented in training, so a prediction over
        it would be unfounded.
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError("O texto do laudo nao pode ser vazio")
        if len(stripped) < MIN_TEXT_CHARS:
            raise ValueError(
                f"O texto do laudo deve ter ao menos {MIN_TEXT_CHARS} caracteres"
            )
        return stripped


class PredictResponse(BaseModel):
    """Classification result for one report."""

    urgencia: str = Field(
        ..., description="Classe predita: normal, atencao ou urgente."
    )
    confianca: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "Probabilidade da classe predita. Null quando o modelo servido nao "
            "expoe predict_proba."
        ),
    )
    probabilidades: dict[str, float] | None = Field(
        None, description="Probabilidade por classe, quando disponivel."
    )
    latencia_ms: float = Field(..., description="Tempo de inferencia no servidor.")
    modelo: str = Field(..., description="Identificador do modelo que respondeu.")


class HealthResponse(BaseModel):
    """Service health payload."""

    status: str
    modelo: str
    modelo_carregado: bool
    versao: str


class ErrorResponse(BaseModel):
    """Uniform error body, so the client always parses the same shape."""

    erro: str
    detalhe: str | None = None
