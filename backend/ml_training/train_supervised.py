"""Supervised XGBoost model training pipeline.

Phase 3: Supervised Model Layer.
Dependencies: xgboost, scikit-learn, pandas, numpy.
Performance budget: training < 5 min on 500k rows; inference < 10ms per call.

Design decisions:
  - Time-based split (NOT random) to respect temporal ordering.
    Random split leaks future aggregate features into training, inflating metrics.
  - scale_pos_weight handles severe class imbalance (0.1–1% fraud rate).
  - eval_metric='aucpr' optimises for PR-AUC, which is more meaningful than
    ROC-AUC under extreme imbalance.
  - early_stopping_rounds prevents overfitting to minority class noise.
  - tree_method='hist' is the fastest CPU method; GPU uses 'gpu_hist'.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit

from ml_training.feature_engineering import SUPERVISED_FEATURE_COLUMNS

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Default hyper-parameters (can be overridden via config / HPO)
# ------------------------------------------------------------------ #
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "eval_metric": "aucpr",
    "early_stopping_rounds": 20,
    "tree_method": "hist",
    "use_label_encoder": False,
    "random_state": 42,
    "verbosity": 0,
}


def train_xgboost_model(
    X: pd.DataFrame,
    y: pd.Series,
    params: dict[str, Any] | None = None,
    n_splits: int = 3,
) -> tuple[xgb.XGBClassifier, dict[str, float]]:
    """Train an XGBoost fraud classifier using time-based cross-validation.

    Uses the LAST fold of TimeSeriesSplit as the validation set for early
    stopping.  This mirrors how the model will be evaluated in production:
    trained on past, validated on future.

    Args:
        X:        Feature DataFrame with SUPERVISED_FEATURE_COLUMNS columns.
        y:        Binary label Series (1 = fraud, 0 = legitimate).
        params:   XGBClassifier kwargs; merged over DEFAULT_PARAMS.
        n_splits: Number of TimeSeriesSplit folds (last used for validation).

    Returns:
        (model, metrics): Trained classifier and training metrics dict.

    Raises:
        ValueError: If there are too few positive samples to train.
    """
    if len(X) == 0 or len(y) == 0:
        raise ValueError("Training data is empty — cannot train XGBoost model")

    n_fraud = int(y.sum())
    n_legit = int((~y.astype(bool)).sum())
    logger.info("train_xgboost: n_total=%d n_fraud=%d n_legit=%d", len(y), n_fraud, n_legit)

    if n_fraud < 5:
        raise ValueError(
            f"Too few fraud samples ({n_fraud}) to train supervised model. "
            "Run bootstrap or wait for more labels."
        )

    # ---- Time-based split (last fold → val, rest → train) ---- #
    tscv = TimeSeriesSplit(n_splits=n_splits)
    splits = list(tscv.split(X))
    train_idx, val_idx = splits[-1]

    X_train = X.iloc[train_idx]
    y_train = y.iloc[train_idx]
    X_val = X.iloc[val_idx]
    y_val = y.iloc[val_idx]

    logger.info(
        "train_xgboost: train=%d val=%d (train_fraud=%d val_fraud=%d)",
        len(X_train), len(X_val), int(y_train.sum()), int(y_val.sum()),
    )

    # ---- Class balance ---- #
    n_neg_train = int((~y_train.astype(bool)).sum())
    n_pos_train = max(int(y_train.sum()), 1)
    scale_pos_weight = n_neg_train / n_pos_train
    logger.info("train_xgboost: scale_pos_weight=%.2f", scale_pos_weight)

    # ---- Build params ---- #
    final_params = {**DEFAULT_PARAMS, **(params or {})}
    final_params["scale_pos_weight"] = scale_pos_weight

    # ---- Train ---- #
    model = xgb.XGBClassifier(**final_params)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # ---- Collect training metrics ---- #
    best_iteration = getattr(model, "best_iteration", model.n_estimators)
    try:
        evals = model.evals_result()
        val_aucpr = evals.get("validation_0", {}).get("aucpr", [None])[-1]
    except Exception:
        val_aucpr = None

    metrics: dict[str, float] = {
        "best_iteration": float(best_iteration or 0),
        "train_size": float(len(X_train)),
        "val_size": float(len(X_val)),
        "n_fraud_train": float(n_pos_train),
        "scale_pos_weight": float(scale_pos_weight),
    }
    if val_aucpr is not None:
        metrics["val_aucpr"] = float(val_aucpr)

    logger.info("train_xgboost: done — best_iter=%s val_aucpr=%s", best_iteration, val_aucpr)
    return model, metrics


def save_model(model: xgb.XGBClassifier, path: str | Path) -> None:
    """Persist a trained XGBClassifier to disk as a pickle.

    Uses pickle so feature metadata (column names) travels with the model.
    For Phase 5 (MLflow), we will use mlflow.xgboost.log_model instead.

    Args:
        model: Trained XGBClassifier.
        path:  Output file path (.pkl).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    logger.info("save_model: saved to %s", path)


def load_model(path: str | Path) -> xgb.XGBClassifier | None:
    """Load an XGBClassifier from disk.

    Returns None if the file does not exist (graceful degradation — system
    will fall back to unsupervised-only scoring).

    Args:
        path: Path to the .pkl file.

    Returns:
        XGBClassifier or None.
    """
    path = Path(path)
    if not path.exists():
        logger.info("load_model: no model file at %s — will use unsup-only scoring", path)
        return None
    try:
        with open(path, "rb") as f:
            model = pickle.load(f)
        logger.info("load_model: loaded supervised model from %s", path)
        return model
    except Exception as exc:
        logger.exception("load_model: failed to load from %s: %s", path, exc)
        return None
