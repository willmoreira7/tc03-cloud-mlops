"""Generates a synthetic corpus with the same shape as the real one.

Two uses, both scaffolding:

1. Letting the notebooks and the pipeline run end to end before the real
   corpus has been downloaded.
2. Giving CI a dataset it can use without versioning real data.

It is NOT a substitute for the real corpus in the final delivery: the
requirement is a public dataset with at least 2,000 samples. Numbers produced
from synthetic data say nothing about real model quality.

Usage:
    python scripts/gen_synthetic_data.py [--rows 3000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allows running the script directly (`python scripts/gen_synthetic_data.py`)
# without requiring the project to be installed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import DATA_RAW, load_config  # noqa: E402

# Vocabulary skewed per category so that a classifier has real signal to find,
# with deliberate overlap so the task is not trivially separable.
_VOCAB: dict[str, list[str]] = {
    "1": ["massa", "lesao", "nodulo", "neoplasia", "biopsia", "celulas", "tumoral"],
    "2": ["gastrico", "hepatico", "intestinal", "endoscopia", "mucosa", "abdominal"],
    "3": ["neurologico", "cefaleia", "convulsao", "cerebral", "cognitivo", "motor"],
    "4": ["cardiaco", "isquemia", "arritmia", "coronariano", "infarto", "ventricular"],
    "5": ["inflamatorio", "febril", "cronico", "sistemico", "edema", "infeccioso"],
}

_FILLER = [
    "paciente",
    "exame",
    "achado",
    "quadro",
    "avaliacao",
    "controle",
    "aspecto",
    "regiao",
    "evolucao",
    "sinais",
    "ausencia",
    "presenca",
]


def _document(rng: np.random.Generator, category: str) -> str:
    """Builds one synthetic report for a category.

    Categories share vocabulary on purpose. With disjoint word sets any
    classifier scores a perfect F1, which makes the stand-in useless: it would
    hide regressions in CI and give a falsely reassuring picture of the
    pipeline. The overlap below keeps the task learnable but not trivial.

    Args:
        rng: Seeded random generator.
        category: Corpus category key.

    Returns:
        The generated text.
    """
    others = [key for key in _VOCAB if key != category]
    borrowed_pool = [word for key in others for word in _VOCAB[key]]

    n_specific = int(rng.integers(4, 9))
    n_borrowed = int(rng.integers(3, 8))
    n_filler = int(rng.integers(25, 50))

    words = list(rng.choice(_VOCAB[category], size=n_specific))
    words += list(rng.choice(borrowed_pool, size=n_borrowed))
    words += list(rng.choice(_FILLER, size=n_filler))
    rng.shuffle(words)
    return " ".join(words)


def generate(rows: int, seed: int) -> pd.DataFrame:
    """Generates the synthetic dataframe.

    Args:
        rows: Number of documents.
        seed: Random seed.

    Returns:
        Dataframe with the raw corpus columns.
    """
    rng = np.random.default_rng(seed)
    categories = list(_VOCAB)
    # Uneven on purpose: the real target is imbalanced, and a balanced stand-in
    # would hide exactly the problem the macro-F1 criterion exists to catch.
    weights = np.array([0.22, 0.20, 0.18, 0.15, 0.25])

    drawn = rng.choice(categories, size=rows, p=weights)
    return pd.DataFrame(
        {
            "medical_abstract": [_document(rng, category) for category in drawn],
            "condition_label": drawn,
        }
    )


def main() -> None:
    """Writes the synthetic corpus to ``data/raw``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=3000)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve o arquivo mesmo que ja exista.",
    )
    args = parser.parse_args()

    config = load_config()
    seed = int(config["seed"])
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    target = DATA_RAW / config["data"]["raw_files"][0]
    # O corpus real e baixado manualmente para o mesmo caminho. Sobrescreve-lo
    # em silencio destruiria o download e faria os notebooks rodarem sobre dados
    # sinteticos sem ninguem perceber.
    if target.exists() and not args.force:
        print(f"ABORTADO: {target} ja existe.")
        print("Use --force para sobrescrever (isso apaga o corpus real baixado).")
        raise SystemExit(1)

    frame = generate(args.rows, seed)
    frame.to_csv(target, index=False)

    print(f"Corpus sintetico gerado: {target} ({len(frame)} linhas)")
    print(frame["condition_label"].value_counts().sort_index().to_string())
    print("\nATENCAO: dados sinteticos. Nao substituem o corpus real na entrega.")


if __name__ == "__main__":
    main()
