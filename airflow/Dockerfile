# Imagem do Airflow com as dependencias de treino do projeto.
#
# O Airflow NAO entra no pyproject.toml: ele traz centenas de dependencias com
# versoes proprias e conflitaria com as da API. Fica isolado nesta imagem.
#
# Build a partir da raiz do repositorio (o compose ja faz isso):
#   docker compose -f airflow/docker-compose.yml build

ARG AIRFLOW_VERSION=3.3.1

# 1) Extrai do uv.lock as versoes exatas das bibliotecas de treino.
FROM python:3.12-slim AS requirements

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /src
COPY pyproject.toml uv.lock ./

# Apenas o que o pipeline de treino/exportacao importa. fastapi, uvicorn e
# pydantic ficam de fora: o proprio Airflow depende deles e trocar suas versoes
# quebraria o api-server.
#
# As versoes vem do lock, e nao de um range, por um motivo concreto: o modelo
# e serializado com pickle. Um scikit-learn diferente do da API geraria um
# artefato que a API nao carrega, ou carrega com comportamento diferente.
RUN uv export --frozen --group onnx --no-dev --no-emit-project --no-hashes \
        --no-annotate --no-header \
    | grep -E '^(flatbuffers|joblib|ml-dtypes|numpy|onnx|onnxruntime|packaging|pandas|protobuf|pyarrow|pyyaml|scikit-learn|scipy|skl2onnx|threadpoolctl)==' \
    > requirements-train.txt \
    && cat requirements-train.txt \
    && test "$(wc -l < requirements-train.txt)" -eq 15


# 2) Airflow + dependencias de treino.
FROM apache/airflow:slim-${AIRFLOW_VERSION}-python3.12

COPY --from=requirements /src/requirements-train.txt /tmp/requirements-train.txt

# Os pacotes do Airflow ja instalados viram restricao: a instalacao das libs de
# treino nao pode, em hipotese nenhuma, trocar a versao do proprio Airflow.
RUN pip freeze | grep -i '^apache-airflow' > /tmp/airflow-pins.txt \
    && pip install --no-cache-dir \
        -r /tmp/requirements-train.txt \
        -c /tmp/airflow-pins.txt

# src/, configs/, data/ e models/ sao montados em /opt/airflow/project pelo
# compose. src/config.py resolve os caminhos a partir da propria localizacao,
# entao data/ e models/ sao encontrados ali sem configuracao extra.
ENV PYTHONPATH=/opt/airflow/project
