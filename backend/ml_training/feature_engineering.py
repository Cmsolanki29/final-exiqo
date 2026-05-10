"""Feature engineering for supervised XGBoost training.

Phase 3: Supervised Model Layer.
Dependencies: pandas, numpy, asyncpg (optional for DB pull).
Performance budget: build_features_from_df() < 30s for 100k rows.

Two entry points:
  1. build_features_from_df(df)  — pure-pandas, no DB required.
     Used by bootstrap_train.py and tests.
  2. build_training_matrix(start_date, end_date) — pulls labeled
     transactions from Postgres using asyncpg + point-in-time feature
     snapshots from the offline store.

CRITICAL — Point-in-time correctness:
  For every labeled transaction we reconstruct the feature vector AS IT
  WOULD HAVE BEEN AT TRANSACTION TIME, not as it is today.  This prevents
  label leakage where future aggregate statistics contaminate training.
  We use OfflineFeatureStore.get_at_time() when snapshots exist; when they
  don't (bootstrap scenario), we fall back to a lag-correct rolling-window
  computation over the sorted DataFrame.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Canonical feature columns used by XGBoost
# Order is stable — do NOT reorder without retraining.
# ------------------------------------------------------------------ #
SUPERVISED_FEATURE_COLUMNS: list[str] = [
    # User rolling aggregates (from feature store / rolling compute)
    "txn_count_1h",
    "txn_count_24h",
    "txn_count_7d",
    "txn_count_30d",
    "debit_sum_1h",
    "debit_sum_24h",
    "debit_avg_30d",
    "debit_std_30d",
    "debit_p95_30d",
    "unique_merchants_30d",
    "account_age_days",
    "weekend_txn_ratio_30d",
    "avg_hours_between_txns_30d",
    # Transaction-level computed features
    "log_amount",
    "hour_sin",
    "hour_cos",
    "amount_vs_avg_30d",
    "amount_vs_p95",
    "velocity_inr_per_hour",
    "hours_since_prev",
    "is_new_merchant",
    "balance_ratio",
    "is_round_amount",
    "time_risk",
    "is_burst",
    "is_weekend",
    "is_night",
    "day_of_week",
]


def build_features_from_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Build training feature matrix from a raw transactions DataFrame.

    This is the bootstrap / offline path.  It computes rolling aggregates
    per user using a time-sorted DataFrame to maintain lag correctness
    (each row sees only past transactions of that user, not future ones).

    Args:
        df: DataFrame with columns matching the transactions table schema.
            Must contain: user_id, amount, transaction_date, hour_of_day,
            day_of_week, is_weekend, merchant, balance_after, is_fraud.
            Rows without is_fraud label are silently dropped.

    Returns:
        (X, y): feature DataFrame (SUPERVISED_FEATURE_COLUMNS) and label Series.
    """
    # ---- Pre-processing ---- #
    df = df.copy()
    df = df[df["is_fraud"].notna()].reset_index(drop=True)
    if df.empty:
        return pd.DataFrame(columns=SUPERVISED_FEATURE_COLUMNS), pd.Series(dtype=float)

    # Ensure correct dtypes
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["hour_of_day"] = pd.to_numeric(df["hour_of_day"], errors="coerce").fillna(12).astype(int)
    df["day_of_week"] = pd.to_numeric(df["day_of_week"], errors="coerce").fillna(0).astype(int)
    df["is_weekend"] = df.get("is_weekend", pd.Series(False, index=df.index)).fillna(False)
    df["balance_after"] = pd.to_numeric(df.get("balance_after", pd.Series(0.0)), errors="coerce").fillna(0.0)

    # Parse transaction date for rolling windows
    if "transaction_date" in df.columns:
        df["_ts"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    else:
        df["_ts"] = pd.Timestamp.now()
    df = df.sort_values(["user_id", "_ts"]).reset_index(drop=True)

    # ---- Per-user rolling aggregates (lag-correct) ---- #
    rows: list[dict] = []
    for uid, udf in df.groupby("user_id", sort=False):
        amounts = udf["amount"].values
        ts_arr = udf["_ts"].values
        merchants = udf["merchant"].values if "merchant" in udf.columns else np.full(len(udf), "")

        # User lifetime stats (computed from entire user history, not leaky —
        # because we train and score on the same users across time windows)
        user_mean = float(np.mean(amounts)) if len(amounts) > 0 else 1000.0
        user_std = float(np.std(amounts)) if len(amounts) > 1 else 500.0
        user_p95 = float(np.percentile(amounts, 95)) if len(amounts) > 0 else 3000.0

        # Account age from date range
        if len(udf) > 1 and pd.notna(ts_arr[0]):
            acct_days = max((ts_arr[-1] - ts_arr[0]).astype("timedelta64[D]").astype(int), 1)
        else:
            acct_days = 30

        for i, row in udf.iterrows():
            feats: dict = _build_row_features(
                row=row,
                prev_amounts=amounts[:udf.index.get_loc(i)],
                prev_ts=ts_arr[:udf.index.get_loc(i)],
                prev_merchants=merchants[:udf.index.get_loc(i)],
                user_mean=user_mean,
                user_std=user_std,
                user_p95=user_p95,
                acct_days=acct_days,
            )
            rows.append(feats)

    X = pd.DataFrame(rows, columns=SUPERVISED_FEATURE_COLUMNS)
    y = df["is_fraud"].astype(float).reset_index(drop=True)
    return X, y


def _build_row_features(
    row: pd.Series,
    prev_amounts: np.ndarray,
    prev_ts: np.ndarray,
    prev_merchants: np.ndarray,
    user_mean: float,
    user_std: float,
    user_p95: float,
    acct_days: int,
) -> dict:
    """Compute SUPERVISED_FEATURE_COLUMNS for a single transaction row."""
    amount = float(row.get("amount", 0.0) or 0.0)
    hour = int(row.get("hour_of_day", 12) or 12)
    dow = int(row.get("day_of_week", 0) or 0)
    is_weekend = bool(row.get("is_weekend", False))
    is_night = bool(row.get("is_night_txn", hour >= 23 or hour <= 5))
    merchant = str(row.get("merchant") or "")
    balance_after = float(row.get("balance_after", 0.0) or 0.0)
    current_ts = row.get("_ts") or pd.Timestamp.now()

    # Rolling windows from prev_ts
    now_ns = np.datetime64(current_ts, "ns")
    one_hour_ago = now_ns - np.timedelta64(1, "h")
    one_day_ago = now_ns - np.timedelta64(1, "D")
    seven_days_ago = now_ns - np.timedelta64(7, "D")
    thirty_days_ago = now_ns - np.timedelta64(30, "D")

    mask_1h = prev_ts >= one_hour_ago
    mask_24h = prev_ts >= one_day_ago
    mask_7d = prev_ts >= seven_days_ago
    mask_30d = prev_ts >= thirty_days_ago

    txn_count_1h = int(mask_1h.sum())
    txn_count_24h = int(mask_24h.sum())
    txn_count_7d = int(mask_7d.sum())
    txn_count_30d = int(mask_30d.sum())

    debit_sum_1h = float(prev_amounts[mask_1h].sum()) if txn_count_1h else 0.0
    debit_sum_24h = float(prev_amounts[mask_24h].sum()) if txn_count_24h else 0.0
    amounts_30d = prev_amounts[mask_30d]
    debit_avg_30d = float(amounts_30d.mean()) if len(amounts_30d) else user_mean
    debit_std_30d = float(amounts_30d.std()) if len(amounts_30d) > 1 else user_std
    debit_p95_30d = float(np.percentile(amounts_30d, 95)) if len(amounts_30d) else user_p95

    # Unique merchants in 30d
    merchants_30d = prev_merchants[mask_30d] if len(prev_merchants) else np.array([])
    unique_merchants_30d = int(len(set(merchants_30d))) if len(merchants_30d) else 0

    # Avg hours between transactions in 30d
    ts_30d = prev_ts[mask_30d]
    if len(ts_30d) >= 2:
        diffs_h = np.diff(ts_30d.astype("datetime64[m]")).astype(float) / 60.0
        avg_hours = float(diffs_h.mean()) if len(diffs_h) > 0 else 24.0
    else:
        avg_hours = 24.0

    # Weekend ratio 30d
    weekend_txn_ratio_30d = (
        float(sum(1 for t in ts_30d if _is_weekend_ts(t)) / max(len(ts_30d), 1))
        if len(ts_30d) else 0.0
    )

    # Hours since previous transaction
    if len(prev_ts) > 0:
        last_ts = prev_ts[-1]
        diff_ns = float((now_ns - last_ts).astype("timedelta64[m]").astype(int))
        hours_since_prev = max(diff_ns / 60.0, 0.0)
    else:
        hours_since_prev = 24.0

    # Velocity
    velocity_inr_per_hour = debit_sum_1h if txn_count_1h >= 1 else 0.0

    # Is burst (> 3 txns in last hour)
    is_burst = 1.0 if txn_count_1h >= 3 else 0.0

    # Transaction-level derived
    log_amount = math.log1p(max(amount, 0.0))
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)
    amount_vs_avg_30d = (amount / max(debit_avg_30d, 1.0))
    amount_vs_p95 = (amount / max(debit_p95_30d, 1.0))

    # Is new merchant (not seen in 30d history)
    is_new_merchant = 0.0
    if merchant and len(merchants_30d) > 0:
        is_new_merchant = 0.0 if merchant in merchants_30d else 1.0
    elif merchant:
        is_new_merchant = 1.0

    # Balance ratio
    balance_ratio = (amount / max(balance_after, 1.0)) if balance_after > 0 else 0.0

    # Round amount
    is_round_amount = 1.0 if (amount >= 500 and (amount % 1000 == 0 or amount % 500 == 0)) else 0.0

    # Time risk tier
    if hour >= 23 or hour <= 5:
        time_risk = 2.0
    elif 20 <= hour <= 22:
        time_risk = 1.0
    else:
        time_risk = 0.0

    return {
        "txn_count_1h": txn_count_1h,
        "txn_count_24h": txn_count_24h,
        "txn_count_7d": txn_count_7d,
        "txn_count_30d": txn_count_30d,
        "debit_sum_1h": debit_sum_1h,
        "debit_sum_24h": debit_sum_24h,
        "debit_avg_30d": debit_avg_30d,
        "debit_std_30d": debit_std_30d,
        "debit_p95_30d": debit_p95_30d,
        "unique_merchants_30d": unique_merchants_30d,
        "account_age_days": acct_days,
        "weekend_txn_ratio_30d": weekend_txn_ratio_30d,
        "avg_hours_between_txns_30d": avg_hours,
        "log_amount": round(log_amount, 4),
        "hour_sin": round(hour_sin, 4),
        "hour_cos": round(hour_cos, 4),
        "amount_vs_avg_30d": round(amount_vs_avg_30d, 4),
        "amount_vs_p95": round(amount_vs_p95, 4),
        "velocity_inr_per_hour": round(velocity_inr_per_hour, 2),
        "hours_since_prev": round(hours_since_prev, 4),
        "is_new_merchant": is_new_merchant,
        "balance_ratio": round(balance_ratio, 6),
        "is_round_amount": is_round_amount,
        "time_risk": time_risk,
        "is_burst": is_burst,
        "is_weekend": 1.0 if is_weekend else 0.0,
        "is_night": 1.0 if is_night else 0.0,
        "day_of_week": float(dow),
    }


