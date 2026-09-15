"""Retreino agendado do modelo de triagem de laudos.

```
ingest_data -> preprocess_data -> train_model -> evaluate_model -> publish_model
```

| Task | O que faz |
|------|-----------|
| `ingest_data` | Confere que o corpus bruto existe e calcula o SHA256 de cada arquivo |
| `preprocess_data` | Mapeia urgencia, limpa e grava os splits em parquet |
| `train_model` | Treina o modelo servido em `models/_staging/<run_id>/` |
| `evaluate_model` | **Quality gate**: criterio de promocao; reprova sem retry |
| `publish_model` | Move o artefato aprovado para `models/<modelo>/`, onde a API le |

Cada task apenas chama `src/pipeline/stages.py` -- a mesma funcao que o
`scripts/train_serving_model.py` usa. A DAG nao tem logica de pipeline propria.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from airflow.sdk import dag, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException

# Os imports de src/ ficam dentro das tasks. O dag-processor reinterpreta este
# arquivo periodicamente; importar scikit-learn e pandas no topo tornaria cada
# parse lento sem nenhum ganho.


@dag(
    dag_id="retreino_triagem",
    description="Retreino do classificador de urgencia de laudos",
    schedule="@weekly",
    start_date=datetime(2026, 9, 1, tzinfo=UTC),
    catchup=False,
    # Duas execucoes simultaneas disputariam data/processed e o publish.
    max_active_runs=1,
    default_args={
        "owner": "mlops",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["mlops", "retreino", "tc03"],
    doc_md=__doc__,
)
def retreino_triagem() -> None:
    @task
    def ingest_data() -> dict[str, Any]:
        from src.pipeline import stages

        return stages.ingest_data()

    @task
    def preprocess_data(ingest: dict[str, Any]) -> dict[str, Any]:
        from src.pipeline import stages

        return stages.preprocess_data()

    @task
    def train_model(preprocess: dict[str, Any]) -> dict[str, Any]:
        from src.pipeline import stages

        run_id = get_current_context()["run_id"]
        return stages.train_model(run_id)

    @task
    def evaluate_model(train: dict[str, Any]) -> dict[str, Any]:
        from src.pipeline import stages

        try:
            return stages.evaluate_model(train["diretorio"])
        except stages.QualityGateError as erro:
            # Retreinar sobre os mesmos dados daria o mesmo modelo reprovado:
            # AirflowFailException encerra a task sem consumir os retries.
            raise AirflowFailException(str(erro)) from erro

    @task
    def publish_model(
        evaluation: dict[str, Any], ingest: dict[str, Any]
    ) -> dict[str, Any]:
        from src.pipeline import stages

        return stages.publish_model(evaluation["diretorio"], ingest)

    ingest = ingest_data()
    preprocess = preprocess_data(ingest)
    train = train_model(preprocess)
    evaluation = evaluate_model(train)
    publish_model(evaluation, ingest)


retreino_triagem()
