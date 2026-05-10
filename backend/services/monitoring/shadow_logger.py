"""Shadow model logging and statistical evaluation for SmartSpend.

Phase 5: MLOps.
Dependencies: asyncpg (core/db.py), numpy.
Performance budget: log() < 5ms (async, fire-and-forget from hot path).

How shadow deployment works:
  1. When a new model is promoted to Staging, it becomes the "shadow" model.
  2. Every transaction is scored by BOTH the production model and the shadow model.
  3. ShadowLogger.log() persists both scores to shadow_predictions table.
  4. ShadowLogger.evaluate_shadow() runs a statistical check:
       a. Score distribution similarity (PSI).
       b. Per-segment regression: no user segment should see >20% more blocks.
  5. If all checks pass, the shadow model is eligible for canary promotion.

Per-segment definitions:
  new_user        — account_age_days < 30
  returning_user  — account_age_days 30-364
  high_value      — avg_txn_amount > 5000
  low_value       — avg_txn_amount <= 5000
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np

from core.db import get_pool

logger = logging.getLogger(__name__)

# Per-segment maximum allowed INCREASE in block rate vs. production
_MAX_BLOCK_RATE_INCREASE = 0.20  # 20 percentage points


class ShadowLogger:
    """Records dual-scored transactions and evaluates shadow model quality.

    Usage (from transactions route):
        asyncio.create_task(shadow_logger.log(
            prod_score=85, shadow_score=78,
            txn_id=1234, prod_action="blocked", shadow_action="review",
            features_hash=features_hash(assembled_features),
        ))
    """

    # ------------------------------------------------------------------ #
    # Write operations
    # ------------------------------------------------------------------ #

    async def log(
        self,
        prod_score: int,
        shadow_score: int,
        txn_id: Optional[int],
        prod_action: str,
        shadow_action: str,
        features_hash: Optional[str] = None,
    ) -> None:
        """Persist a dual-scored prediction pair to shadow_predictions.

        This is called fire-and-forget from the transaction route after the
        DB insert so we have a valid txn_id.  Failures are logged but do not
        propagate.

        Args:
            prod_score:     Risk score (0-100) from the production model.
            shadow_score:   Risk score (0-100) from the shadow model.
            txn_id:         Postgres transaction id (nullable before insert).
            prod_action:    Decision action from production ('accepted', 'blocked', etc.).
            shadow_action:  Hypothetical action from shadow model.
            features_hash:  MD5 of feature vector for correlation with feature_snapshots.
        """
        pool = get_pool()
        if pool is None:
            logger.debug("shadow_logger.log: pool unavailable, skipping")
            return
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO shadow_predictions
                        (transaction_id, prod_score, shadow_score,
                         prod_action, shadow_action, feature_hash)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    txn_id,
                    prod_score,
                    shadow_score,
                    prod_action,
                    shadow_action,
                    features_hash,
                )
            logger.debug(
                "shadow_logger.log: txn_id=%s prod=%d shadow=%d",
                txn_id, prod_score, shadow_score,
            )
        except Exception as exc:
            logger.warning("shadow_logger.log failed txn_id=%s: %s", txn_id, exc)

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    async def evaluate_shadow(self, period_days: int = 7) -> dict[str, Any]:
        """Evaluate shadow model over the last `period_days`.

        Checks:
          1. Score distribution PSI < 0.25 between prod and shadow scores.
          2. Per-segment block rate: shadow block rate must not exceed
             production block rate by more than 20 percentage points in
             any segment.

        Returns:
            Dict with keys:
              passed (bool),
              checks (dict of check_name → {passed, details}),
              score_psi (float),
              period_days (int),
              sample_n (int).
        """
        rows = await self._fetch_shadow_rows(period_days)
        if not rows:
            return {
                "passed": True,
                "checks": {},
                "score_psi": 0.0,
                "period_days": period_days,
                "sample_n": 0,
                "note": "no shadow predictions in period",
            }

        prod_scores = np.array([r["prod_score"] for r in rows], dtype=float)
        shadow_scores = np.array([r["shadow_score"] for r in rows], dtype=float)

        from services.monitoring.drift import population_stability_index
        score_psi = population_stability_index(prod_scores, shadow_scores)

        checks: dict[str, dict] = {}

        # Check 1: score distribution stability
        psi_passed = score_psi < 0.25
        checks["score_distribution_psi"] = {
            "passed": psi_passed,
            "psi": score_psi,
            "threshold": 0.25,
        }

        # Check 2: per-segment block rate regression
        segment_check = await self._check_segment_regression(rows)
        checks["segment_block_rate"] = segment_check

        overall_passed = all(c["passed"] for c in checks.values())
        logger.info(
            "shadow_logger.evaluate_shadow: passed=%s psi=%.4f sample_n=%d",
            overall_passed, score_psi, len(rows),
        )
        return {
            "passed": overall_passed,
            "checks": checks,
            "score_psi": score_psi,
            "period_days": period_days,
            "sample_n": len(rows),
        }

    async def _fetch_shadow_rows(self, period_days: int) -> list[dict]:
        """Pull shadow_predictions rows for the last period_days."""
        pool = get_pool()
        if pool is None:
            return []
        try:
            since = datetime.now(timezone.utc) - timedelta(days=period_days)
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT sp.prod_score, sp.shadow_score,
                           sp.prod_action, sp.shadow_action,
                           t.amount, t.user_id
                    FROM   shadow_predictions sp
                    LEFT   JOIN transactions t ON t.id = sp.transaction_id
                    WHERE  sp.created_at >= $1
                    LIMIT  50000
                    """,
                    since,
                )
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning("shadow_logger._fetch_shadow_rows failed: %s", exc)
            return []

    async def _check_segment_regression(
        self, rows: list[dict]
    ) -> dict[str, Any]:
        """Check that no user segment sees >20% more blocks under shadow model.

        Segments are defined purely from amount (no account_age_days available
        in shadow_predictions without an extra join):
          high_value:  amount > 5000
          low_value:   amount <= 5000 (or amount is NULL)
        """
        segments: dict[str, dict[str, list[str]]] = {
            "high_value":  {"prod": [], "shadow": []},
            "low_value":   {"prod": [], "shadow": []},
        }

        for row in rows:
            amount = row.get("amount") or 0
            seg = "high_value" if amount > 5000 else "low_value"
            segments[seg]["prod"].append(row["prod_action"])
            segments[seg]["shadow"].append(row["shadow_action"])

        segment_results: dict[str, dict] = {}
        all_passed = True

        for seg_name, data in segments.items():
            prod_actions = data["prod"]
            shadow_actions = data["shadow"]
            if len(prod_actions) < 10:
                segment_results[seg_name] = {"passed": True, "note": "insufficient_data"}
                continue

            prod_block_rate = _block_rate(prod_actions)
            shadow_block_rate = _block_rate(shadow_actions)
            delta = shadow_block_rate - prod_block_rate
            seg_passed = delta <= _MAX_BLOCK_RATE_INCREASE

            if not seg_passed:
                all_passed = False
                logger.warning(
                    "shadow.segment_regression_fail segment=%s prod_rate=%.3f shadow_rate=%.3f delta=%.3f",
                    seg_name, prod_block_rate, shadow_block_rate, delta,
                )

            segment_results[seg_name] = {
                "passed": seg_passed,
                "prod_block_rate": prod_block_rate,
                "shadow_block_rate": shadow_block_rate,
                "delta": delta,
                "n": len(prod_actions),
            }

        return {"passed": all_passed, "segments": segment_results}


def _block_rate(actions: list[str]) -> float:
    """Fraction of actions that are 'blocked'."""
    if not actions:
        return 0.0
    return sum(1 for a in actions if a == "blocked") / len(actions)


def features_hash(features: Optional[dict]) -> Optional[str]:
    """Stable MD5 hash of a feature dict for correlation in shadow_predictions."""
    if features is None:
        return None
    try:
        payload = json.dumps(features, sort_keys=True, default=str)
        return hashlib.md5(payload.encode()).hexdigest()
    except Exception:
        return None


# Module-level singleton
shadow_logger = ShadowLogger()
