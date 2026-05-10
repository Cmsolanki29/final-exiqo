"""Admin API routes — merchant risk configuration, blacklist management, and MLOps.

Phase 4: Decision Engine adds merchant config and blacklist endpoints.
Phase 5: MLOps adds model registry, promotion, rollback, drift reports, shadow reports,
         and a /metrics Prometheus endpoint.

Auth: X-Admin-Token header checked against ADMIN_TOKEN env var.
      Phase 4 uses a simple header check.  Real JWT/RBAC in a future hardening pass.

All endpoints are under /api/admin/ prefix (registered in main.py).

Performance budget: all endpoints are admin/backoffice — no hard latency target,
                    but DB calls use asyncpg to avoid blocking the event loop.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from services.decision_engine import decision_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------------------------------------------ #
# Auth dependency
# ------------------------------------------------------------------ #

def _require_admin(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> None:
    """FastAPI dependency: validates the X-Admin-Token header.

    Raises HTTP 403 if the token is missing or incorrect.
    The expected value is the ADMIN_TOKEN env var (default 'dev-admin-secret').
    """
    expected = os.getenv("ADMIN_TOKEN", "dev-admin-secret")
    if x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Token header")


# ------------------------------------------------------------------ #
# Request / Response schemas (admin-specific, not shared)
# ------------------------------------------------------------------ #

class MerchantRiskConfigPatch(BaseModel):
    """Request body for PATCH /api/admin/merchants/{id}/risk-config."""
    block_threshold: int = Field(default=80, ge=0, le=100)
    challenge_threshold: int = Field(default=60, ge=0, le=100)
    review_threshold: int = Field(default=40, ge=0, le=100)
    custom_rules: dict = Field(default_factory=dict)


class BlacklistAddRequest(BaseModel):
    """Request body for POST /api/admin/blacklist."""
    entity_type: str = Field(
        description="One of: merchant, device, ip, card, user, location"
    )
    entity_value: str = Field(description="Entity identifier string")
    reason: str = Field(description="Human-readable reason for the block")
    severity: str = Field(default="HIGH", description="LOW | MEDIUM | HIGH | CRITICAL")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional expiry datetime (null = permanent)",
    )


# ------------------------------------------------------------------ #
# Merchant risk config endpoints
# ------------------------------------------------------------------ #

@router.get("/merchants/{merchant_id}/risk-config", dependencies=[Depends(_require_admin)])
async def get_merchant_risk_config(merchant_id: str) -> dict:
    """Fetch the risk configuration for a specific merchant.

    Returns the custom config if one exists, or the global defaults if not.
    """
    try:
        config = await decision_engine.get_merchant_config(merchant_id)
        if config is None:
            return {
                "merchant_id": merchant_id,
                "block_threshold": 80,
                "challenge_threshold": 60,
                "review_threshold": 40,
                "custom_rules": {},
                "source": "global_default",
            }
        return {**dict(config), "source": "custom"}
    except Exception as exc:
        logger.exception("get_merchant_risk_config failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/merchants/{merchant_id}/risk-config", dependencies=[Depends(_require_admin)])
async def update_merchant_risk_config(
    merchant_id: str, body: MerchantRiskConfigPatch
) -> dict:
    """Create or update risk thresholds for a specific merchant.

    Changes take effect within the Redis cache TTL (5 minutes).
    """
    if body.block_threshold <= body.challenge_threshold:
        raise HTTPException(
            status_code=400,
            detail="block_threshold must be > challenge_threshold",
        )
    if body.challenge_threshold <= body.review_threshold:
        raise HTTPException(
            status_code=400,
            detail="challenge_threshold must be > review_threshold",
        )
    try:
        await decision_engine.upsert_merchant_config(
            merchant_id=merchant_id,
            block_threshold=body.block_threshold,
            challenge_threshold=body.challenge_threshold,
            review_threshold=body.review_threshold,
            custom_rules=body.custom_rules,
        )
        return {
            "status": "updated",
            "merchant_id": merchant_id,
            "block_threshold": body.block_threshold,
            "challenge_threshold": body.challenge_threshold,
            "review_threshold": body.review_threshold,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("update_merchant_risk_config failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------ #
# Blacklist endpoints
# ------------------------------------------------------------------ #

@router.post("/blacklist", status_code=201, dependencies=[Depends(_require_admin)])
async def add_to_blacklist(body: BlacklistAddRequest) -> dict:
    """Add an entity to the hard-block blacklist.

    Existing entries for the same (entity_type, entity_value) pair are
    updated (upsert semantics).
    """
    valid_types = {"merchant", "device", "ip", "card", "user", "location"}
    if body.entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"entity_type must be one of: {', '.join(sorted(valid_types))}",
        )
    try:
        entity_id = await decision_engine.add_to_blacklist(
            entity_type=body.entity_type,
            entity_value=body.entity_value,
            reason=body.reason,
            severity=body.severity,
            expires_at=body.expires_at,
        )
        return {
            "status": "added",
            "id": entity_id,
            "entity_type": body.entity_type,
            "entity_value": body.entity_value,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("add_to_blacklist failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/blacklist/{entity_id}", dependencies=[Depends(_require_admin)])
async def remove_from_blacklist(entity_id: int) -> dict:
    """Remove a blacklist entry by its primary key id."""
    try:
        deleted = await decision_engine.remove_from_blacklist(entity_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Blacklist entry {entity_id} not found")
        return {"status": "deleted", "id": entity_id}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("remove_from_blacklist failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/blacklist", dependencies=[Depends(_require_admin)])
async def list_blacklist(
    entity_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List all blacklisted entities (paginated).

    Args:
        entity_type: Optional filter by entity type.
        limit:       Page size (max 1000).
        offset:      Pagination offset.
    """
    try:
        from core.db import get_pool
        pool = get_pool()
        if pool is None:
            raise HTTPException(status_code=503, detail="Database unavailable")

        async with pool.acquire() as conn:
            if entity_type:
                rows = await conn.fetch(
                    """
                    SELECT id, entity_type, entity_value, reason, severity, added_at, expires_at
                    FROM   blacklisted_entities
                    WHERE  entity_type = $1
                    ORDER  BY added_at DESC
                    LIMIT  $2 OFFSET $3
                    """,
                    entity_type, limit, offset,
                )
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM blacklisted_entities WHERE entity_type = $1",
                    entity_type,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, entity_type, entity_value, reason, severity, added_at, expires_at
                    FROM   blacklisted_entities
                    ORDER  BY added_at DESC
                    LIMIT  $1 OFFSET $2
                    """,
                    limit, offset,
                )
                total = await conn.fetchval("SELECT COUNT(*) FROM blacklisted_entities")

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": r["id"],
                    "entity_type": r["entity_type"],
                    "entity_value": r["entity_value"],
                    "reason": r["reason"],
                    "severity": r["severity"],
                    "added_at": r["added_at"].isoformat() if r["added_at"] else None,
                    "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
                }
                for r in rows
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("list_blacklist failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------ #
# Phase 5: Model registry + MLOps endpoints
# ------------------------------------------------------------------ #

class ModelPromoteRequest(BaseModel):
    """Request body for POST /api/admin/models/{name}/{version}/promote."""
    stage: str = Field(
        default="production",
        description="Target stage: shadow | canary | production | archived",
    )
    traffic_percentage: int = Field(default=0, ge=0, le=100)
    promoted_by: Optional[str] = Field(default=None)


@router.get("/models", dependencies=[Depends(_require_admin)])
async def list_models(name: str = Query(default="smartspend_fraud_xgb")) -> dict:
    """List all registered model versions with MLflow stages and deployment metadata.

    Returns versions from MLflow registry plus current_versions summary.
    """
    from services.ml_registry.registry import model_registry
    all_versions = model_registry.list_all_versions(name)
    current = model_registry.current_versions(name)
    return {
        "model_name": name,
        "current_versions": current,
        "all_versions": all_versions,
        "registry_available": model_registry._available,
    }


@router.post("/models/{name}/{version}/promote", dependencies=[Depends(_require_admin)])
async def promote_model(name: str, version: str, body: ModelPromoteRequest) -> dict:
    """Manually promote a model version to a stage.

    Example: promote v3 to canary at 10% traffic:
        POST /api/admin/models/smartspend_fraud_xgb/3/promote
        body: {"stage": "canary", "traffic_percentage": 10}
    """
    valid_stages = {"shadow", "canary", "production", "archived"}
    if body.stage not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"stage must be one of: {', '.join(sorted(valid_stages))}",
        )
    from services.ml_registry.registry import model_registry
    ok = model_registry.promote(
        name, version, body.stage,
        promoted_by=body.promoted_by,
        traffic_percentage=body.traffic_percentage,
    )
    if not ok:
        raise HTTPException(status_code=502, detail="MLflow promotion failed — check registry availability")

    # Hot-reload if promoting to production or shadow
    if body.stage in ("production", "shadow", "canary"):
        from services.hybrid_scorer import hybrid_scorer
        hybrid_scorer.reload_models()

    return {
        "status": "promoted",
        "model_name": name,
        "version": version,
        "stage": body.stage,
        "traffic_percentage": body.traffic_percentage,
    }


@router.post("/models/{name}/rollback", dependencies=[Depends(_require_admin)])
async def rollback_model(name: str) -> dict:
    """Emergency rollback: archive current Production, promote previous Staging to Production.

    Use when a recently promoted model is causing elevated block rates or errors.
    """
    from services.ml_registry.registry import model_registry
    ok = model_registry.rollback(name)
    if not ok:
        raise HTTPException(status_code=502, detail="Rollback failed — check registry")

    # Reload with the rolled-back model
    from services.hybrid_scorer import hybrid_scorer
    hybrid_scorer.reload_models()

    return {"status": "rolled_back", "model_name": name}


@router.post("/models/reload", dependencies=[Depends(_require_admin)])
async def reload_models() -> dict:
    """Hot-reload all models (production, shadow, canary) from MLflow registry.

    Use after manual MLflow stage changes or when the scorer needs refreshing.
    """
    from services.hybrid_scorer import hybrid_scorer
    hybrid_scorer.reload_models()
    return {
        "status": "reloaded",
        "has_supervised": hybrid_scorer.has_supervised_model,
        "has_shadow": hybrid_scorer.has_shadow_model,
    }


# ------------------------------------------------------------------ #
# Phase 5: Drift + shadow reports
# ------------------------------------------------------------------ #

@router.get("/drift-report", dependencies=[Depends(_require_admin)])
async def get_drift_report(
    limit: int = Query(default=50, ge=1, le=500),
    feature_name: Optional[str] = Query(default=None),
) -> dict:
    """Latest PSI drift report from drift_reports table.

    Returns the most recent drift check results per feature.
    Filter by feature_name for a specific feature's history.
    """
    from core.db import get_pool
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        async with pool.acquire() as conn:
            if feature_name:
                rows = await conn.fetch(
                    """
                    SELECT feature_name, psi_value, kl_divergence, computed_at, alert_triggered
                    FROM   drift_reports
                    WHERE  feature_name = $1
                    ORDER  BY computed_at DESC
                    LIMIT  $2
                    """,
                    feature_name, limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (feature_name)
                           feature_name, psi_value, kl_divergence, computed_at, alert_triggered
                    FROM   drift_reports
                    ORDER  BY feature_name, computed_at DESC
                    LIMIT  $1
                    """,
                    limit,
                )
        items = [
            {
                "feature_name": r["feature_name"],
                "psi_value": float(r["psi_value"]),
                "kl_divergence": float(r["kl_divergence"]),
                "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
                "alert_triggered": r["alert_triggered"],
            }
            for r in rows
        ]
        high_drift = [i for i in items if i["psi_value"] > 0.25]
        return {
            "total_features": len(items),
            "high_drift_features": len(high_drift),
            "threshold": 0.25,
            "items": items,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_drift_report failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/shadow-report", dependencies=[Depends(_require_admin)])
async def get_shadow_report(period_days: int = Query(default=7, ge=1, le=30)) -> dict:
    """Latest shadow model comparison report.

    Compares production vs. shadow model scores over the last period_days.
    Calls ShadowLogger.evaluate_shadow() which performs statistical tests.
    """
    from services.monitoring.shadow_logger import shadow_logger
    report = await shadow_logger.evaluate_shadow(period_days=period_days)
    return report


@router.get("/drift-run", dependencies=[Depends(_require_admin)])
async def trigger_drift_check() -> dict:
    """Manually trigger an immediate drift check (outside normal hourly schedule).

    Useful after a deployment or suspicious alert.
    """
    from workers.drift_monitor_worker import drift_monitor_worker
    import asyncio
    asyncio.create_task(drift_monitor_worker._run_drift_check())
    return {"status": "triggered", "message": "Drift check running in background"}


# ------------------------------------------------------------------ #
# Phase 6: Graph / Network analysis endpoints
# ------------------------------------------------------------------ #

@router.get("/users/{user_id}/network", dependencies=[Depends(_require_admin)])
async def get_user_network(user_id: int) -> dict:
    """Return adjacent users and shared entities for a fraud analyst.

    Shows which merchants, devices, and IPs this user shares with other users,
    how many direct neighbors they have, and whether any neighbors are confirmed
    fraud users.

    This is the primary endpoint for manual fraud investigation: the analyst
    opens a suspicious user's profile and sees their full network context.

    Args:
        user_id: Postgres user primary key.
    """
    from services.graph.graph_features import graph_feature_service
    result = await graph_feature_service.get_network_summary(user_id)
    if "error" in result and result["error"] == "database_unavailable":
        raise HTTPException(status_code=503, detail="Database unavailable")
    return result


@router.get("/users/{user_id}/fraud-distance", dependencies=[Depends(_require_admin)])
async def get_fraud_distance(user_id: int) -> dict:
    """Return shortest path distance to nearest confirmed-fraud user.

    A distance of:
      0  → user themselves has confirmed fraud transactions
      1  → user shares a merchant with a confirmed-fraud user
      2  → user is two merchant-hops from a fraud user
      -1 → no path found within 2 hops (low-risk network position)

    Used by fraud analysts to quickly triage: users at distance 1 warrant
    closer scrutiny even if their current transaction looks normal.

    Args:
        user_id: Postgres user primary key.
    """
    from services.graph.graph_features import graph_feature_service
    result = await graph_feature_service.get_fraud_distance(user_id)
    if "error" in result and result.get("error") == "database_unavailable":
        raise HTTPException(status_code=503, detail="Database unavailable")
    return result


@router.get("/users/{user_id}/fraud-ring", dependencies=[Depends(_require_admin)])
async def get_fraud_ring(
    user_id: int,
    depth: int = Query(default=2, ge=1, le=3),
) -> dict:
    """Find connected fraud users within `depth` hops.

    Returns user IDs who are reachable from user_id via shared
    merchant/device/IP edges AND have at least one confirmed fraud transaction.

    Args:
        user_id: Starting user.
        depth:   Max hops (1–3, default 2).
    """
    from services.graph.graph_features import graph_feature_service
    ring = await graph_feature_service.find_fraud_ring(user_id, depth=depth)
    return {
        "user_id": user_id,
        "depth": depth,
        "fraud_ring_size": len(ring),
        "fraud_user_ids": ring,
    }
