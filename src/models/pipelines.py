"""Pipeline builders for the candidate models.

Every candidate is a ``TfidfVectorizer`` followed by a classifier, wrapped in
a single ``Pipeline``. Keeping the vectoriser inside the pipeline is what
prevents leakage: it is fitted on the training fold only, never on the whole
dataset.

Adding a new candidate means adding one entry to ``CANDIDATES`` -- the
notebooks and the comparison stage pick it up without further changes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from src.config import load_config


def build_vectorizer() -> TfidfVectorizer:
    """Creates the shared TF-IDF vectoriser.

    Identical across every candidate so that differences in the comparison
    come from the classifier, not from the text representation.

    Returns:
        The configured vectoriser.
    """
    params = load_config()["vectorizer"]
    return TfidfVectorizer(
        max_features=int(params["max_features"]),
        ngram_range=tuple(params["ngram_range"]),
        min_df=int(params["min_df"]),
        sublinear_tf=bool(params["sublinear_tf"]),
        strip_accents="unicode",
        lowercase=True,
    )


def build_pipeline(estimator: Any) -> Pipeline:
    """Wraps an estimator together with the TF-IDF vectoriser.

    Args:
        estimator: Any scikit-learn classifier.

    Returns:
        A fitted-ready pipeline.
    """
    return Pipeline([("tfidf", build_vectorizer()), ("clf", estimator)])


def _logreg(seed: int, **params: Any) -> LogisticRegression:
    return LogisticRegression(random_state=seed, **params)


def _random_forest(seed: int, **params: Any) -> RandomForestClassifier:
    return RandomForestClassifier(random_state=seed, n_jobs=-1, **params)


def _linear_svc(seed: int, **params: Any) -> LinearSVC:
    return LinearSVC(random_state=seed, **params)


def _dummy_stratified(seed: int, **_: Any) -> DummyClassifier:
    return DummyClassifier(strategy="stratified", random_state=seed)


def _dummy_most_frequent(seed: int, **_: Any) -> DummyClassifier:
    return DummyClassifier(strategy="most_frequent")


# name -> (estimator factory, config key under `models`, is_baseline)
CANDIDATES: dict[str, tuple[Callable[..., Any], str | None, bool]] = {
    "dummy_most_frequent": (_dummy_most_frequent, None, True),
    "dummy_stratified": (_dummy_stratified, None, True),
    "tfidf_logreg": (_logreg, "logreg", False),
    "tfidf_random_forest": (_random_forest, "random_forest", False),
    "tfidf_linear_svc": (_linear_svc, "linear_svc", False),
}


def param_grid(candidate: str) -> list[dict[str, Any]]:
    """Expands the configured hyperparameter grid for one candidate.

    Args:
        candidate: Key in ``CANDIDATES``.

    Returns:
        List of parameter dicts; a single empty dict for baselines, which
        have nothing to tune.
    """
    from itertools import product

    _, config_key, _ = CANDIDATES[candidate]
    if config_key is None:
        return [{}]

    grid = load_config()["models"][config_key]
    keys = list(grid)
    return [dict(zip(keys, values)) for values in product(*(grid[k] for k in keys))]


def build_candidate(candidate: str, seed: int, **params: Any) -> Pipeline:
    """Builds the full pipeline for one candidate.

    Args:
        candidate: Key in ``CANDIDATES``.
        seed: Random seed applied to the estimator.
        **params: Hyperparameters for the estimator.

    Returns:
        The assembled pipeline.
    """
    factory, _, _ = CANDIDATES[candidate]
    return build_pipeline(factory(seed, **params))
