"""Trains the model the API serves, in one command.

Exists so that the container is buildable from a fresh clone. The notebooks
are the record of the analysis, not a build step: nobody should have to run
seven notebooks to get a working service.

The stages are the same ones the notebooks call, in the same order, so this
script and the analysis cannot drift apart. It is also the natural body of the
Airflow retraining DAG.

Usage:
    python scripts/train_serving_model.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import DATA_PROCESSED, ensure_dirs, load_config, set_seed  # noqa: E402
from src.data.loader import (  # noqa: E402
    RawDataNotFoundError,
    load_raw,
    raw_files_present,
)
from src.data.preprocessing import (  # noqa: E402
    class_distribution,
    drop_degenerate,
    make_splits,
    map_urgency,
)
from src.models.experiment import run_candidate  # noqa: E402


def preparar_dados() -> None:
    """Builds the train/val/test splits from the raw corpus."""
    presentes, ausentes = raw_files_present()
    print(f"Arquivos brutos usados:  {', '.join(presentes)}")
    if ausentes:
        print(
            f"AVISO: ausentes {', '.join(ausentes)} - as metricas vao diferir "
            "de uma execucao com o corpus completo."
        )

    raw = load_raw()
    print(f"Documentos brutos:      {len(raw):,}")

    mapeado = map_urgency(raw)
    limpo = drop_degenerate(mapeado)
    print(f"Apos limpeza:           {len(limpo):,}")
    print(class_distribution(limpo).to_string())

    splits = make_splits(limpo)
    for nome, frame in splits.items():
        frame.to_parquet(DATA_PROCESSED / f"{nome}.parquet", index=False)
        print(f"  {nome:6s} -> {len(frame):,}")


def main() -> None:
    """Runs preprocessing and trains the served model."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-preprocess",
        action="store_true",
        help="Reaproveita os splits ja existentes em data/processed.",
    )
    args = parser.parse_args()

    ensure_dirs()
    seed = set_seed()
    candidato = load_config()["serving"]["model"]
    print(f"Modelo servido: {candidato} | seed={seed}\n")

    if not args.skip_preprocess:
        try:
            preparar_dados()
        except RawDataNotFoundError as erro:
            print(erro)
            print(
                "\nSem o corpus, gere um substituto sintetico:\n"
                "  python scripts/gen_synthetic_data.py --rows 3000"
            )
            raise SystemExit(1) from erro

    print(f"\nTreinando {candidato}...")
    resultado = run_candidate(candidato)

    metricas = resultado["test_metrics"]
    print(f"\nParametros: {resultado['best_params']}")
    print(f"f1_macro:       {metricas['f1_macro']:.4f}")
    print(f"recall_urgente: {metricas['recall_urgente']:.4f}")
    print(f"p95:            {resultado['latency']['latency_p95_ms']:.2f} ms")
    print(f"\nArtefato: {resultado['output_dir'] / 'model.pkl'}")
    print("A imagem Docker ja pode ser construida.")


if __name__ == "__main__":
    main()
