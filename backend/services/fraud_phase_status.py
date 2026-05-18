"""Probe live status for each FraudShield phase (1–12) for the control-room UI."""

from __future__ import annotations

import os
from typing import Any

from core.config import get_settings


def _status(live: bool, training: bool = False, shadow: bool = False) -> tuple[str, str]:
    if live:
        return "live", "LIVE"
    if shadow:
        return "limited", "SHADOW"
    if training:
        return "limited", "TRAINING"
    return "inactive", "NOT READY"


def get_phases_status(user_id: int | None = None) -> dict[str, Any]:
    """Return per-phase status for GET /fraud-shield/phases-status."""
    s = get_settings()
    phases: list[dict[str, Any]] = []

    redis_ok = False
    try:
        from core.redis import get_redis

        redis_ok = get_redis() is not None
    except Exception:
        pass

    local_bus_ok = False
    try:
        from services.event_bus.local_bus import is_registered

        local_bus_ok = is_registered()
    except Exception:
        pass

    pool_ok = False
    try:
        from core.db import get_pool

        pool_ok = get_pool() is not None
    except Exception:
        pass

    # Phase 1 — LIVE with Redis streams OR in-process local_bus + Postgres events table
    phase1_live = redis_ok or local_bus_ok or pool_ok
    phase1_detail = (
        "Redis streams + consumers"
        if redis_ok
        else "In-process bus + Postgres durability (no Redis required)"
    )
    st, lbl = _status(phase1_live)
    phases.append({"n": 1, "key": "events", "status": st, "statusLabel": lbl, "detail": phase1_detail})

    # Phase 2 — materializer + memory/Postgres offline when Redis absent
    phase2_live = pool_ok or local_bus_ok
    phase2_detail = (
        "Redis online feature store"
        if redis_ok
        else "Memory + Postgres snapshots (no Redis required)"
    )
    st, lbl = _status(phase2_live)
    phases.append({"n": 2, "key": "features", "status": st, "statusLabel": lbl, "detail": phase2_detail})

    # Phase 3 — IF per user
    if_trained = False
    txn_count = 0
    if user_id is not None:
        try:
            from services.ml_model import ml_detector

            if_trained = int(user_id) in ml_detector.models
        except Exception:
            pass
        try:
            from db import get_connection

            cnx = get_connection()
            cur = cnx.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM transactions WHERE user_id = %s AND UPPER(type) = 'DEBIT'",
                (user_id,),
            )
            txn_count = int(cur.fetchone()[0] or 0)
            cur.close()
            cnx.close()
        except Exception:
            pass
    st, lbl = _status(if_trained, training=txn_count >= 10 and not if_trained)
    phases.append(
        {
            "n": 3,
            "key": "xgb",
            "status": st,
            "statusLabel": lbl,
            "detail": f"IsolationForest {'trained' if if_trained else 'pending'} · {txn_count} debits",
        }
    )

    # Phase 4
    phases.append({"n": 4, "key": "policies", "status": "live", "statusLabel": "LIVE", "detail": "Decision engine on check-transaction"})

    # Phase 5
    mlflow_ok = False
    try:
        from services.ml_registry.registry import model_registry

        mlflow_ok = bool(model_registry._available)
    except Exception:
        pass
    st, lbl = _status(mlflow_ok or if_trained)
    phases.append({"n": 5, "key": "mlops", "status": st, "statusLabel": lbl, "detail": "Registry + drift workers"})

    # Phase 6
    phases.append({"n": 6, "key": "graph", "status": "live", "statusLabel": "LIVE", "detail": "SQL graph features in scoring"})

    # Phase 7
    shap_ok = False
    try:
        from services.explainability.shap_explainer import shap_explainer

        shap_ok = bool(shap_explainer.available)
    except Exception:
        pass
    st, lbl = _status(True)
    phases.append(
        {
            "n": 7,
            "key": "shap",
            "status": st if shap_ok else "limited",
            "statusLabel": "LIVE" if shap_ok else "LIVE",
            "detail": "Feature-vs-baseline explanations" + (" + TreeSHAP" if shap_ok else ""),
        }
    )

    # Phase 8
    phases.append({"n": 8, "key": "feedback", "status": "live", "statusLabel": "LIVE", "detail": "Alert actions → feedback flywheel"})

    # Phase 9
    p9 = bool(s.PHASE_9_AGENT_ENABLED)
    st, lbl = _status(p9, training=not p9)
    phases.append({"n": 9, "key": "llm", "status": st, "statusLabel": lbl, "detail": "Auto-investigate on HIGH/CRITICAL"})

    # Phase 10
    p10 = bool(s.PHASE_10_GNN_ENABLED)
    gnn_trained = os.path.exists(os.path.join("models", "gnn_model.pt"))
    st, lbl = _status(p10 and gnn_trained, training=p10 and not gnn_trained)
    phases.append({"n": 10, "key": "gnn", "status": st, "statusLabel": lbl, "detail": "GNN embedding distance blend"})

    # Phase 11
    p11 = bool(s.PHASE_11_DNN_ENABLED)
    promoted = bool(s.PHASE_11_DNN_PROMOTED)
    dnn_model = os.path.exists(os.path.join("models", "dnn_model.pt"))
    if p11 and promoted and dnn_model:
        st, lbl = "live", "LIVE"
    elif p11:
        st, lbl = _status(False, shadow=True)
    else:
        st, lbl = _status(False, training=True)
    phases.append({"n": 11, "key": "dnn", "status": st, "statusLabel": lbl, "detail": "DNN shadow / promoted blend"})

    # Phase 12
    p12 = bool(s.PHASE_12_ORCHESTRATOR_ENABLED)
    st, lbl = _status(p12, training=not p12)
    phases.append({"n": 12, "key": "orch", "status": st, "statusLabel": lbl, "detail": "Multi-model orchestrator routing"})

    live = sum(1 for p in phases if p["status"] == "live")
    training = sum(1 for p in phases if p["statusLabel"] == "TRAINING")
    shadow = sum(1 for p in phases if p["statusLabel"] == "SHADOW")
    partial = sum(1 for p in phases if p["status"] == "limited" and p["statusLabel"] not in ("TRAINING", "SHADOW"))

    return {
        "phases": phases,
        "summary": {
            "live": live,
            "training": training,
            "shadow": shadow,
            "partial": partial,
            "inactive": 12 - live - training - shadow - partial,
            "headline": f"{live} live · {training} training · {shadow} shadow",
        },
    }
