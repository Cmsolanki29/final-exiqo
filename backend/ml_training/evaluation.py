"""Supervised model evaluation metrics for fraud detection.

Phase 3: Supervised Model Layer.
Dependencies: scikit-learn, numpy, xgboost.
Performance budget: evaluate_model() < 5s for 100k rows.

Why these metrics?
  ROC-AUC misleads under extreme class imbalance — a model that predicts
  "all legitimate" scores ~0.99 ROC-AUC on 0.1% fraud data.  PR-AUC
  (Precision-Recall AUC) is immune because it focuses on the positive class.
  Recall@FPR is what fraud ops teams care about: "what fraction of fraud
  do we catch if we can only tolerate N false alarms per 1000 transactions?"
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.metrics import (
    auc,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

logger = logging.getLogger(__name__)


def evaluate_model(
    model: Any,
    X_test: Any,
    y_test: Any,
) -> dict[str, float | list | None]:
    """Compute production-grade evaluation metrics for a fraud classifier.

    All metrics are computed on a held-out test set.  These numbers feed
    MLflow (Phase 5) and the shadow evaluation pipeline (Phase 5).

    Args:
        model:  Fitted scikit-learn–compatible classifier with predict_proba.
        X_test: Test feature matrix (DataFrame or ndarray).
        y_test: Binary label array (1 = fraud).

    Returns:
        Dict with keys:
          pr_auc               — Primary metric. AUC of precision-recall curve.
          roc_auc              — Secondary metric. AUC of ROC curve.
          recall_at_1pct_fpr   — Recall when FPR = 0.01 (1 false alarm per 100 legit txns).
          recall_at_5pct_fpr   — Recall when FPR = 0.05.
          precision_at_80_recall — Precision achieved at ≥80% recall.
          precision_at_50_recall — Precision achieved at ≥50% recall.
          confusion_matrix_at_best_f1 — [[TN, FP], [FN, TP]] at the threshold maximising F1.
          n_test               — Test set size.
          n_fraud_test         — Fraud count in test set.
          threshold_best_f1    — Decision threshold at best F1.
    """
    y_test = np.asarray(y_test, dtype=float)
    n_total = len(y_test)
    n_fraud = int(y_test.sum())

    if n_fraud == 0:
        logger.warning("evaluate_model: no fraud samples in test set — metrics will be degenerate")
        return _degenerate_metrics(n_total, n_fraud)

    if n_total - n_fraud == 0:
        logger.warning("evaluate_model: no legitimate samples in test set — metrics will be degenerate")
        return _degenerate_metrics(n_total, n_fraud)

    # ---- Predicted probabilities ---- #
    try:
        y_proba = model.predict_proba(X_test)[:, 1]
    except Exception as exc:
        logger.exception("evaluate_model: predict_proba failed: %s", exc)
        return _degenerate_metrics(n_total, n_fraud)

    # ---- PR-AUC ---- #
    precision_arr, recall_arr, pr_thresholds = precision_recall_curve(y_test, y_proba)
    pr_auc_val = float(auc(recall_arr, precision_arr))

    # ---- ROC-AUC ---- #
    try:
        roc_auc_val = float(roc_auc_score(y_test, y_proba))
        fpr_arr, tpr_arr, roc_thresholds = roc_curve(y_test, y_proba)
    except Exception:
        roc_auc_val = 0.0
        fpr_arr, tpr_arr = np.array([0.0, 1.0]), np.array([0.0, 1.0])

    # ---- Recall at FPR targets ---- #
    recall_at_1pct_fpr = _recall_at_fpr(fpr_arr, tpr_arr, target_fpr=0.01)
    recall_at_5pct_fpr = _recall_at_fpr(fpr_arr, tpr_arr, target_fpr=0.05)

    # ---- Precision at recall targets ---- #
    precision_at_80_recall = _precision_at_recall(precision_arr, recall_arr, target_recall=0.80)
    precision_at_50_recall = _precision_at_recall(precision_arr, recall_arr, target_recall=0.50)

    # ---- Best-F1 threshold ---- #
    f1_scores = _compute_f1(precision_arr[:-1], recall_arr[:-1])
    if len(f1_scores) > 0:
        best_f1_idx = int(np.argmax(f1_scores))
        best_threshold = float(pr_thresholds[best_f1_idx]) if best_f1_idx < len(pr_thresholds) else 0.5
        y_pred_best = (y_proba >= best_threshold).astype(int)
        cm = confusion_matrix(y_test.astype(int), y_pred_best).tolist()
    else:
        best_threshold = 0.5
        cm = None

    metrics = {
        "pr_auc": round(pr_auc_val, 4),
        "roc_auc": round(roc_auc_val, 4),
        "recall_at_1pct_fpr": round(recall_at_1pct_fpr, 4),
        "recall_at_5pct_fpr": round(recall_at_5pct_fpr, 4),
        "precision_at_80_recall": round(precision_at_80_recall, 4),
        "precision_at_50_recall": round(precision_at_50_recall, 4),
        "confusion_matrix_at_best_f1": cm,
        "threshold_best_f1": round(best_threshold, 4),
        "n_test": float(n_total),
        "n_fraud_test": float(n_fraud),
    }

    logger.info(
        "evaluate_model: pr_auc=%.4f roc_auc=%.4f recall@1%%fpr=%.4f n=%d",
        metrics["pr_auc"], metrics["roc_auc"], metrics["recall_at_1pct_fpr"], n_total,
    )
    return metrics


def _recall_at_fpr(
    fpr_arr: np.ndarray,
    tpr_arr: np.ndarray,
    target_fpr: float,
) -> float:
    """Return TPR (recall) at the operating point closest to target_fpr."""
    if len(fpr_arr) == 0:
        return 0.0
    idx = np.searchsorted(fpr_arr, target_fpr, side="right")
    idx = min(idx, len(tpr_arr) - 1)
    return float(tpr_arr[idx])


def _precision_at_recall(
    precision_arr: np.ndarray,
    recall_arr: np.ndarray,
    target_recall: float,
) -> float:
    """Return precision at the operating point where recall >= target_recall."""
    mask = recall_arr >= target_recall
    if not mask.any():
        return 0.0
    return float(precision_arr[mask][-1])


def _compute_f1(precision: np.ndarray, recall: np.ndarray) -> np.ndarray:
    """Element-wise F1 from aligned precision and recall arrays."""
    denom = precision + recall
    denom = np.where(denom == 0, 1e-10, denom)
    return 2 * precision * recall / denom


def _degenerate_metrics(n_total: int, n_fraud: int) -> dict:
    """Return a zero-filled metrics dict for degenerate test sets."""
    return {
        "pr_auc": 0.0,
        "roc_auc": 0.0,
        "recall_at_1pct_fpr": 0.0,
        "recall_at_5pct_fpr": 0.0,
        "precision_at_80_recall": 0.0,
        "precision_at_50_recall": 0.0,
        "confusion_matrix_at_best_f1": None,
        "threshold_best_f1": 0.5,
        "n_test": float(n_total),
        "n_fraud_test": float(n_fraud),
    }
