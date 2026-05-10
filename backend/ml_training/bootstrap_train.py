"""Bootstrap script — train the initial XGBoost model using synthetic fraud.

Phase 3: Supervised Model Layer.

Why synthetic?
  At launch there are zero real fraud labels.  Synthetic injection creates
  plausible fraud patterns so the supervised layer has something to learn.
  Real labels (Phase 8) will progressively replace synthetic ones during
  weekly retraining (Phase 5).

Usage:
  cd backend
  python -m ml_training.bootstrap_train

  Or with custom model output path:
  python -m ml_training.bootstrap_train --model-path models/supervised_v1.pkl

The script:
  1. Connects to Postgres and pulls all DEBIT transactions.
  2. If the DB is unavailable or has < MIN_ROWS rows, generates pure synthetic data.
  3. Injects synthetic fraud at 0.5%.
  4. Builds feature matrix via build_features_from_df().
  5. Trains XGBoost with time-based split.
  6. Evaluates on the last 20% of rows (held-out test set).
  7. Saves model to SUPERVISED_MODEL_PATH.
  8. Prints metrics summary.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend/ is on sys.path so imports work from any CWD
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from core.config import get_settings
from ml_training.evaluation import evaluate_model
from ml_training.feature_engineering import build_features_from_df
from ml_training.synthetic_data import generate_synthetic_fraud
from ml_training.train_supervised import save_model, train_xgboost_model

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("bootstrap_train")

MIN_ROWS = 100  # Minimum rows needed for meaningful training


def _load_from_db() -> pd.DataFrame | None:
    """Pull DEBIT transactions from Postgres using psycopg2 (synchronous)."""
    try:
        import psycopg2
        settings = get_settings()
        dsn = settings.DATABASE_URL.replace("postgresql://", "postgresql://", 1)
        conn = psycopg2.connect(dsn)
        df = pd.read_sql(
            """
            SELECT id, user_id, amount, merchant, category, payment_method,
                   hour_of_day, day_of_week, is_weekend, balance_after,
                   transaction_date, type
            FROM   transactions
            WHERE  type = 'DEBIT'
            ORDER  BY user_id, transaction_date
            """,
            conn,
        )
        conn.close()
        logger.info("Loaded %d DEBIT transactions from database", len(df))
        return df
    except Exception as exc:
        logger.warning("DB load failed (%s) — will generate fully synthetic data", exc)
        return None


def _generate_synthetic_only(n_rows: int = 5000) -> pd.DataFrame:
    """Generate a fully synthetic transaction dataset (no DB required)."""
    rng = np.random.default_rng(42)
    n_users = max(n_rows // 50, 10)
    user_ids = rng.choice(range(1, n_users + 1), size=n_rows)
    amounts = rng.lognormal(mean=7.5, sigma=1.2, size=n_rows)  # ₹ distribution

    from datetime import date, timedelta
    base_date = date(2025, 1, 1)
    dates = [str(base_date + timedelta(days=int(d))) for d in rng.integers(0, 365, size=n_rows)]
    hours = rng.integers(6, 23, size=n_rows)

    return pd.DataFrame({
        "id": range(1, n_rows + 1),
        "user_id": user_ids,
        "amount": amounts,
        "merchant": rng.choice(["Amazon", "Swiggy", "Zomato", "Flipkart", "DMart", "PayTM"], size=n_rows),
        "category": rng.choice(["Food", "Shopping", "Groceries", "Utilities", "Entertainment"], size=n_rows),
        "payment_method": rng.choice(["UPI", "CARD", "NET_BANKING"], size=n_rows),
        "hour_of_day": hours,
        "day_of_week": rng.integers(0, 7, size=n_rows),
        "is_weekend": rng.choice([True, False], size=n_rows),
        "balance_after": rng.uniform(100, 50000, size=n_rows),
        "transaction_date": dates,
        "type": "DEBIT",
        "is_fraud": False,
        "fraud_label_source": "legitimate",
    })


def run(model_path: str | None = None) -> dict:
    """Execute the full bootstrap training pipeline.

    Returns:
        Dict of evaluation metrics (pr_auc, roc_auc, etc.).
    """
    settings = get_settings()
    output_path = Path(model_path or settings.SUPERVISED_MODEL_PATH)

    logger.info("=== Bootstrap Training — Phase 3 ===")
    logger.info("Output path: %s", output_path)

    # ---- Step 1: Load or generate data ---- #
    df = _load_from_db()
    if df is None or len(df) < MIN_ROWS:
        logger.info("Using fully synthetic data (%d rows)", 5000)
        df = _generate_synthetic_only(n_rows=5000)

    # ---- Step 2: Inject synthetic fraud ---- #
    df_with_fraud = generate_synthetic_fraud(df, fraud_rate=0.005)
    n_fraud = int(df_with_fraud["is_fraud"].sum())
    n_total = len(df_with_fraud)
    logger.info("Dataset: %d rows, %d fraud (%.3f%%)", n_total, n_fraud, n_fraud / n_total * 100)

    # ---- Step 3: Build feature matrix ---- #
    logger.info("Building feature matrix...")
    X, y = build_features_from_df(df_with_fraud)
    logger.info("Feature matrix: X=%s, positives=%d", X.shape, int(y.sum()))

    if int(y.sum()) < 5:
        logger.error("Too few fraud samples after feature engineering — aborting")
        return {"error": "too_few_fraud_samples", "pr_auc": 0.0}

    # ---- Step 4: Time-based split (last 20% for test) ---- #
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    logger.info(
        "Split: train=%d (fraud=%d), test=%d (fraud=%d)",
        len(X_train), int(y_train.sum()), len(X_test), int(y_test.sum()),
    )

    # ---- Step 5: Train ---- #
    logger.info("Training XGBoost...")
    model, train_metrics = train_xgboost_model(X_train, y_train)
    logger.info("Training metrics: %s", train_metrics)

    # ---- Step 6: Evaluate ---- #
    logger.info("Evaluating on held-out test set...")
    eval_metrics = evaluate_model(model, X_test, y_test)

    logger.info("─" * 50)
    logger.info("EVALUATION RESULTS")
    logger.info("  PR-AUC:              %.4f", eval_metrics["pr_auc"])
    logger.info("  ROC-AUC:             %.4f", eval_metrics["roc_auc"])
    logger.info("  Recall@1%%FPR:        %.4f", eval_metrics["recall_at_1pct_fpr"])
    logger.info("  Recall@5%%FPR:        %.4f", eval_metrics["recall_at_5pct_fpr"])
    logger.info("  Precision@80%%Recall: %.4f", eval_metrics["precision_at_80_recall"])
    logger.info("─" * 50)

    # ---- Step 7: Save model ---- #
    save_model(model, output_path)
    logger.info("Model saved → %s", output_path)

    # ---- Step 8: Save metrics JSON sidecar ---- #
    all_metrics = {**train_metrics, **eval_metrics}
    metrics_record = {
        "model_path": str(output_path),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "train_size": int(train_metrics.get("train_size", len(X_train))),
        "val_size": int(train_metrics.get("val_size", len(X_test))),
        "n_fraud_train": int(train_metrics.get("n_fraud_train", int(y_train.sum()))),
        "scale_pos_weight": float(train_metrics.get("scale_pos_weight", 1.0)),
        "best_iteration": int(train_metrics.get("best_iteration", 0)),
        "roc_auc": float(eval_metrics.get("roc_auc", 0.0)),
        "pr_auc": float(eval_metrics.get("pr_auc", 0.0)),
        "val_aucpr": float(train_metrics.get("val_aucpr", 0.0)),
        "recall_at_1pct_fpr": float(eval_metrics.get("recall_at_1pct_fpr", 0.0)),
        "recall_at_5pct_fpr": float(eval_metrics.get("recall_at_5pct_fpr", 0.0)),
        "precision_at_80_recall": float(eval_metrics.get("precision_at_80_recall", 0.0)),
        "total_rows": int(n_total),
        "fraud_rate": round(n_fraud / n_total, 5),
    }
    metrics_path = output_path.with_suffix("").parent / (output_path.stem + "_metrics.json")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics_record, indent=2))
    logger.info("Metrics saved → %s", metrics_path)
    logger.info("Bootstrap complete. Reload HybridScorer to activate supervised layer.")

    return all_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap XGBoost fraud model")
    parser.add_argument("--model-path", default=None, help="Output .pkl path")
    args = parser.parse_args()
    metrics = run(model_path=args.model_path)
    pr = metrics.get("pr_auc", 0.0)
    sys.exit(0 if pr > 0.5 else 1)
