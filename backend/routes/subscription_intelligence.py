"""
Subscription Intelligence API — device usage, verdicts, substitutions, reminders.
SIMULATED: real impl uses Android UsageStatsManager via companion mobile SDK (device_links + app_usage_signals are seeded).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import get_db
from routes.subscription_graveyard import build_subscription_dashboard
from services.subscription_intelligence.schema_bootstrap import ensure_subscription_intelligence_schema
from services.subscription_intelligence import (
    apply_reminder_action,
    detect_substitutions,
    evaluate_subscription,
    fetch_recommendation_paragraph,
    persist_verdict,
    schedule_reminders_for_subscription,
    simulate_next_day,
)
from services.subscription_intelligence.reminder_scheduler import fetch_pending_reminders

router = APIRouter(prefix="/subscription-intelligence", tags=["Subscription Intelligence"])


def subscription_intel_connection(conn=Depends(get_db)):
    """Ensure migration 021 DDL exists before any subscription-intelligence query."""
    ensure_subscription_intelligence_schema(conn)
    return conn


class DeviceLinkBody(BaseModel):
    # SIMULATED: production version uses Android UsageStatsManager via companion mobile SDK
    device_type: str = Field(default="simulated", description="android | ios | simulated")
    permissions: dict[str, bool] = Field(default_factory=dict)
    apps_linked: list[str] = Field(default_factory=list)


class ReminderActionBody(BaseModel):
    action: str = Field(..., description="cancel_now | remind_later | keep")


def _device_row(conn, user_id: int) -> dict[str, Any] | None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, linked_at, device_type, permissions, apps_linked, link_status
            FROM device_links WHERE user_id = %s AND link_status = 'active' LIMIT 1;
            """,
            (user_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        perms = r[3]
        apps = r[4]
        if isinstance(perms, str):
            perms = json.loads(perms)
        if isinstance(apps, str):
            apps = json.loads(apps)
        return {
            "id": r[0],
            "linked_at": r[1].isoformat() if r[1] else None,
            "device_type": r[2],
            "permissions": perms,
            "apps_linked": apps or [],
            "link_status": r[5],
        }
    finally:
        cur.close()


def _intel_rows(conn, user_id: int) -> dict[int, dict[str, Any]]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, merchant, monthly_cost, intelligence_category, linked_app_package,
                   current_verdict, verdict_confidence, verdict_reason, verdict_monthly_waste,
                   next_billing_date, billing_day, sub_lifecycle, is_pro, last_evaluated_at
            FROM subscriptions WHERE user_id = %s ORDER BY merchant;
            """,
            (user_id,),
        )
        out: dict[int, dict[str, Any]] = {}
        for row in cur.fetchall():
            sid = int(row[0])
            out[sid] = {
                "id": sid,
                "merchant": row[1],
                "monthly_cost_intel": float(row[2] or 0),
                "intelligence_category": row[3],
                "linked_app_package": row[4],
                "current_verdict": row[5],
                "verdict_confidence": row[6],
                "verdict_reason": row[7],
                "verdict_monthly_waste": float(row[8] or 0),
                "next_billing_date": row[9].isoformat() if row[9] else None,
                "billing_day": row[10],
                "sub_lifecycle": row[11],
                "is_pro": bool(row[12]) if row[12] is not None else False,
                "last_evaluated_at": row[13].isoformat() if row[13] else None,
            }
        return out
    finally:
        cur.close()


def _merge_by_merchant(subs_list: list[dict], by_id: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    by_merchant = {v["merchant"]: v for v in by_id.values()}
    merged = []
    for s in subs_list:
        m = s.get("merchant")
        row = by_merchant.get(m)
        base = {**s}
        if row:
            base.update(
                {
                    "subscription_id": row["id"],
                    "intelligence_category": row.get("intelligence_category"),
                    "linked_app_package": row.get("linked_app_package"),
                    "current_verdict": row.get("current_verdict"),
                    "verdict_confidence": row.get("verdict_confidence"),
                    "verdict_reason": row.get("verdict_reason"),
                    "verdict_monthly_waste": row.get("verdict_monthly_waste"),
                    "next_billing_date": row.get("next_billing_date"),
                    "billing_day": row.get("billing_day"),
                    "sub_lifecycle": row.get("sub_lifecycle"),
                    "is_pro": row.get("is_pro"),
                    "last_evaluated_at": row.get("last_evaluated_at"),
                }
            )
        merged.append(base)
    return merged


def _usage_rollups(conn, user_id: int, since: date) -> dict[str, list[dict[str, Any]]]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT app_package, signal_date, usage_minutes
            FROM app_usage_signals
            WHERE user_id = %s AND signal_date >= %s
            ORDER BY app_package, signal_date;
            """,
            (user_id, since),
        )
        by_pkg: dict[str, list[dict[str, Any]]] = {}
        for pkg, sd, um in cur.fetchall():
            by_pkg.setdefault(str(pkg), []).append({"d": sd.isoformat(), "m": int(um or 0)})
        return by_pkg
    finally:
        cur.close()


