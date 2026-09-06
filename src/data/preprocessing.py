"""Text cleaning, urgency mapping and split generation.

Everything here runs exactly once, in ``02_preprocessing.ipynb``. The model
notebooks consume the resulting parquet files and never re-derive a split --
otherwise each model would be measured on different data and the comparison
would be meaningless.
"""

from __future__ import annotations

import re

import pandas as pd
from sklearn.model_selection import train_test_split

from src.config import load_config
from src.data.loader import LABEL_COLUMN, TEXT_COLUMN

_WHITESPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Normalises a single document.

    Deliberately conservative: collapses whitespace and trims. Lowercasing and
    stopword removal are left to the vectoriser so that every model shares the
    same treatment.

    Args:
        text: Raw document.

    Returns:
        The normalised text.
    """
    if not isinstance(text, str):
        return ""
    return _WHITESPACE.sub(" ", text).strip()


def map_urgency(frame: pd.DataFrame) -> pd.DataFrame:
    """Derives the urgency label from the corpus category.

    The mapping is a documented heuristic, not a clinical validation -- see
    docs/DATASET.md. Rows whose category has no mapping are dropped rather
    than silently bucketed into a default class.

    Args:
        frame: Dataframe with a ``categoria_original`` column.

    Returns:
        Dataframe with an added ``urgencia`` column, unmapped rows removed.
    """
    mapping = {str(k): v for k, v in load_config()["urgency_mapping"].items()}
    urgency = frame["categoria_original"].astype(str).str.strip().map(mapping)

    result = frame.assign(**{LABEL_COLUMN: urgency})
    return result[result[LABEL_COLUMN].notna()].reset_index(drop=True)


def drop_degenerate(frame: pd.DataFrame) -> pd.DataFrame:
    """Removes empty, too-short and duplicated documents.

    Args:
        frame: Dataframe with a ``texto`` column.

    Returns:
        The filtered dataframe.
    """
    min_chars = int(load_config()["data"]["min_text_chars"])
    cleaned = frame.assign(**{TEXT_COLUMN: frame[TEXT_COLUMN].map(clean_text)})
    long_enough = cleaned[cleaned[TEXT_COLUMN].str.len() >= min_chars]
    return long_enough.drop_duplicates(subset=[TEXT_COLUMN]).reset_index(drop=True)


def make_splits(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Splits into train/validation/test, stratified by urgency.

    Args:
        frame: Dataframe with ``texto`` and ``urgencia`` columns.

    Returns:
        Mapping of split name to dataframe.
    """
    config = load_config()
    split_config = config["split"]
    seed = int(config["seed"])
    stratify_col = frame[LABEL_COLUMN] if split_config["stratify"] else None

    holdout_size = split_config["val_ratio"] + split_config["test_ratio"]
    train, holdout = train_test_split(
        frame,
        test_size=holdout_size,
        random_state=seed,
        stratify=stratify_col,
    )

    # Within the holdout, val and test must keep their configured proportion.
    test_share = split_config["test_ratio"] / holdout_size
    holdout_stratify = holdout[LABEL_COLUMN] if split_config["stratify"] else None
    val, test = train_test_split(
        holdout,
        test_size=test_share,
        random_state=seed,
        stratify=holdout_stratify,
    )

    return {
        "train": train.reset_index(drop=True),
        "val": val.reset_index(drop=True),
        "test": test.reset_index(drop=True),
    }


def class_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Summarises how many documents each urgency class holds.

    Args:
        frame: Dataframe with an ``urgencia`` column.

    Returns:
        Dataframe with absolute counts and proportions per class.
    """
    counts = frame[LABEL_COLUMN].value_counts()
    return pd.DataFrame(
        {"n": counts, "proporcao": (counts / counts.sum()).round(4)}
    ).sort_index()
