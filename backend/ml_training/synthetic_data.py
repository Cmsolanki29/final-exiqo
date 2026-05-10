"""Synthetic fraud injection for bootstrap training.

Phase 3: Supervised Model Layer.
Dependencies: pandas, numpy.
Performance budget: generate_synthetic_fraud() < 5s for 100k rows.

Why synthetic data?
  At launch, we have zero labeled fraud examples.  Without labeled data,
  the XGBoost layer cannot train.  Synthetic injection creates plausible
  fraud patterns to bootstrap the supervised model.  Real labels from
  user reports and chargebacks (Phase 8) will progressively replace them.

Five fraud patterns (mirrors Stripe Radar's rule taxonomy):
  1. Card-testing burst  — rapid small debits from same user
  2. Account drain       — single transaction far above user's p95
  3. Off-hours unusual   — night transaction for daytime-only user
  4. Geo-impossible      — simulated with unusual location + high amount
  5. New-merchant drain  — high amount at never-seen merchant
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd


def generate_synthetic_fraud(
    legitimate_df: pd.DataFrame,
    fraud_rate: float = 0.005,
    seed: int = 42,
) -> pd.DataFrame:
    """Inject synthetic fraud rows into a legitimate transaction DataFrame.

    The returned DataFrame contains ALL rows (legitimate + synthetic fraud)
    with `is_fraud` and `fraud_label_source` columns added.

    Args:
        legitimate_df: DataFrame with transactions matching the `transactions`
                       table schema (at minimum: user_id, amount, category,
                       merchant, hour_of_day, is_weekend, transaction_date).
        fraud_rate:    Target fraction of the output that should be fraud.
                       Default 0.5% mirrors real-world card fraud base rates.
        seed:          Random seed for reproducibility.

    Returns:
        Combined DataFrame with is_fraud (bool) and fraud_label_source (str).
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)

    if legitimate_df.empty:
        return legitimate_df.copy()

    df = legitimate_df.copy()
    df["is_fraud"] = False
    df["fraud_label_source"] = "legitimate"

    n_fraud_target = max(1, int(len(df) * fraud_rate))
    fraud_rows: list[dict[str, Any]] = []

    # Compute per-user stats for pattern generation
    debit_df = df[df.get("type", "DEBIT") == "DEBIT"] if "type" in df.columns else df
    user_stats = (
        debit_df.groupby("user_id")["amount"]
        .agg(mean="mean", std="std", p95=lambda x: x.quantile(0.95), count="count")
        .to_dict("index")
    )

    users = debit_df["user_id"].unique().tolist()
    if not users:
        return df

    def _user_stats(uid: int) -> dict:
        return user_stats.get(uid, {"mean": 1000.0, "std": 500.0, "p95": 3000.0, "count": 10})

    def _base_row(uid: int) -> dict[str, Any]:
        """Clone a legitimate row from this user as the base for a fraud row."""
        user_rows = debit_df[debit_df["user_id"] == uid]
        if user_rows.empty:
            user_rows = df[df["user_id"] == uid]
        base = user_rows.sample(1, random_state=int(rng.integers(0, 2**31))).iloc[0].to_dict()
        return base

    n_per_pattern = max(1, n_fraud_target // 5)

    # ------------------------------------------------------------------ #
    # Pattern 1: Card-testing burst
    # Rapid small transactions (< ₹200) within a 2-minute window.
    # Card testers probe with micro-charges before a large withdrawal.
    # ------------------------------------------------------------------ #
    for _ in range(n_per_pattern):
        uid = int(rng.choice(users))
        base = _base_row(uid)
        burst_time = _random_datetime(rng)
        for j in range(rng.integers(5, 8).item()):
            row = dict(base)
            row["user_id"] = uid
            row["amount"] = float(rng.integers(10, 150))
            row["hour_of_day"] = burst_time.hour
            row["transaction_date"] = (burst_time + timedelta(seconds=j * 20)).date()
            row["merchant"] = f"TestMerchant_{rng.integers(100, 999)}"
            row["is_fraud"] = True
            row["fraud_label_source"] = "synthetic_card_test_burst"
            fraud_rows.append(row)

    # ------------------------------------------------------------------ #
    # Pattern 2: Account drain
    # Single transaction > 10x user's p95 amount.
    # Classic cashout: attacker drains account in one shot.
    # ------------------------------------------------------------------ #
    for _ in range(n_per_pattern):
        uid = int(rng.choice(users))
        stats = _user_stats(uid)
        drain_amount = float(stats["p95"]) * float(rng.uniform(10.0, 20.0))
        base = _base_row(uid)
        row = dict(base)
        row["amount"] = round(drain_amount, 2)
        row["merchant"] = "BulkTransferSuspicious"
        row["hour_of_day"] = int(rng.integers(0, 4))  # odd hour
        row["is_fraud"] = True
        row["fraud_label_source"] = "synthetic_account_drain"
        fraud_rows.append(row)

    # ------------------------------------------------------------------ #
    # Pattern 3: Off-hours unusual
    # 3 AM transaction for a user whose typical hour is 9 AM–9 PM.
    # Stolen credentials are often used at night when the victim is asleep.
    # ------------------------------------------------------------------ #
    daytime_users = (
        debit_df[debit_df["hour_of_day"].between(8, 21)]["user_id"].unique().tolist()
        if "hour_of_day" in debit_df.columns else users
    )
    for _ in range(n_per_pattern):
        uid = int(rng.choice(daytime_users or users))
        stats = _user_stats(uid)
        base = _base_row(uid)
        row = dict(base)
        row["amount"] = float(stats["mean"]) * float(rng.uniform(2.0, 5.0))
        row["hour_of_day"] = int(rng.choice([1, 2, 3, 4]))
        row["is_night_txn"] = True
        row["merchant"] = f"NightMerchant_{rng.integers(1, 99)}"
        row["is_fraud"] = True
        row["fraud_label_source"] = "synthetic_off_hours"
        fraud_rows.append(row)

    # ------------------------------------------------------------------ #
    # Pattern 4: Geo-impossible (simulated without real coordinates)
    # High amount + unusual location marker in rapid succession.
    # In production this would check lat/lon distance between consecutive txns.
    # ------------------------------------------------------------------ #
    for _ in range(n_per_pattern):
        uid = int(rng.choice(users))
        stats = _user_stats(uid)
        base = _base_row(uid)
        row = dict(base)
        row["amount"] = float(stats["p95"]) * float(rng.uniform(3.0, 8.0))
        row["location"] = "International_Suspicious"
        row["merchant"] = f"ForeignMerchant_{rng.integers(1, 999)}"
        row["payment_method"] = "CARD"
        row["is_fraud"] = True
        row["fraud_label_source"] = "synthetic_geo_impossible"
        # Mark for signal in signals dict
        row["_geo_flag"] = True
        fraud_rows.append(row)

    # ------------------------------------------------------------------ #
    # Pattern 5: New-merchant drain
    # High amount at a merchant the user has never transacted with,
    # combined with low balance after.
    # ------------------------------------------------------------------ #
    for _ in range(n_per_pattern):
        uid = int(rng.choice(users))
        stats = _user_stats(uid)
        base = _base_row(uid)
        row = dict(base)
        row["amount"] = float(stats["mean"]) * float(rng.uniform(5.0, 12.0))
        row["merchant"] = f"NeverSeenMerchant_{rng.integers(10000, 99999)}"
        row["balance_after"] = float(rng.integers(10, 200))
        row["is_fraud"] = True
        row["fraud_label_source"] = "synthetic_new_merchant_drain"
        fraud_rows.append(row)

    if not fraud_rows:
        return df

    fraud_df = pd.DataFrame(fraud_rows)
    # Ensure the fraud df has the same columns as the legit df
    for col in df.columns:
        if col not in fraud_df.columns:
            fraud_df[col] = df[col].iloc[0] if len(df) > 0 else None

    fraud_df = fraud_df[df.columns]
    result = pd.concat([df, fraud_df], ignore_index=True)

    actual_rate = fraud_df["is_fraud"].sum() / len(result)
    print(f"Synthetic fraud: {len(fraud_df)} rows injected ({actual_rate*100:.2f}% fraud rate)")
    return result


def _random_datetime(rng: np.random.Generator) -> datetime:
    """Generate a random datetime within the last 90 days."""
    days_back = int(rng.integers(1, 90))
    hour = int(rng.integers(0, 24))
    minute = int(rng.integers(0, 60))
    return datetime.now() - timedelta(days=days_back, hours=hour, minutes=minute)
