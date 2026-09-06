"""Reading the raw corpus and the processed splits.

The raw side is tolerant on purpose: the corpus is downloaded by hand, and
small differences in column naming between mirrors should not break the
notebooks. The processed side is strict -- everything downstream depends on
the ``texto``/``urgencia`` schema documented in docs/DATASET.md.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from src.config import DATA_PROCESSED, DATA_RAW, load_config

DATASET_URL = "https://www.kaggle.com/datasets/saharalaa/medical-abstracts-tc-corpus"

TEXT_COLUMN = "texto"
LABEL_COLUMN = "urgencia"

_TEXT_CANDIDATES = ("medical_abstract", "abstract", "text", "texto")
_LABEL_CANDIDATES = ("condition_label", "label", "target", "class")


class RawDataNotFoundError(FileNotFoundError):
    """Raised when no raw corpus file is present in ``data/raw``."""


def _resolve_column(frame: pd.DataFrame, configured: str, candidates: tuple) -> str:
    """Finds a column by configured name, falling back to known aliases.

    Args:
        frame: The dataframe to inspect.
        configured: Column name from the config file.
        candidates: Known alternative names, tried in order.

    Returns:
        The matching column name.

    Raises:
        KeyError: If neither the configured name nor any alias is present.
    """
    if configured in frame.columns:
        return configured
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    raise KeyError(
        f"Nenhuma coluna encontrada entre {(configured, *candidates)}. "
        f"Colunas disponiveis: {list(frame.columns)}"
    )


def raw_files_present() -> tuple[list[str], list[str]]:
    """Lists which configured raw files exist and which are missing.

    ``load_raw`` concatenates whatever it finds. Running with a subset of the
    corpus therefore produces different splits and different metrics -- with no
    error. Surfacing the file list is what keeps that difference visible.

    Returns:
        Tuple of (present filenames, missing filenames).
    """
    configured = load_config()["data"]["raw_files"]
    present = [name for name in configured if (DATA_RAW / name).exists()]
    missing = [name for name in configured if name not in present]
    return present, missing


def load_raw() -> pd.DataFrame:
    """Loads and concatenates every configured raw CSV.

    Returns:
        Dataframe with the original text and label columns renamed to
        ``texto`` and ``categoria_original``.

    Raises:
        RawDataNotFoundError: If none of the configured files exist.
    """
    config = load_config()
    data_config = config["data"]

    frames = []
    for filename in data_config["raw_files"]:
        path = DATA_RAW / filename
        if path.exists():
            frames.append(pd.read_csv(path))

    if not frames:
        expected = ", ".join(data_config["raw_files"])
        raise RawDataNotFoundError(
            f"Nenhum arquivo bruto encontrado em {DATA_RAW}.\n"
            f"Esperado um destes: {expected}\n"
            f"Baixe o corpus em {DATASET_URL}\n"
            "e extraia os CSVs em data/raw/ (ver docs/DATASET.md)."
        )

    raw = pd.concat(frames, ignore_index=True)
    text_col = _resolve_column(raw, data_config["raw_text_column"], _TEXT_CANDIDATES)
    label_col = _resolve_column(raw, data_config["raw_label_column"], _LABEL_CANDIDATES)

    return raw.rename(columns={text_col: TEXT_COLUMN, label_col: "categoria_original"})[
        [TEXT_COLUMN, "categoria_original"]
    ]


def load_split(name: str) -> pd.DataFrame:
    """Reads one processed split.

    Args:
        name: One of ``train``, ``val`` or ``test``.

    Returns:
        Dataframe with the ``texto`` and ``urgencia`` columns.
    """
    path = DATA_PROCESSED / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Split '{name}' nao encontrado em {path}. "
            "Rode o notebook 02_preprocessing.ipynb primeiro."
        )
    return pd.read_parquet(path)


def load_all_splits() -> dict[str, pd.DataFrame]:
    """Reads train, validation and test splits at once.

    Returns:
        Mapping of split name to dataframe.
    """
    return {name: load_split(name) for name in ("train", "val", "test")}


def dataset_hash(path: Path) -> str:
    """Computes the SHA256 of a file, for reproducibility records.

    Args:
        path: File to hash.

    Returns:
        Hex digest of the file contents.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