def _waste_ledger_yearly(conn, user_id: int) -> float:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(verdict_monthly_waste), 0)::float
            FROM subscriptions WHERE user_id = %s;
            """,
            (user_id,),
        )
        return float(cur.fetchone()[0] or 0) * 12.0
    finally:
        cur.close()


@router.get("/{user_id}/hub")
def intelligence_hub(user_id: int, conn=Depends(subscription_intel_connection)):
    base = build_subscription_dashboard(user_id, conn)
    by_id = _intel_rows(conn, user_id)
    device = _device_row(conn, user_id)
    merged = _merge_by_merchant(base.get("subscriptions") or [], by_id)
    seen_m = {s["merchant"] for s in merged}
    for row in by_id.values():
        if row["merchant"] not in seen_m:
            merged.append(
                {
                    "merchant": row["merchant"],
                    "amount": row["monthly_cost_intel"],
                    "billing_cycle": "MONTHLY",
                    "category": row.get("intelligence_category") or "other",
                    "status": "SUSPICIOUS",
                    "usage_score": 50,
                    "last_used_days": 14,
                    "monthly_cost": row["monthly_cost_intel"],
                    "times_charged": 3,
                    "first_charged": (date.today() - timedelta(days=120)).isoformat(),
                    "last_charged": (date.today() - timedelta(days=3)).isoformat(),
                    "insight": "Device-intelligence row (bank scan may not yet cluster this merchant).",
                    "subscription_id": row["id"],
                    "intelligence_category": row.get("intelligence_category"),
                    "linked_app_package": row.get("linked_app_package"),
                    "current_verdict": row.get("current_verdict"),
                    "verdict_confidence": row.get("verdict_confidence"),
                    "verdict_reason": row.get("verdict_reason"),
                    "verdict_monthly_waste": row.get("verdict_monthly_waste"),
                    "next_billing_date": row.get("next_billing_date"),
                    "billing_day": row.get("billing_day"),
                    "sub_lifecycle": row.get("sub_lifecycle"),
                    "is_pro": row.get("is_pro"),
                    "last_evaluated_at": row.get("last_evaluated_at"),
                }
            )
            seen_m.add(row["merchant"])
    roll = _usage_rollups(conn, user_id, date.today() - timedelta(days=89))
    for s in merged:
        pkg = s.get("linked_app_package")
        if pkg and pkg in roll:
            s["usage_series"] = roll[pkg][-45:]
    subs = fetch_pending_reminders(conn, user_id)
    substitutions: list[dict[str, Any]] = []
    try:
        substitutions = detect_substitutions(conn, user_id)
    except Exception:
        substitutions = []
    yearly = round(_waste_ledger_yearly(conn, user_id), 2)
    monthly_intel = round(sum(float(r.get("verdict_monthly_waste") or 0) for r in by_id.values()), 2)
    discovery_total = round(sum(float(s.get("monthly_cost") or 0) for s in merged), 2)
    return {
        "discovery": {
            "count": len(merged),
            "monthly_total_inr": discovery_total,
            "message": f"We found {len(merged)} subscriptions across your account — ₹{discovery_total:,.0f}/month.",
        },
        "device_linked": device is not None,
        "device": device,
        "subscriptions": merged,
        "substitutions": substitutions,
        "pending_reminders": subs,
        "waste_ledger_yearly_saved_inr": yearly,
        "verdict_monthly_waste_sum_inr": monthly_intel,
        "legacy": {"ai_advice": base.get("ai_advice"), "cancel_guide": base.get("cancel_guide")},
    }


@router.post("/{user_id}/device-link")
def post_device_link(user_id: int, body: DeviceLinkBody, conn=Depends(subscription_intel_connection)):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO device_links (user_id, device_type, permissions, apps_linked, link_status)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, 'active')
            ON CONFLICT (user_id) DO UPDATE SET
              linked_at = NOW(),
              device_type = EXCLUDED.device_type,
              permissions = EXCLUDED.permissions,
              apps_linked = EXCLUDED.apps_linked,
              link_status = 'active';
            """,
            (
                user_id,
                body.device_type,
                json.dumps(body.permissions or {}),
                json.dumps(body.apps_linked or []),
            ),
        )
    finally:
        cur.close()
    from services.subscription_intelligence.seed_demo import run_seed_for_user

    run_seed_for_user(conn, user_id, wipe_device=False)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM subscriptions WHERE user_id=%s ORDER BY id;", (user_id,))
        sids = [r[0] for r in cur.fetchall()]
    finally:
        cur.close()
    for sid in sids:
        vr = evaluate_subscription(conn, sid)
        if vr is not None:
            persist_verdict(conn, sid, vr)
            schedule_reminders_for_subscription(conn, sid, escalation_level=1)
    return {"ok": True, "device": _device_row(conn, user_id), "evaluated_subscriptions": len(sids)}


