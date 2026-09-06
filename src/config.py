"""Project paths and configuration loading.

Single entry point for anything a notebook or pipeline stage needs to know
about where files live and which hyperparameters to use. Notebooks import
from here instead of hardcoding paths, so moving a directory is a one-line
change.
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = PROJECT_ROOT / "configs" / "model_config.yaml"
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
EVALUATION_DIR = MODELS_DIR / "evaluation"
NOTEBOOK_OUTPUTS = PROJECT_ROOT / "notebooks" / "outputs"


@lru_cache(maxsize=1)
def load_config(path: Path | None = None) -> dict[str, Any]:
    """Reads ``configs/model_config.yaml``.

    Args:
        path: Optional override, used by tests.

    Returns:
        The parsed configuration mapping.
    """
    config_path = path or CONFIG_PATH
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def set_seed(seed: int | None = None) -> int:
    """Fixes the seeds that affect scikit-learn and numpy.

    Args:
        seed: Seed value; falls back to the one in the config file.

    Returns:
        The seed that was applied.
    """
    resolved = seed if seed is not None else int(load_config()["seed"])
    random.seed(resolved)
    np.random.seed(resolved)
    return resolved


def ensure_dirs() -> None:
    """Creates the output directories the pipeline writes to."""
    for directory in (DATA_PROCESSED, MODELS_DIR, EVALUATION_DIR, NOTEBOOK_OUTPUTS):
        directory.mkdir(parents=True, exist_ok=True)