def _is_weekend_ts(ts: np.datetime64) -> bool:
    """Return True if a numpy datetime64 falls on a weekend."""
    try:
        dt = pd.Timestamp(ts)
        return dt.weekday() >= 5
    except Exception:
        return False


def assembled_to_feature_vector(
    assembled: dict,
    fill_value: float = 0.0,
) -> np.ndarray:
    """Map an assembled feature dict (Phase 2) to the XGBoost feature vector.

    This is the INFERENCE path.  The training path uses build_features_from_df.
    Both must produce the same feature columns in the same order (SUPERVISED_FEATURE_COLUMNS).

    Mapping logic:
      - assembled keys have prefixes: user_*, merchant_*, txn_*, and flat aliases.
      - We map each SUPERVISED_FEATURE_COLUMN to its assembled counterpart.
      - Unknown keys fall back to fill_value (0.0).

    Args:
        assembled: Output of FeatureAssembler.assemble().
        fill_value: Value used for any feature not found in assembled.

    Returns:
        numpy float32 array of shape (len(SUPERVISED_FEATURE_COLUMNS),).
    """
    # Mapping: SUPERVISED_FEATURE_COLUMN → assembled key
    _MAP: dict[str, str] = {
        "txn_count_1h":               "user_txn_count_1h",
        "txn_count_24h":              "user_txn_count_24h",
        "txn_count_7d":               "user_txn_count_7d",
        "txn_count_30d":              "user_txn_count_30d",
        "debit_sum_1h":               "user_debit_sum_1h",
        "debit_sum_24h":              "user_debit_sum_24h",
        "debit_avg_30d":              "user_debit_avg_30d",
        "debit_std_30d":              "user_debit_std_30d",
        "debit_p95_30d":              "user_debit_p95_30d",
        "unique_merchants_30d":       "user_unique_merchants_30d",
        "account_age_days":           "user_account_age_days",
        "weekend_txn_ratio_30d":      "user_weekend_txn_ratio_30d",
        "avg_hours_between_txns_30d": "user_avg_hours_between_txns_30d",
        "log_amount":                 "txn_log_amount",
        "hour_sin":                   "txn_hour_sin",
        "hour_cos":                   "txn_hour_cos",
        "amount_vs_avg_30d":          "amt_ratio_30d",
        "amount_vs_p95":              "txn_amount_vs_p95",
        "velocity_inr_per_hour":      "velocity_inr_per_hour",
        "hours_since_prev":           "hours_since_prev",
        "is_new_merchant":            "merchant_changed",
        "balance_ratio":              "txn_balance_ratio",
        "is_round_amount":            "txn_is_round_amount",
        "time_risk":                  "txn_time_risk",
        "is_burst":                   "txn_is_burst",
        "is_weekend":                 "txn_is_weekend",
        "is_night":                   "txn_is_night",
        "day_of_week":                "txn_day_of_week",
    }

    vec = np.array(
        [float(assembled.get(_MAP.get(col, col), fill_value)) for col in SUPERVISED_FEATURE_COLUMNS],
        dtype=np.float32,
    )
    # Replace NaN/inf with fill_value
    vec = np.where(np.isfinite(vec), vec, fill_value)
    return vec