@router.post("/{user_id}/subscriptions/{subscription_id}/evaluate")
def post_evaluate(user_id: int, subscription_id: int, conn=Depends(subscription_intel_connection)):
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM subscriptions WHERE id = %s;", (subscription_id,))
        r = cur.fetchone()
        if not r or int(r[0]) != user_id:
            raise HTTPException(status_code=404, detail="Subscription not found")
    finally:
        cur.close()
    vr = evaluate_subscription(conn, subscription_id)
    if not vr:
        raise HTTPException(status_code=400, detail="Could not evaluate")
    persist_verdict(conn, subscription_id, vr)
    schedule_reminders_for_subscription(conn, subscription_id, escalation_level=1)
    return {
        "verdict": vr.verdict,
        "confidence": vr.confidence,
        "reason": vr.reason,
        "monthly_waste": vr.monthly_waste,
        "substitution": vr.substitution,
    }


@router.get("/{user_id}/subscriptions/{subscription_id}/recommendation")
def get_recommendation(user_id: int, subscription_id: int, conn=Depends(subscription_intel_connection)):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT merchant, monthly_cost, intelligence_category, current_verdict, verdict_reason, linked_app_package
            FROM subscriptions WHERE id = %s AND user_id = %s;
            """,
            (subscription_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        merchant, monthly_cost, cat, verdict, reason, pkg = row
    finally:
        cur.close()
    today = date.today()
    d0 = today - timedelta(days=30)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(usage_minutes), 0)::bigint
            FROM app_usage_signals WHERE user_id = %s AND app_package = %s AND signal_date >= %s;
            """,
            (user_id, pkg or "", d0),
        )
        mins = int(cur.fetchone()[0] or 0)
    finally:
        cur.close()
    usage_summary = f"Last 30d in-app time ≈ {mins} minutes ({mins/60:.1f} hours)."
    sub_name = str(merchant)
    substitute_name = None
    if verdict == "dead" and pkg:
        try:
            subs = detect_substitutions(conn, user_id)
            for s in subs:
                if int(s.get("subscription_id") or 0) == subscription_id:
                    substitute_name = s.get("to_package")
                    break
        except Exception:
            substitute_name = None
    paragraph = fetch_recommendation_paragraph(
        name=sub_name,
        monthly_cost=float(monthly_cost or 0),
        category=str(cat or "other"),
        verdict=str(verdict or "declining"),
        reason=str(reason or ""),
        usage_summary=usage_summary,
        substitute_name=substitute_name,
    )
    return {"paragraph": paragraph}


@router.get("/{user_id}/substitutions")
def get_substitutions(user_id: int, conn=Depends(subscription_intel_connection)):
    return {"insights": detect_substitutions(conn, user_id)}


@router.get("/{user_id}/reminders/pending")
def get_reminders(user_id: int, conn=Depends(subscription_intel_connection)):
    return {"reminders": fetch_pending_reminders(conn, user_id)}


@router.post("/{user_id}/reminders/{reminder_id}/action")
def post_reminder_action(user_id: int, reminder_id: int, body: ReminderActionBody, conn=Depends(subscription_intel_connection)):
    return apply_reminder_action(conn, reminder_id, user_id, body.action)


@router.post("/{user_id}/reminders/simulate-next-day")
def post_simulate_next_day(user_id: int, conn=Depends(subscription_intel_connection)):
    """Demo helper: shift reminder clocks back 24h (enable with DEMO_MODE=1 in production if desired)."""
    n = simulate_next_day(conn, user_id)
    return {"shifted_rows": n}


@router.post("/{user_id}/reset-demo")
def post_reset_demo(user_id: int, conn=Depends(subscription_intel_connection)):
    """Re-seed intelligence demo data for this user (real DB writes)."""
    from services.subscription_intelligence.seed_demo import run_seed_for_user

    run_seed_for_user(conn, user_id, wipe_device=True)
    return {"ok": True}
