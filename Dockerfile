# Build em dois estagios: o builder resolve as dependencias com uv, o runtime
# carrega apenas a venv, o codigo e o artefato do modelo.
#
# O runtime NAO instala o grupo dev (jupyter, matplotlib, seaborn, pytest):
# nada disso participa da inferencia, e mante-los inflaria a imagem sem
# beneficio - o que contraria o requisito de latencia e de tamanho.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 1) Dependencias primeiro, em camada propria: so e reconstruida quando o lock
#    muda, nao a cada alteracao de codigo.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Codigo e instalacao do projeto.
COPY src/ ./src/
COPY configs/ ./configs/
RUN uv sync --frozen --no-dev


FROM python:3.12-slim AS runtime

# Usuario sem privilegios: um comprometimento do processo nao vira root no host.
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser configs/ ./configs/
# O artefato treinado. Em producao viria do S3, publicado pelo job de retreino.
COPY --chown=appuser:appuser models/ ./models/

USER appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# O health check consulta /health, que reporta se o modelo esta em memoria.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