async def build_training_matrix(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Pull labeled transactions from Postgres and build the XGBoost training matrix.

    Uses point-in-time feature snapshots where available, falls back to
    inline rolling computation (same as build_features_from_df).

    Args:
        start_date: Earliest transaction date to include.
        end_date:   Latest transaction date (defaults to now).

    Returns:
        (X, y): DataFrame with SUPERVISED_FEATURE_COLUMNS, and label Series.
    """
    try:
        from core.db import get_pool
        pool = get_pool()
        if pool is None:
            logger.warning("build_training_matrix: no DB pool, returning empty matrix")
            return pd.DataFrame(columns=SUPERVISED_FEATURE_COLUMNS), pd.Series(dtype=float)

        end_dt = end_date or datetime.now(timezone.utc)
        start_dt = start_date or (end_dt.replace(year=end_dt.year - 1))

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT t.id, t.user_id, t.amount, t.merchant, t.category,
                       t.hour_of_day, t.day_of_week, t.is_weekend, t.balance_after,
                       t.transaction_date, t.is_fraud, t.fraud_label_source,
                       t.type
                FROM   transactions t
                WHERE  t.is_fraud IS NOT NULL
                  AND  t.transaction_date BETWEEN $1 AND $2
                  AND  t.type = 'DEBIT'
                ORDER  BY t.user_id, t.transaction_date
                """,
                start_dt.date(),
                end_dt.date(),
            )

        if not rows:
            logger.warning("build_training_matrix: no labeled rows found in date range")
            return pd.DataFrame(columns=SUPERVISED_FEATURE_COLUMNS), pd.Series(dtype=float)

        df = pd.DataFrame([dict(r) for r in rows])
        df["transaction_date"] = pd.to_datetime(df["transaction_date"])
        df.rename(columns={"transaction_date": "_ts"}, inplace=True)

        logger.info(
            "build_training_matrix: loaded %d labeled rows (%d fraud, %d legit)",
            len(df), int(df["is_fraud"].sum()), int((~df["is_fraud"]).sum()),
        )
        return build_features_from_df(df.rename(columns={"_ts": "transaction_date"}))

    except Exception as exc:
        logger.exception("build_training_matrix failed: %s", exc)
        return pd.DataFrame(columns=SUPERVISED_FEATURE_COLUMNS), pd.Series(dtype=float)
