"""
Seed 90-day app_usage_signals + subscription intelligence columns for demo users.
SIMULATED: production version uses Android UsageStatsManager via companion mobile SDK.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from psycopg2.extensions import connection as PgConnection

from services.subscription_intelligence import (
    evaluate_subscription,
    persist_verdict,
    schedule_reminders_for_subscription,
)


def _upsert_sub_row(
    cur,
    user_id: int,
    merchant: str,
    *,
    amount: float,
    billing_cycle: str,
    category: str,
    status: str,
    usage_score: int,
    last_used_days: int,
    monthly_cost: float,
    times_charged: int,
    first_charged: date,
    last_charged: date,
    intelligence_category: str,
    linked_app_package: str,
    billing_day: int,
    next_billing_date: date,
    is_pro: bool,
) -> None:
    cur.execute(
        """
        INSERT INTO subscriptions (
          user_id, merchant, amount, billing_cycle, category, status,
          usage_score, last_used_days, monthly_cost, times_charged, first_charged, last_charged,
          intelligence_category, linked_app_package, billing_day, next_billing_date, currency, sub_lifecycle, is_pro
        ) VALUES (
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'INR','active',%s
        )
        ON CONFLICT (user_id, merchant) DO UPDATE SET
          amount = EXCLUDED.amount,
          billing_cycle = EXCLUDED.billing_cycle,
          category = EXCLUDED.category,
          status = EXCLUDED.status,
          usage_score = EXCLUDED.usage_score,
          last_used_days = EXCLUDED.last_used_days,
          monthly_cost = EXCLUDED.monthly_cost,
          times_charged = EXCLUDED.times_charged,
          first_charged = EXCLUDED.first_charged,
          last_charged = EXCLUDED.last_charged,
          intelligence_category = EXCLUDED.intelligence_category,
          linked_app_package = EXCLUDED.linked_app_package,
          billing_day = EXCLUDED.billing_day,
          next_billing_date = EXCLUDED.next_billing_date,
          is_pro = EXCLUDED.is_pro;
        """,
        (
            user_id,
            merchant,
            amount,
            billing_cycle,
            category,
            status,
            usage_score,
            last_used_days,
            monthly_cost,
            times_charged,
            first_charged,
            last_charged,
            intelligence_category,
            linked_app_package,
            billing_day,
            next_billing_date,
            is_pro,
        ),
    )


def _bulk_usage(cur, user_id: int, pkg: str, series: list[tuple[date, int, int, int]]) -> None:
    """(signal_date, usage_minutes, sessions, weekend_minutes)"""
    for d, mins, sess, wk in series:
        peak = 21 if mins > 40 else 12
        cur.execute(
            """
            INSERT INTO app_usage_signals (
              user_id, app_package, signal_date, usage_minutes, session_count,
              last_opened_at, weekend_minutes, peak_hour, notifications_received, notifications_opened
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id, app_package, signal_date) DO UPDATE SET
              usage_minutes = EXCLUDED.usage_minutes,
              session_count = EXCLUDED.session_count,
              weekend_minutes = EXCLUDED.weekend_minutes,
              peak_hour = EXCLUDED.peak_hour;
            """,
            (
                user_id,
                pkg,
                d,
                mins,
                sess,
                f"{d.isoformat()} 20:15:00+00",
                wk,
                peak,
                max(0, sess // 2),
                max(0, sess // 4),
            ),
        )


def run_seed_for_user(conn: PgConnection, user_id: int, *, wipe_device: bool = True) -> None:
    rnd = random.Random(42 + user_id)
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM reminder_outcomes WHERE reminder_id IN (SELECT id FROM scheduled_reminders WHERE user_id=%s);",
            (user_id,),
        )
        cur.execute("DELETE FROM scheduled_reminders WHERE user_id=%s;", (user_id,))
        cur.execute(
            "DELETE FROM verdict_history WHERE subscription_id IN (SELECT id FROM subscriptions WHERE user_id=%s);",
            (user_id,),
        )
        cur.execute("DELETE FROM app_usage_signals WHERE user_id=%s;", (user_id,))
        if wipe_device:
            cur.execute("DELETE FROM device_links WHERE user_id=%s;", (user_id,))

        today = date.today()
        d0 = today - timedelta(days=89)

        def days() -> list[date]:
            return [d0 + timedelta(days=i) for i in range(90)]

        all_days = days()

        # Netflix — thriving steady ~45 min/day
        nf = []
        for d in all_days:
            base = 35 + rnd.randint(0, 25)
            nf.append((d, base, max(1, base // 25), base // 3 if d.weekday() >= 5 else 0))
        _bulk_usage(cur, user_id, "com.netflix.mediaclient", nf)

        # Spotify — collapse last 35 days
        sp = []
        for i, d in enumerate(all_days):
            if i < 55:
                m = 120 + rnd.randint(0, 40)
            elif i < 70:
                m = 40 + rnd.randint(0, 15)
            else:
                m = rnd.randint(0, 2)
            sp.append((d, m, max(1, m // 30) if m > 5 else 0, m // 4 if d.weekday() >= 5 else 0))
        _bulk_usage(cur, user_id, "com.spotify.music", sp)

        # YouTube Music — rises as Spotify falls
        ym = []
        for i, d in enumerate(all_days):
            if i < 30:
                m = 15 + rnd.randint(0, 10)
            else:
                m = 80 + rnd.randint(0, 60) + min(80, (i - 30) * 3)
            ym.append((d, m, max(1, m // 20), m // 3 if d.weekday() >= 5 else 0))
        _bulk_usage(cur, user_id, "com.google.android.apps.youtube.music", ym)

        # YouTube Premium (main app)
        yt = []
        for i, d in enumerate(all_days):
            m = 20 + min(120, i * 2) + rnd.randint(0, 20)
            yt.append((d, m, max(1, m // 25), m // 4 if d.weekday() >= 5 else 0))
        _bulk_usage(cur, user_id, "com.google.android.youtube", yt)

        # LinkedIn — dormant (almost no sessions)
        li = []
        for d in all_days:
            m = rnd.randint(0, 8)
            li.append((d, m, 0, 0))
        _bulk_usage(cur, user_id, "com.linkedin.android", li)

        # ChatGPT — upgrade path (heavy ramp)
        cg = []
        for i, d in enumerate(all_days):
            m = 10 + int((i / 90) * 220) + rnd.randint(0, 25)
            cg.append((d, m, max(2, m // 18), m // 5 if d.weekday() >= 5 else 0))
        _bulk_usage(cur, user_id, "com.openai.chatgpt", cg)

        # Canva — dead last 65d
        cv = []
        for i, d in enumerate(all_days):
            m = rnd.randint(15, 45) if i < 25 else rnd.randint(0, 1)
            cv.append((d, m, 1 if m > 3 else 0, 0))
        _bulk_usage(cur, user_id, "com.canva.editor", cv)

        # Amazon (Prime) — clear month-over-month decline
        am = []
        for i, d in enumerate(all_days):
            m = max(8, int(72 - i * 0.75) + rnd.randint(0, 8))
            am.append((d, m, max(1, m // 22), m // 5 if d.weekday() >= 5 else 0))
        _bulk_usage(cur, user_id, "in.amazon.mShop.android.shopping", am)

        nb = today + timedelta(days=3)
        common = dict(
            billing_cycle="MONTHLY",
            status="ACTIVE",
            usage_score=70,
            last_used_days=4,
            times_charged=12,
            first_charged=today - timedelta(days=300),
            last_charged=today - timedelta(days=5),
            billing_day=nb.day,
            next_billing_date=nb,
        )

        rows = [
            ("Netflix India", 649, "Entertainment", "video", "com.netflix.mediaclient", False),
            ("Spotify Premium", 119, "Entertainment", "music", "com.spotify.music", False),
            ("Amazon Prime", 1499 / 12, "Entertainment", "video", "in.amazon.mShop.android.shopping", False),
            ("YouTube Premium", 129, "Entertainment", "music", "com.google.android.youtube", False),
            ("LinkedIn Premium", 999, "Finance & Investment", "professional", "com.linkedin.android", False),
            ("ChatGPT Plus", 1999, "Bills & Utilities", "productivity", "com.openai.chatgpt", False),
            ("Canva Pro", 499, "Bills & Utilities", "productivity", "com.canva.editor", False),
        ]
        for merchant, amt, cat, icat, pkg, is_pro in rows:
            _upsert_sub_row(
                cur,
                user_id,
                merchant,
                amount=float(amt),
                billing_cycle=common["billing_cycle"],
                category=cat,
                status=common["status"],
                usage_score=common["usage_score"],
                last_used_days=common["last_used_days"],
                monthly_cost=float(amt),
                times_charged=common["times_charged"],
                first_charged=common["first_charged"],
                last_charged=common["last_charged"],
                intelligence_category=icat,
                linked_app_package=pkg,
                billing_day=common["billing_day"],
                next_billing_date=common["next_billing_date"],
                is_pro=is_pro,
            )

        cur.execute("SELECT id FROM subscriptions WHERE user_id=%s ORDER BY id;", (user_id,))
        ids = [r[0] for r in cur.fetchall()]
        for sid in ids:
            vr = evaluate_subscription(conn, sid)
            if vr is not None:
                persist_verdict(conn, sid, vr)
                schedule_reminders_for_subscription(conn, sid, escalation_level=1)
    finally:
        cur.close()
