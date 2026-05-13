"""Paired substitution insights from real usage + substitution graph."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from psycopg2.extensions import connection as PgConnection

from .verdict_engine import compute_pkg_growth


def detect_substitutions(conn: PgConnection, user_id: int) -> list[dict[str, Any]]:
    cur = conn.cursor()
    try:
        today = date.today()
        last30_start = today - timedelta(days=30)
        prev30_start = today - timedelta(days=60)
        prev30_end = today - timedelta(days=30)

        cur.execute(
            """
            SELECT id, merchant, monthly_cost, intelligence_category, linked_app_package, current_verdict
            FROM subscriptions
            WHERE user_id = %s AND linked_app_package IS NOT NULL
              AND current_verdict IN ('declining', 'dormant', 'dead');
            """,
            (user_id,),
        )
        subs = cur.fetchall()
        out: list[dict[str, Any]] = []

        cur.execute("SELECT category, primary_app, substitute_apps, category_display_name FROM subscription_substitutions;")
        graph = cur.fetchall()

        for sub_id, merchant, monthly_cost, cat, primary_pkg, verdict in subs:
            for g_cat, g_primary, subs_json, display in graph:
                if g_primary != primary_pkg:
                    continue
                apps = subs_json
                if isinstance(apps, str):
                    apps = json.loads(apps)
                if not apps:
                    continue
                cur.execute(
                    """
                    SELECT COALESCE(SUM(usage_minutes), 0)::bigint
                    FROM app_usage_signals
                    WHERE user_id = %s AND app_package = %s AND signal_date >= %s;
                    """,
                    (user_id, primary_pkg, last30_start),
                )
                primary_last = int(cur.fetchone()[0] or 0)
                cur.execute(
                    """
                    SELECT COALESCE(SUM(usage_minutes), 0)::bigint
                    FROM app_usage_signals
                    WHERE user_id = %s AND app_package = %s AND signal_date >= %s AND signal_date < %s;
                    """,
                    (user_id, primary_pkg, prev30_start, prev30_end),
                )
                primary_prev = int(cur.fetchone()[0] or 0)
                p_delta = (primary_last - primary_prev) / max(float(primary_prev), 1.0)

                best_pkg = None
                best_growth = 0.0
                for alt in apps:
                    g = compute_pkg_growth(cur, user_id, alt, last30_start, today, prev30_start, prev30_end)
                    if g > best_growth:
                        best_growth = g
                        best_pkg = alt

                if p_delta < -0.35 and best_growth >= 1.8 and best_pkg:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(usage_minutes), 0)::bigint
                        FROM app_usage_signals
                        WHERE user_id = %s AND app_package = %s AND signal_date >= %s;
                        """,
                        (user_id, best_pkg, last30_start),
                    )
                    alt_min = int(cur.fetchone()[0] or 0)
                    out.append(
                        {
                            "subscription_id": sub_id,
                            "from_merchant": merchant,
                            "from_package": primary_pkg,
                            "to_package": best_pkg,
                            "category_display": display,
                            "monthly_cost": float(monthly_cost or 0),
                            "headline": f"You migrated usage from {merchant.split()[0]} toward a substitute in {display}.",
                            "body": (
                                f"Primary app usage trend is down sharply while {best_pkg.split('.')[-1]} is up ~{best_growth:.1f}× vs prior 30 days. "
                                f"Consider cancelling {merchant} (≈₹{float(monthly_cost or 0):,.0f}/mo) if the new habit stuck."
                            ),
                            "from_last30_minutes": primary_last,
                            "to_last30_minutes": alt_min,
                        }
                    )
                break
        return out
    finally:
        cur.close()
