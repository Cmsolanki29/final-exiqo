"""Feature assembler — combines entity features + transaction-level signals.

Phase 2: Online Feature Store.
Dependencies: redis (via online_store), asyncpg (via offline_store), numpy.
Performance budget: assemble() < 30ms including Redis pipeline call.

What this does:
  1. Fires one Redis pipeline to fetch user + merchant features simultaneously.
  2. Applies catalog defaults for any missing features.
  3. Computes transaction-level derived features from the raw txn payload:
     - Log-scaled amount
     - Hour sin/cos encoding (cyclical)
     - Amount vs user average (the most important real-time signal)
     - is_new_merchant (not in user's known_merchants)
     - Time-of-day risk tier
  4. Returns a single flat dict with prefixed keys (user_*, merchant_*, txn_*).
     This dict is passed directly into score_single() as the `features` argument,
     replacing the neutral velocity defaults used in Phase 1.

Latency breakdown target:
  Redis pipeline  ~2ms
  Python compute  ~1ms
  Total           ~3ms  (well within 30ms budget)
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from services.feature_store.catalog import get_defaults
from services.feature_store.online_store import online_feature_store

logger = logging.getLogger(__name__)


class FeatureAssembler:
    """Assembles the full feature vector for a single incoming transaction.

    Designed to be called once per transaction on the hot path.  All I/O is
    async (single Redis pipeline); no blocking DB calls in the hot path.
    """

    async def assemble(
        self, txn: dict[str, Any], user_id: int | None = None
    ) -> dict[str, Any]:
        """Build the full feature vector for a transaction.

        Args:
            txn:     TransactionIn.to_feature_dict() output or equivalent dict.
            user_id: Explicit user_id; falls back to txn["user_id"] if present.

        Returns:
            Flat dict of feature_name → scalar value, ready for score_single().
        """
        t0 = time.perf_counter()

        uid_str = str(user_id or txn.get("user_id", "0"))
        merchant = str(txn.get("merchant") or "").strip()

        # ---- Single pipeline call: fetch user + merchant features ---- #
        requests: list[tuple[str, str]] = [("user", uid_str)]
        if merchant:
            requests.append(("merchant", merchant))

        multi_result = await online_feature_store.get_multi(requests)

        user_feats: dict[str, Any] = multi_result.get(f"user:{uid_str}", get_defaults("user"))
        merchant_feats: dict[str, Any] = (
            multi_result.get(f"merchant:{merchant}", get_defaults("merchant"))
            if merchant
            else get_defaults("merchant")
        )

        # ---- Transaction-level computed features ---- #
        txn_feats = self._compute_txn_features(txn, user_feats)

        # ---- Combine with prefixed keys ---- #
        assembled: dict[str, Any] = {}
        for k, v in user_feats.items():
            assembled[f"user_{k}"] = v
        for k, v in merchant_feats.items():
            assembled[f"merchant_{k}"] = v
        for k, v in txn_feats.items():
            assembled[f"txn_{k}"] = v

        # ---- Flat aliases used by score_single velocity logic ---- #
        # These are the keys score_single reads from the `features` param.
        assembled["amt_ratio_30d"] = txn_feats.get("amount_vs_user_avg_30d", 1.0)
        assembled["hours_since_prev"] = txn_feats.get("hours_since_prev_estimate", 24.0)
        assembled["velocity_inr_per_hour"] = txn_feats.get("velocity_inr_per_hour", 0.0)
        assembled["merchant_changed"] = txn_feats.get("is_new_merchant", 0.0)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        if elapsed_ms > 30:
            logger.warning(
                "feature_assemble_slow latency_ms=%.1f user=%s", elapsed_ms, uid_str
            )
        else:
            logger.debug(
                "feature_assembled user=%s n_features=%d latency_ms=%.2f",
                uid_str, len(assembled), elapsed_ms,
            )

        return assembled

    def _compute_txn_features(
        self, txn: dict[str, Any], user_feats: dict[str, Any]
    ) -> dict[str, Any]:
        """Derive transaction-level features from the raw payload + user context.

        These are computed in-process (no I/O) so they are always current —
        unlike entity features which are materialised every 15 minutes.

        Returns a dict with unprefixed keys (prefix is added by assemble()).
        """
        amount = float(txn.get("amount") or 0.0)
        hour = int(txn.get("hour_of_day") or 0)
        dow = int(txn.get("day_of_week") or 0)
        is_weekend = bool(txn.get("is_weekend", False))
        is_night = bool(txn.get("is_night_txn", False))
        merchant = str(txn.get("merchant") or "")
        balance_after = txn.get("balance_after")

        # Log-scaled amount (compresses the INR distribution)
        log_amount = math.log1p(max(amount, 0.0))

        # Cyclical hour encoding: avoids 23 → 0 discontinuity
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)

        # Amount relative to user's 30d average
        user_avg = float(user_feats.get("debit_avg_30d") or 0.0)
        if user_avg > 0:
            amount_vs_user_avg_30d = amount / user_avg
        else:
            amount_vs_user_avg_30d = 1.0

        # Amount relative to user's p95 (> 1 means above normal ceiling)
        user_p95 = float(user_feats.get("debit_p95_30d") or 0.0)
        amount_vs_p95 = (amount / user_p95) if user_p95 > 0 else 1.0

        # Velocity estimate — debit_sum_1h / max(1, txn_count_1h) transactions
        txn_count_1h = int(user_feats.get("txn_count_1h") or 0)
        debit_sum_1h = float(user_feats.get("debit_sum_1h") or 0.0)
        velocity_inr_per_hour = debit_sum_1h if txn_count_1h >= 1 else 0.0

        # Estimate hours since previous transaction (avg inter-arrival / recent count)
        avg_inter = float(user_feats.get("avg_hours_between_txns_30d") or 24.0)
        # If burst (> 3 txns in last hour), hours_since_prev is very small
        if txn_count_1h >= 3:
            hours_since_prev_estimate = max(60.0 / max(txn_count_1h, 1) / 60.0, 0.017)
        else:
            hours_since_prev_estimate = avg_inter

        # Is this a new merchant? (not in known_merchants list — Phase 3+ populates this)
        # For now, if merchant_txn_count_30d == 0, treat as new
        merchant_txn_count = int(user_feats.get("merchant_txn_count_30d") or 0)
        is_new_merchant = 1.0 if (merchant and merchant_txn_count == 0) else 0.0

        # Balance utilisation
        if balance_after is not None and float(balance_after) > 0:
            balance_ratio = amount / float(balance_after)
        else:
            balance_ratio = 0.0

        # Round-amount flag (common in test transactions and bulk payments)
        is_round_amount = 1.0 if (amount >= 500 and (amount % 1000 == 0 or amount % 500 == 0)) else 0.0

        # Time-of-day risk tier
        if hour >= 23 or hour <= 5:
            time_risk = 2.0
        elif 20 <= hour <= 22:
            time_risk = 1.0
        else:
            time_risk = 0.0

        # Burst detection: > 3 transactions in last hour is unusual
        is_burst = 1.0 if txn_count_1h >= 3 else 0.0

        return {
            "log_amount": round(log_amount, 4),
            "hour_sin": round(hour_sin, 4),
            "hour_cos": round(hour_cos, 4),
            "amount_vs_user_avg_30d": round(amount_vs_user_avg_30d, 4),
            "amount_vs_p95": round(amount_vs_p95, 4),
            "velocity_inr_per_hour": round(velocity_inr_per_hour, 2),
            "hours_since_prev_estimate": round(hours_since_prev_estimate, 4),
            "is_new_merchant": is_new_merchant,
            "balance_ratio": round(balance_ratio, 6),
            "is_round_amount": is_round_amount,
            "time_risk": time_risk,
            "is_burst": is_burst,
            "is_weekend": 1.0 if is_weekend else 0.0,
            "is_night": 1.0 if is_night else 0.0,
            "day_of_week": float(dow),
        }


# Module-level singleton
feature_assembler = FeatureAssembler()
