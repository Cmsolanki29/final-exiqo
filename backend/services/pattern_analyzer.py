"""Spending pattern analysis beyond raw anomaly flags."""

from __future__ import annotations

import calendar
import os
from datetime import date, datetime, timedelta
from typing import Any

import psycopg2

from db import get_connection


class SpendingPatternAnalyzer:
    """Analyzes velocity, recurrence, spikes, merchants, time habits, and savings trajectory."""

    def get_db_connection(self) -> psycopg2.extensions.connection:
        return get_connection()

    def analyze_spending_velocity(self, user_id: int) -> dict[str, Any]:
        conn = self.get_db_connection()
        cur = conn.cursor()
        try:
            today = date.today()
            y, m = today.year, today.month
            last_m, last_y = (m - 1, y) if m > 1 else (12, y - 1)
            days_this = calendar.monthrange(y, m)[1]
            days_last = calendar.monthrange(last_y, last_m)[1]

            def month_total(yy: int, mm: int) -> float:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0)::float FROM transactions
                    WHERE user_id = %s AND type = 'DEBIT'
                      AND EXTRACT(YEAR FROM transaction_date)::int = %s
                      AND EXTRACT(MONTH FROM transaction_date)::int = %s
                    """,
                    (user_id, yy, mm),
                )
                return float(cur.fetchone()[0] or 0)

            this_spend = month_total(y, m)
            last_spend = month_total(last_y, last_m)
            this_avg = this_spend / max(days_this, 1)
            last_avg = last_spend / max(days_last, 1)
            if last_avg > 0:
                vel_pct = round((this_avg - last_avg) / last_avg * 100, 2)
            else:
                vel_pct = 0.0 if this_avg == 0 else 100.0
            accelerating = this_avg > last_avg * 1.05
            alert_needed = this_avg > last_avg * 1.3 if last_avg > 0 else this_spend > 0

            return {
                "this_month_daily_avg": round(this_avg, 2),
                "last_month_daily_avg": round(last_avg, 2),
                "velocity_change_pct": vel_pct,
                "is_accelerating": bool(accelerating),
                "alert_needed": bool(alert_needed),
            }
        finally:
            cur.close()
            conn.close()

    def find_recurring_transactions(self, user_id: int) -> list[dict[str, Any]]:
        """Merchants appearing in 3+ distinct months (similar to subscription / EMI / bill)."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT
                    merchant,
                    COUNT(DISTINCT DATE_TRUNC('month', transaction_date))::int AS month_span,
                    AVG(amount)::float AS avg_amt,
                    MAX(category) AS category
                FROM transactions
                WHERE user_id = %s AND type = 'DEBIT'
                  AND merchant IS NOT NULL AND TRIM(merchant) <> ''
                GROUP BY merchant
                HAVING COUNT(DISTINCT DATE_TRUNC('month', transaction_date)) >= 3
                ORDER BY month_span DESC, avg_amt DESC
                LIMIT 25
                """,
                (user_id,),
            )
            out: list[dict[str, Any]] = []
            for merchant, month_span, avg_amt, cat in cur.fetchall():
                next_d = date.today().replace(day=1) + timedelta(days=32)
                next_d = date(next_d.year, next_d.month, 1)
                out.append(
                    {
                        "merchant": merchant,
                        "amount": round(float(avg_amt), 2),
                        "category": cat,
                        "frequency": f"{int(month_span)} distinct months",
                        "next_expected_date": next_d.isoformat(),
                    }
                )
            return out
        finally:
            cur.close()
            conn.close()

    def detect_category_spikes(self, user_id: int) -> list[dict[str, Any]]:
        conn = self.get_db_connection()
        cur = conn.cursor()
        try:
            today = date.today()
            y, m = today.year, today.month
            months_back = []
            cy, cm = y, m
            for _ in range(4):
                months_back.append((cy, cm))
                if cm == 1:
                    cy, cm = cy - 1, 12
                else:
                    cm -= 1

            this_y, this_m = months_back[0]
            prev_months = months_back[1:]

            def cat_tot(yy: int, mm: int) -> dict[str, float]:
                cur.execute(
                    """
                    SELECT COALESCE(category, 'Uncategorized'), COALESCE(SUM(amount), 0)::float
                    FROM transactions
                    WHERE user_id = %s AND type = 'DEBIT'
                      AND EXTRACT(YEAR FROM transaction_date)::int = %s
                      AND EXTRACT(MONTH FROM transaction_date)::int = %s
                    GROUP BY 1
                    """,
                    (user_id, yy, mm),
                )
                return {r[0]: float(r[1]) for r in cur.fetchall()}

            this_map = cat_tot(this_y, this_m)
            prev_maps = [cat_tot(py, pm) for py, pm in prev_months]
            all_cats = set(this_map.keys()) | set().union(*(pm.keys() for pm in prev_maps))
            spikes = []
            for cat in all_cats:
                this_v = this_map.get(cat, 0.0)
                prev_vals = [pm.get(cat, 0.0) for pm in prev_maps]
                avg3 = sum(prev_vals) / max(len(prev_vals), 1)
                if avg3 <= 0:
                    continue
                spike_pct = (this_v - avg3) / avg3 * 100
                if spike_pct > 50:
                    sev = "CRITICAL" if spike_pct > 100 else "WARNING"
                    spikes.append(
                        {
                            "category": cat,
                            "this_month": round(this_v, 2),
                            "three_month_avg": round(avg3, 2),
                            "spike_pct": round(spike_pct, 2),
                            "severity": sev,
                        }
                    )
            spikes.sort(key=lambda x: -x["spike_pct"])
            return spikes[:20]
        finally:
            cur.close()
            conn.close()

    def get_merchant_frequency(self, user_id: int, top_n: int = 10) -> list[dict[str, Any]]:
        conn = self.get_db_connection()
        cur = conn.cursor()
        try:
            today = date.today()
            y, m = today.year, today.month
            cur.execute(
                """
                SELECT merchant,
                       COUNT(*)::int,
                       SUM(amount)::float,
                       AVG(amount)::float,
                       MAX(category) AS category
                FROM transactions
                WHERE user_id = %s AND type = 'DEBIT'
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                  AND merchant IS NOT NULL AND merchant <> ''
                GROUP BY merchant
                ORDER BY COUNT(*) DESC, SUM(amount) DESC
                LIMIT %s
                """,
                (user_id, y, m, top_n),
            )
            return [
                {
                    "merchant": r[0],
                    "visit_count": int(r[1]),
                    "total_spent": round(float(r[2]), 2),
                    "avg_per_visit": round(float(r[3]), 2),
                    "category": r[4],
                }
                for r in cur.fetchall()
            ]
        finally:
            cur.close()
            conn.close()

    def analyze_time_patterns(self, user_id: int) -> dict[str, Any]:
        conn = self.get_db_connection()
        cur = conn.cursor()
        try:
            today = date.today()
            y, m = today.year, today.month
            cur.execute(
                """
                SELECT hour_of_day, COUNT(*)::int FROM transactions
                WHERE user_id = %s AND type = 'DEBIT'
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                  AND hour_of_day IS NOT NULL
                GROUP BY hour_of_day ORDER BY COUNT(*) DESC LIMIT 1
                """,
                (user_id, y, m),
            )
            ph = cur.fetchone()
            peak_hour = int(ph[0]) if ph else 12

            cur.execute(
                """
                SELECT day_of_week, COUNT(*)::int FROM transactions
                WHERE user_id = %s AND type = 'DEBIT'
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                  AND day_of_week IS NOT NULL
                GROUP BY day_of_week ORDER BY COUNT(*) DESC LIMIT 1
                """,
                (user_id, y, m),
            )
            pdw = cur.fetchone()
            names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            peak_day = names[int(pdw[0])] if pdw else "N/A"

            cur.execute(
                """
                SELECT COALESCE(AVG(amount), 0)::float FROM transactions
                WHERE user_id = %s AND type = 'DEBIT' AND is_weekend = TRUE
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                """,
                (user_id, y, m),
            )
            wend = float(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT COALESCE(AVG(amount), 0)::float FROM transactions
                WHERE user_id = %s AND type = 'DEBIT' AND (is_weekend = FALSE OR is_weekend IS NULL)
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                """,
                (user_id, y, m),
            )
            wday = float(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT COUNT(*)::int FROM transactions
                WHERE user_id = %s AND type = 'DEBIT' AND is_night_txn = TRUE
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                """,
                (user_id, y, m),
            )
            night_cnt = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT COUNT(*)::int FROM transactions
                WHERE user_id = %s AND type = 'DEBIT'
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                  AND hour_of_day IS NOT NULL AND hour_of_day < 10
                """,
                (user_id, y, m),
            )
            morning_cnt = int(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT COUNT(*)::int FROM transactions
                WHERE user_id = %s AND type = 'DEBIT'
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                """,
                (user_id, y, m),
            )
            total_cnt = int(cur.fetchone()[0] or 1)

            return {
                "peak_hour": peak_hour,
                "peak_day": peak_day,
                "weekend_vs_weekday": {
                    "weekend_avg": round(wend, 2),
                    "weekday_avg": round(wday, 2),
                },
                "night_transaction_count": night_cnt,
                "morning_spender": bool(morning_cnt > total_cnt * 0.35),
            }
        finally:
            cur.close()
            conn.close()

    def get_savings_trajectory(self, user_id: int) -> dict[str, Any]:
        conn = self.get_db_connection()
        cur = conn.cursor()
        try:
            today = date.today()
            y, m = today.year, today.month
            last_day = calendar.monthrange(y, m)[1]
            remaining = max((date(y, m, last_day) - today).days, 0)

            cur.execute(
                "SELECT savings_goal::float, monthly_income::float FROM users WHERE id = %s",
                (user_id,),
            )
            ur = cur.fetchone()
            goal = float(ur[0] or 0) if ur else 0.0
            income = float(ur[1] or 0) if ur else 0.0

            cur.execute(
                """
                SELECT COALESCE(SUM(CASE WHEN type = 'CREDIT' THEN amount ELSE 0 END), 0)::float,
                       COALESCE(SUM(CASE WHEN type = 'DEBIT' THEN amount ELSE 0 END), 0)::float
                FROM transactions
                WHERE user_id = %s
                  AND EXTRACT(YEAR FROM transaction_date)::int = %s
                  AND EXTRACT(MONTH FROM transaction_date)::int = %s
                """,
                (user_id, y, m),
            )
            inc, exp = cur.fetchone()
            saved = float(inc or 0) - float(exp or 0)
            daily_need = (goal - saved) / max(remaining, 1) if goal > saved else 0.0
            projected = saved + daily_need * remaining if remaining else saved
            on_track = saved >= goal * (today.day / max(last_day, 1)) if goal > 0 else saved >= 0
            deficit = max(0.0, goal - saved)

            return {
                "monthly_goal": round(goal, 2),
                "current_month_saved": round(saved, 2),
                "days_remaining": remaining,
                "projected_savings": round(projected, 2),
                "on_track": bool(on_track),
                "deficit": round(deficit, 2),
                "monthly_income": round(income, 2),
            }
        finally:
            cur.close()
            conn.close()


pattern_analyzer = SpendingPatternAnalyzer()
