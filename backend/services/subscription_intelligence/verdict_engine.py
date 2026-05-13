"""
Deterministic subscription verdict engine (NOT an LLM).
Reads real app_usage_signals rows from PostgreSQL.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from psycopg2.extensions import connection as PgConnection


@dataclass
class VerdictResult:
    verdict: str
    confidence: int
    reason: str
    monthly_waste: float
    usage_delta_30d: float = 0.0
    substitution: dict[str, Any] | None = None


def _sum_minutes(rows: list[tuple]) -> int:
    return int(sum(int(r[0] or 0) for r in rows))


def _sum_sessions(rows: list[tuple]) -> int:
    return int(sum(int(r[1] or 0) for r in rows))


def get_substitutes(cur, category: str, primary_pkg: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT substitute_apps, category_display_name
        FROM subscription_substitutions
        WHERE category = %s AND primary_app = %s
        LIMIT 1;
        """,
        (category, primary_pkg),
    )
    row = cur.fetchone()
    if not row:
        return []
    apps, display = row[0], row[1]
    if isinstance(apps, str):
        apps = json.loads(apps)
    return [{"package": p, "display_name": display} for p in (apps or [])]


def compute_pkg_growth(cur, user_id: int, pkg: str, last_start: date, last_end: date, prev_start: date, prev_end: date) -> float:
    cur.execute(
        """
        SELECT COALESCE(SUM(usage_minutes), 0)::bigint
        FROM app_usage_signals
        WHERE user_id = %s AND app_package = %s AND signal_date >= %s AND signal_date < %s;
        """,
        (user_id, pkg, last_start, last_end),
    )
    last_m = int(cur.fetchone()[0] or 0)
    cur.execute(
        """
        SELECT COALESCE(SUM(usage_minutes), 0)::bigint
        FROM app_usage_signals
        WHERE user_id = %s AND app_package = %s AND signal_date >= %s AND signal_date < %s;
        """,
        (user_id, pkg, prev_start, prev_end),
    )
    prev_m = int(cur.fetchone()[0] or 0)
    return float(last_m) / max(float(prev_m), 1.0)


def compute_pro_threshold(category: str) -> float:
    """Hours per month above which we consider 'heavy' usage for upgrade hints."""
    return {"music": 40, "video": 35, "professional": 25, "productivity": 30, "fitness": 10, "news": 15}.get(category, 25)


def has_pro_tier(name: str) -> bool:
    n = (name or "").lower()
    return any(
        k in n
        for k in (
            "chatgpt",
            "notion",
            "canva",
            "youtube",
            "linkedin",
            "spotify",
            "netflix",
            "prime",
        )
    )


