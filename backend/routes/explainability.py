"""Explainability routes — full SHAP breakdowns and similar-transaction lookup.

Phase 7: SHAP Explainability.
Dependencies: shap_explainer (Phase 7), offline_store (Phase 2), asyncpg pool (Phase 1),
              admin auth via X-Admin-Token (Phase 4).
Performance budget: /explain may take 30–80ms (SHAP + feature reconstruction);
                    /similar is a DB query, typically < 20ms.

Endpoints:
  GET /api/transactions/{id}/explain  — full SHAP attribution (admin only).
  GET /api/transactions/{id}/similar  — 10 most similar transactions by features.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transactions", tags=["explainability"])


# ------------------------------------------------------------------ #
# Auth dependency (same token as admin routes)
# ------------------------------------------------------------------ #

def _require_admin(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Verify the X-Admin-Token header.  Raises 403 if invalid."""
    import os
    expected = os.getenv("ADMIN_TOKEN", "dev-admin-secret")
    if x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Token header")


# ------------------------------------------------------------------ #
# Explain endpoint
# ------------------------------------------------------------------ #

@router.get("/{txn_id}/explain", dependencies=[Depends(_require_admin)])
async def explain_transaction(txn_id: int) -> dict[str, Any]:
    """Return a full SHAP explanation for a past transaction.

    Reconstructs the feature vector from:
      1. The transaction's stored attributes (amount, hour, merchant, etc.).
      2. The offline feature store snapshot at transaction time (Phase 2).
    Then runs SHAP on the reconstructed vector and returns all feature
    attributions, sorted by absolute SHAP value.

    Args:
        txn_id: Postgres transaction primary key.

    Returns:
        Dict with transaction summary, feature vector, and full SHAP breakdown.
        Returns {"available": false} when supervised model or SHAP not ready.
    """
    from core.db import get_pool
    from ml_training.feature_engineering import (
        SUPERVISED_FEATURE_COLUMNS,
        assembled_to_feature_vector,
    )
    from services.explainability.shap_explainer import shap_explainer
    from services.feature_store.offline_store import offline_feature_store
    from services.feature_store.feature_assembly import FeatureAssembler

    # ---- Fetch transaction record ---- #
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool unavailable")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, amount, merchant, category, hour_of_day,
                   day_of_week, is_weekend, payment_method, location,
                   transaction_date, transaction_time, type,
                   risk_score, risk_level, anomaly_flag, anomaly_reason,
                   is_fraud
            FROM   transactions
            WHERE  id = $1
            """,
            txn_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail=f"Transaction {txn_id} not found")

    txn_dict = dict(row)

    # ---- Reconstruct feature vector ---- #
    # Try offline store (point-in-time snapshot from Phase 2)
    assembled: dict[str, Any] = {}
    try:
        from datetime import timezone
        at_time = None
        if row["transaction_date"] and row["transaction_time"]:
            from datetime import datetime
            at_time = datetime.combine(
                row["transaction_date"], row["transaction_time"]
            ).replace(tzinfo=timezone.utc)

        if at_time is not None:
            offline_feats = await offline_feature_store.get_at_time(
                "user", str(row["user_id"]), at_time
            )
            if offline_feats:
                assembled.update({f"user_{k}": v for k, v in offline_feats.items()})
    except Exception as exc:
        logger.debug("explain: offline feature retrieval failed: %s", exc)

    # Fill transaction-level features from the transaction record itself
    assembler = FeatureAssembler()
    try:
        txn_feats = assembler._compute_txn_features(txn_dict, assembled)
        for k, v in txn_feats.items():
            assembled[f"txn_{k}"] = v
        assembled["amt_ratio_30d"] = txn_feats.get("amount_vs_user_avg_30d", 1.0)
        assembled["merchant_changed"] = txn_feats.get("is_new_merchant", 0.0)
    except Exception as exc:
        logger.debug("explain: txn feature computation failed: %s", exc)

    # Convert to supervised feature vector
    try:
        feat_vec = assembled_to_feature_vector(assembled)
    except Exception as exc:
        logger.warning("explain: feature vector build failed: %s", exc)
        feat_vec = np.zeros(len(SUPERVISED_FEATURE_COLUMNS))

    # ---- SHAP explanation ---- #
    if not shap_explainer.available:
        return {
            "transaction_id": txn_id,
            "available":      False,
            "reason":         "SHAP explainer not ready (no supervised model loaded)",
            "transaction":    _txn_summary(txn_dict),
        }

    shap_result = shap_explainer.explain_full(feat_vec, SUPERVISED_FEATURE_COLUMNS)

    return {
        "transaction_id":   txn_id,
        "transaction":      _txn_summary(txn_dict),
        "shap_explanation": shap_result,
        "feature_vector":   [
            {"feature": name, "value": float(feat_vec[i]) if i < len(feat_vec) else 0.0}
            for i, name in enumerate(SUPERVISED_FEATURE_COLUMNS)
        ],
    }


# ------------------------------------------------------------------ #
# Similar transactions endpoint
# ------------------------------------------------------------------ #

@router.get("/{txn_id}/similar", dependencies=[Depends(_require_admin)])
async def similar_transactions(
    txn_id: int,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    """Find the `limit` most similar past transactions by feature proximity.

    Similarity is computed using a lightweight composite score based on:
      - Same category (binary match)
      - Amount within 2× of the target
      - Same day-of-week
      - Same payment method
    This avoids the need to store full feature vectors per transaction, while
    still returning meaningful contextual neighbors for fraud analysis.

    For production use, store SUPERVISED_FEATURE_COLUMNS vectors in a
    pgvector column and use cosine similarity (Phase 9 roadmap).

    Args:
        txn_id: Reference transaction.
        limit:  Max results (1–50, default 10).
    """
    from core.db import get_pool

    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool unavailable")

    async with pool.acquire() as conn:
        # Fetch reference transaction
        ref = await conn.fetchrow(
            "SELECT id, user_id, amount, category, payment_method, "
            "day_of_week, hour_of_day, merchant, risk_score, is_fraud "
            "FROM transactions WHERE id = $1",
            txn_id,
        )
        if ref is None:
            raise HTTPException(status_code=404, detail=f"Transaction {txn_id} not found")

        ref_amount = float(ref["amount"] or 0)
        ref_category = ref["category"] or ""
        ref_payment = ref["payment_method"] or ""
        ref_dow = ref["day_of_week"]
        ref_hour = ref["hour_of_day"]

        amount_lo = ref_amount / 2.0
        amount_hi = ref_amount * 2.0

        # Find candidate similar transactions (DB-side pre-filter)
        rows = await conn.fetch(
            """
            SELECT id, user_id, amount, category, payment_method,
                   day_of_week, hour_of_day, merchant,
                   risk_score, risk_level, is_fraud,
                   transaction_date, transaction_time
            FROM   transactions
            WHERE  id != $1
              AND  amount BETWEEN $2 AND $3
              AND  category = $4
            ORDER  BY ABS(amount - $5) ASC
            LIMIT  $6
            """,
            txn_id, amount_lo, amount_hi, ref_category, ref_amount, limit * 3,
        )

    # Python-side ranking: compute simple similarity score
    def _sim(row: dict) -> float:
        s = 0.0
        # Amount closeness (normalised)
        if ref_amount > 0:
            s += 1.0 - min(abs(float(row["amount"]) - ref_amount) / ref_amount, 1.0)
        # Feature matches
        if row["payment_method"] == ref_payment:
            s += 0.5
        if row["day_of_week"] == ref_dow:
            s += 0.3
        if row["hour_of_day"] is not None and abs((row["hour_of_day"] or 0) - (ref_hour or 0)) <= 2:
            s += 0.2
        if row["merchant"] == ref["merchant"]:
            s += 0.3
        return s

    ranked = sorted([dict(r) for r in rows], key=_sim, reverse=True)[:limit]

    return {
        "reference_txn_id": txn_id,
        "reference": {
            "amount":    ref_amount,
            "category":  ref_category,
            "merchant":  ref["merchant"],
            "risk_score": ref["risk_score"],
        },
        "similar_count": len(ranked),
        "similar_transactions": [
            {
                "id":             r["id"],
                "user_id":        r["user_id"],
                "amount":         float(r["amount"]),
                "category":       r["category"],
                "merchant":       r["merchant"],
                "payment_method": r["payment_method"],
                "risk_score":     r["risk_score"],
                "risk_level":     r["risk_level"],
                "is_fraud":       r["is_fraud"],
                "date":           str(r["transaction_date"]) if r["transaction_date"] else None,
            }
            for r in ranked
        ],
    }


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _txn_summary(row: dict) -> dict[str, Any]:
    """Return a clean summary of a transaction row for API responses."""
    return {
        "id":             row.get("id"),
        "user_id":        row.get("user_id"),
        "amount":         float(row.get("amount") or 0),
        "merchant":       row.get("merchant"),
        "category":       row.get("category"),
        "payment_method": row.get("payment_method"),
        "hour_of_day":    row.get("hour_of_day"),
        "day_of_week":    row.get("day_of_week"),
        "risk_score":     row.get("risk_score"),
        "risk_level":     row.get("risk_level"),
        "is_fraud":       row.get("is_fraud"),
    }
