"""Trains the model the API serves, in one command.

Exists so that the container is buildable from a fresh clone. The notebooks
are the record of the analysis, not a build step: nobody should have to run
seven notebooks to get a working service.

Runs the same stages as the Airflow retraining DAG, in the same order, by
calling ``src/pipeline/stages.py``. The model is trained into a staging
directory and only published to ``models/`` if it passes the quality gate.

Usage:
    python scripts/train_serving_model.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loader import RawDataNotFoundError  # noqa: E402
from src.pipeline import stages  # noqa: E402


def main() -> None:
    """Runs ingest, preprocessing, training, quality gate and publishing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-preprocess",
        action="store_true",
        help="Reaproveita os splits ja existentes em data/processed.",
    )
    args = parser.parse_args()

    run_id = stages.new_run_id()
    print(f"Run: {run_id}\n")

    try:
        ingest = stages.ingest_data()
    except RawDataNotFoundError as erro:
        print(erro)
        print(
            "\nPara apenas validar a stack, gere um substituto sintetico:\n"
            "  uv run python scripts/gen_synthetic_data.py --rows 3000\n"
            "As metricas resultantes nao reproduzem as documentadas."
        )
        raise SystemExit(1) from erro

    print(f"[1/5] ingest       arquivos: {', '.join(ingest['arquivos'])}")
    if ingest["ausentes"]:
        print(
            f"      AVISO: ausentes {', '.join(ingest['ausentes'])} - as metricas "
            "vao diferir de uma execucao com o corpus completo."
        )

    if args.skip_preprocess:
        print("[2/5] preprocess   pulado (--skip-preprocess)")
    else:
        prep = stages.preprocess_data()
        print(
            f"[2/5] preprocess   {prep['documentos_brutos']:,} brutos -> "
            f"{prep['documentos_limpos']:,} limpos | splits {prep['splits']}"
        )

    treino = stages.train_model(run_id)
    metricas = treino["test_metrics"]
    print(f"[3/5] train        {treino['candidato']} | {treino['best_params']}")
    print(f"      f1_macro:       {metricas['f1_macro']:.4f}")
    print(f"      recall_urgente: {metricas['recall_urgente']:.4f}")
    print(f"      p95:            {treino['latency']['latency_p95_ms']:.2f} ms")

    try:
        stages.evaluate_model(treino["diretorio"])
    except stages.QualityGateError as erro:
        print(f"[4/5] evaluate     REPROVADO\n\n{erro}")
        raise SystemExit(1) from erro
    print("[4/5] evaluate     aprovado no quality gate")

    publicado = stages.publish_model(treino["diretorio"], ingest)
    print(f"[5/5] publish      {publicado['diretorio']}")
    print("\nA imagem Docker ja pode ser construida.")


if __name__ == "__main__":
    main()