def evaluate_subscription(conn: PgConnection, subscription_id: int) -> VerdictResult | None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, user_id, merchant, monthly_cost, intelligence_category, linked_app_package, is_pro
            FROM subscriptions WHERE id = %s;
            """,
            (subscription_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        _id, user_id, merchant, monthly_cost, category, linked_pkg, is_pro = row
        monthly_cost = float(monthly_cost or 0)
        category = (category or "other").lower()
        merchant = merchant or ""

        if not linked_pkg:
            return VerdictResult(
                verdict="declining",
                confidence=40,
                reason="No device link yet — connect SmartSpend Device Intelligence for usage-grounded verdicts.",
                monthly_waste=round(monthly_cost * 0.15, 2),
                usage_delta_30d=0.0,
                substitution=None,
            )

        today = date.today()
        last30_start = today - timedelta(days=30)
        prev30_start = today - timedelta(days=60)
        prev30_end = today - timedelta(days=30)
        d60 = today - timedelta(days=60)

        cur.execute(
            """
            SELECT usage_minutes, session_count
            FROM app_usage_signals
            WHERE user_id = %s AND app_package = %s AND signal_date >= %s;
            """,
            (user_id, linked_pkg, last30_start),
        )
        last30_rows = cur.fetchall()
        cur.execute(
            """
            SELECT usage_minutes, session_count
            FROM app_usage_signals
            WHERE user_id = %s AND app_package = %s AND signal_date >= %s AND signal_date < %s;
            """,
            (user_id, linked_pkg, prev30_start, prev30_end),
        )
        prev30_rows = cur.fetchall()

        last30_minutes = _sum_minutes(last30_rows)
        prev30_minutes = _sum_minutes(prev30_rows)
        delta = (last30_minutes - prev30_minutes) / max(float(prev30_minutes), 1.0)

        cur.execute(
            """
            SELECT usage_minutes, session_count
            FROM app_usage_signals
            WHERE user_id = %s AND app_package = %s AND signal_date >= %s;
            """,
            (user_id, linked_pkg, d60),
        )
        last60_rows = cur.fetchall()
        last60_minutes = _sum_minutes(last60_rows)
        last30_sessions = _sum_sessions(last30_rows)
        prev30_sessions = _sum_sessions(prev30_rows)

        # DEAD: near-zero 60d
        if last30_minutes < 5 and prev30_minutes < 5:
            return VerdictResult(
                verdict="dead",
                confidence=95,
                reason="No meaningful usage in 60+ days",
                monthly_waste=round(monthly_cost, 2),
                usage_delta_30d=delta,
                substitution=None,
            )

        substitutes = get_substitutes(cur, category, linked_pkg)
        top_sub: dict[str, Any] | None = None
        max_growth = 0.0
        for s in substitutes:
            g = compute_pkg_growth(cur, user_id, s["package"], last30_start, today, prev30_start, prev30_end)
            if g > max_growth:
                max_growth = g
                top_sub = s

        if delta < -0.4 and max_growth >= 2.0 and top_sub:
            return VerdictResult(
                verdict="dead",
                confidence=92,
                reason=f"Migrated toward {top_sub.get('display_name', 'another app')}",
                monthly_waste=round(monthly_cost, 2),
                usage_delta_30d=delta,
                substitution={"package": top_sub["package"], "label": top_sub.get("display_name", "")},
            )

        if last30_sessions < 2 and prev30_sessions < 4:
            return VerdictResult(
                verdict="dormant",
                confidence=80,
                reason="Less than 2 sessions/month in recent window",
                monthly_waste=round(monthly_cost * 0.85, 2),
                usage_delta_30d=delta,
                substitution=None,
            )

        if delta < -0.4:
            return VerdictResult(
                verdict="declining",
                confidence=75,
                reason=f"Usage down {abs(delta * 100):.0f}% vs prior 30 days",
                monthly_waste=round(monthly_cost * min(abs(delta), 0.95), 2),
                usage_delta_30d=delta,
                substitution=None,
            )

        hours = last30_minutes / 60.0
        if hours > compute_pro_threshold(category) and has_pro_tier(merchant) and not (is_pro or False):
            return VerdictResult(
                verdict="upgrade",
                confidence=85,
                reason=f"{hours:.0f}h/month in-app — pro tier likely ROI-positive for your workflow",
                monthly_waste=0.0,
                usage_delta_30d=delta,
                substitution=None,
            )

        return VerdictResult(
            verdict="thriving",
            confidence=90,
            reason="Healthy usage pattern vs prior month",
            monthly_waste=0.0,
            usage_delta_30d=delta,
            substitution=None,
        )
    finally:
        cur.close()


def persist_verdict(conn: PgConnection, subscription_id: int, vr: VerdictResult) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE subscriptions SET
              current_verdict = %s,
              verdict_confidence = %s,
              verdict_reason = %s,
              verdict_monthly_waste = %s,
              last_evaluated_at = NOW()
            WHERE id = %s;
            """,
            (vr.verdict, vr.confidence, vr.reason, vr.monthly_waste, subscription_id),
        )
        cur.execute(
            """
            INSERT INTO verdict_history (subscription_id, verdict, usage_delta_30d, confidence, reason)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (subscription_id, vr.verdict, vr.usage_delta_30d, vr.confidence, vr.reason),
        )
    finally:
        cur.close()
