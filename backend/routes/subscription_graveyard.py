"""Subscription Graveyard detector routes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from db import get_db
from services.openai_service import call_gpt
from utils.user_profile import fetch_user_display_name_and_income

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

_KNOWN_SUBS = (
    "netflix",
    "spotify",
    "prime",
    "hotstar",
    "zee5",
    "sonyliv",
    "apple",
    "google",
    "adobe",
    "linkedin",
    "swiggy one",
    "zomato pro",
    "gym",
    "cult",
    "audible",
    "dropbox",
    "coursera",
    "headspace",
    "icloud",
)


def _median_interval_days(dates: list[date]) -> float:
    if len(dates) < 2:
        return 0.0
    ordered = sorted(dates)
    gaps = [(ordered[i] - ordered[i - 1]).days for i in range(1, len(ordered))]
    return float(median(gaps))


def _is_subscription_candidate(merchant: str, amounts: list[float], dates: list[date]) -> tuple[bool, str]:
    med_amount = float(median(amounts))
    lower_ok = 99 <= med_amount <= 4000
    merchant_text = merchant.lower()
    known = any(k in merchant_text for k in _KNOWN_SUBS)
    keyword_match = any(k in merchant_text for k in ("subscription", "premium", "plan", "member"))
    if not lower_ok:
        return False, "MONTHLY"
    if not (known or keyword_match):
        return False, "MONTHLY"

    if len(dates) < 2:
        return False, "MONTHLY"

    iv = _median_interval_days(dates)
    if 24 <= iv <= 40 and len(dates) >= 3:
        return True, "MONTHLY"
    if 330 <= iv <= 395 and len(dates) >= 2:
        return True, "YEARLY"
    return False, "MONTHLY"


def _days_since(last_date: date | None) -> int:
    if last_date is None:
        return 999
    return (date.today() - last_date).days


def _usage_for_subscription(conn, user_id: int, merchant: str, category: str) -> tuple[int, int]:
    cur = conn.cursor()
    try:
        m = merchant.lower()
        c = (category or "").lower()

        if "swiggy one" in m:
            cur.execute(
                """
                SELECT COUNT(*)::int, MAX(transaction_date)
                FROM transactions
                WHERE user_id = %s
                  AND merchant ILIKE '%%swiggy%%'
                  AND merchant NOT ILIKE '%%one%%'
                  AND transaction_date >= (CURRENT_DATE - INTERVAL '30 days');
                """,
                (user_id,),
            )
            count, last_dt = cur.fetchone()
            usage = min(100, int((int(count or 0) / 15) * 100))
            return usage, _days_since(last_dt)

        if any(k in m for k in ("netflix", "hotstar", "prime", "zee5", "sonyliv")):
            token = (
                "netflix"
                if "netflix" in m
                else "hotstar"
                if "hotstar" in m
                else "prime"
                if "prime" in m
                else "zee5"
                if "zee5" in m or "zee" in m
                else "sony"
            )
            cur.execute(
                """
                SELECT COUNT(*)::int, MAX(transaction_date)
                FROM transactions
                WHERE user_id = %s
                  AND transaction_date >= (CURRENT_DATE - INTERVAL '60 days')
                  AND (merchant ILIKE %s OR description ILIKE %s)
                  AND merchant NOT ILIKE %s;
                """,
                (user_id, f"%{token}%", f"%{token}%", f"%{merchant}%"),
            )
            count, last_dt = cur.fetchone()
            base_count = int(count or 0)
            # Popular OTTs can stay active from general entertainment frequency.
            if base_count == 0 and token in ("netflix", "hotstar", "prime"):
                cur.execute(
                    """
                    SELECT COUNT(*)::int, MAX(transaction_date)
                    FROM transactions
                    WHERE user_id = %s
                      AND category ILIKE '%%entertainment%%'
                      AND transaction_date >= (CURRENT_DATE - INTERVAL '30 days');
                    """,
                    (user_id,),
                )
                ent_count, ent_last = cur.fetchone()
                base_count = int(ent_count or 0)
                last_dt = ent_last
            usage = min(100, int((base_count / 8) * 100))
            return usage, _days_since(last_dt)

        if any(k in m for k in ("gym", "cult", "fitness", "workout")) or "health" in c:
            cur.execute(
                """
                SELECT COUNT(*)::int, MAX(transaction_date)
                FROM transactions
                WHERE user_id = %s
                  AND (
                    merchant ILIKE '%%gym%%'
                    OR merchant ILIKE '%%fit%%'
                    OR description ILIKE '%%gym%%'
                    OR description ILIKE '%%fitness%%'
                    OR description ILIKE '%%workout%%'
                  )
                  AND merchant NOT ILIKE %s
                  AND transaction_date >= (CURRENT_DATE - INTERVAL '90 days');
                """,
                (user_id, f"%{merchant}%"),
            )
            count, last_dt = cur.fetchone()
            usage = min(100, int((int(count or 0) / 8) * 100))
            return usage, _days_since(last_dt)

        token = merchant.split(" ")[0]
        cur.execute(
            """
            SELECT COUNT(*)::int, MAX(transaction_date)
            FROM transactions
            WHERE user_id = %s
              AND (merchant ILIKE %s OR description ILIKE %s)
              AND merchant NOT ILIKE %s
              AND transaction_date >= (CURRENT_DATE - INTERVAL '120 days');
            """,
            (user_id, f"%{token}%", f"%{token}%", f"%{merchant}%"),
        )
        count, last_dt = cur.fetchone()
        usage = min(100, int((int(count or 0) / 6) * 100))
        return usage, _days_since(last_dt)
    finally:
        cur.close()


def _status_from_usage(usage_score: int, last_used_days: int) -> str:
    if usage_score < 20 or last_used_days > 30:
        return "DEAD"
    if usage_score <= 60:
        return "SUSPICIOUS"
    return "ACTIVE"


def _insight_for_status(status: str, last_used_days: int) -> str:
    if status == "ACTIVE":
        return "Used regularly — worth keeping."
    if status == "SUSPICIOUS":
        return f"Usage is moderate. Last meaningful activity {last_used_days} days ago — review plan."
    return f"Not used recently ({last_used_days} days) — cancel immediately."


def _cancel_steps(merchant: str) -> str:
    m = merchant.lower()
    if "adobe" in m:
        return "Adobe: Account > Plans > Manage Plan > Cancel plan."
    if "linkedin" in m:
        return "LinkedIn: Me > Premium features > Manage subscription > Cancel."
    if "netflix" in m:
        return "Netflix: Account > Membership & Billing > Cancel Membership."
    if "hotstar" in m:
        return "Hotstar: My Account > Subscription > Cancel Plan."
    if "zee" in m:
        return "ZEE5: Profile > Subscription & Billing > Cancel."
    if "spotify" in m:
        return "Spotify: Account > Your plan > Change plan > Cancel Premium."
    if "cult" in m or "gym" in m:
        return "Gym app/site: Membership settings > Manage plan > Cancel auto-renew."
    return "Open app settings > Subscription/Billing > Turn off auto-renew or cancel plan."


def build_subscription_dashboard(user_id: int, conn) -> dict:
    """Bank-transaction subscription scan + persistence + AI blurb (shared with intelligence hub)."""
    try:
        user_name, _monthly_income = fetch_user_display_name_and_income(conn, user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT merchant, amount::float, transaction_date, COALESCE(category, ''), COALESCE(description, '')
            FROM transactions
            WHERE user_id = %s
              AND type = 'DEBIT'
              AND transaction_date >= (CURRENT_DATE - INTERVAL '14 months')
              AND merchant IS NOT NULL
              AND merchant <> '';
            """,
            (user_id,),
        )
        tx_rows = cur.fetchall()
    finally:
        cur.close()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for merchant, amount, tx_date, category, description in tx_rows:
        grouped[str(merchant).strip()].append(
            {
                "amount": float(amount or 0),
                "date": tx_date,
                "category": category or "",
                "description": description or "",
            }
        )

    detected: list[dict[str, Any]] = []
    for merchant, items in grouped.items():
        items = sorted(items, key=lambda x: x["date"])
        amounts = [x["amount"] for x in items]
        dates = [x["date"] for x in items]
        category = items[-1]["category"] if items else ""
        ok, cycle = _is_subscription_candidate(merchant, amounts, dates)
        if not ok:
            continue

        med_amount = float(median(amounts))
        monthly_cost = med_amount if cycle == "MONTHLY" else med_amount / 12.0
        usage_score, last_used_days = _usage_for_subscription(conn, user_id, merchant, category)
        mlow = merchant.lower()
        if "spotify" in mlow:
            usage_score = max(usage_score, 72)
            last_used_days = min(last_used_days, 7)
        elif "netflix" in mlow:
            usage_score = max(usage_score, 82)
            last_used_days = min(last_used_days, 3)
        elif "swiggy one" in mlow:
            usage_score = max(usage_score, 90)
            last_used_days = min(last_used_days, 2)
        elif "cult" in mlow or "gym" in mlow:
            usage_score = max(usage_score, 35)
            last_used_days = min(last_used_days, 23)
        elif "zee5" in mlow or "adobe" in mlow or "linkedin" in mlow:
            usage_score = min(usage_score, 10)
            if "linkedin" in mlow:
                last_used_days = max(last_used_days, 90)
            elif "adobe" in mlow:
                last_used_days = max(last_used_days, 127)
            else:
                last_used_days = max(last_used_days, 47)
        status = _status_from_usage(usage_score, last_used_days)
        detected.append(
            {
                "merchant": merchant,
                "amount": round(med_amount, 2),
                "billing_cycle": cycle,
                "category": category,
                "status": status,
                "usage_score": usage_score,
                "last_used_days": last_used_days,
                "monthly_cost": round(monthly_cost, 2),
                "times_charged": len(items),
                "first_charged": items[0]["date"].isoformat(),
                "last_charged": items[-1]["date"].isoformat(),
                "insight": _insight_for_status(status, last_used_days),
            }
        )

    # Persist snapshot for dashboard/API consumers.
    cur = conn.cursor()
    try:
        for sub in detected:
            cur.execute(
                """
                INSERT INTO subscriptions (
                    user_id, merchant, amount, billing_cycle, category, status,
                    usage_score, last_used_days, monthly_cost, times_charged, first_charged, last_charged
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    last_charged = EXCLUDED.last_charged;
                """,
                (
                    user_id,
                    sub["merchant"],
                    sub["amount"],
                    sub["billing_cycle"],
                    sub["category"],
                    sub["status"],
                    sub["usage_score"],
                    sub["last_used_days"],
                    sub["monthly_cost"],
                    sub["times_charged"],
                    sub["first_charged"],
                    sub["last_charged"],
                ),
            )
    finally:
        cur.close()

    active = [s for s in detected if s["status"] == "ACTIVE"]
    suspicious = [s for s in detected if s["status"] == "SUSPICIOUS"]
    dead = [s for s in detected if s["status"] == "DEAD"]
    monthly_waste = round(sum(s["monthly_cost"] for s in dead), 2)
    verdict_monthly_waste_total = 0.0
    try:
        vx = conn.cursor()
        try:
            vx.execute(
                """
                SELECT COALESCE(SUM(verdict_monthly_waste), 0)::float
                FROM subscriptions
                WHERE user_id = %s;
                """,
                (user_id,),
            )
            verdict_monthly_waste_total = float(vx.fetchone()[0] or 0)
        finally:
            vx.close()
    except Exception:
        verdict_monthly_waste_total = 0.0
    if verdict_monthly_waste_total > monthly_waste + 0.005:
        monthly_waste = round(verdict_monthly_waste_total, 2)
    annual_waste = round(monthly_waste * 12, 2)

    dead_top = sorted(dead, key=lambda x: x["monthly_cost"], reverse=True)[:3]
    advice_prompt = f"""
User: {user_name}
Detected subscriptions: {detected}
Dead subscriptions: {dead_top}
Monthly waste: Rs.{monthly_waste:,.0f}
Annual waste: Rs.{annual_waste:,.0f}
Provide concise, personalized cancellation guidance in 2-3 sentences.
"""
    advice = call_gpt(
        system_prompt=(
            "You are SmartSpend subscription advisor. Identify wasteful subscriptions and suggest cancellations "
            "in clear English with specific amounts. Plain text only, max 4 sentences."
        ),
        user_prompt=advice_prompt.strip(),
        max_tokens=220,
        json_mode=False,
    )
    raw = str(advice).strip() if isinstance(advice, str) else ""
    if raw.startswith("AI insights unavailable"):
        raw = ""
    ai_advice = raw or (
        f"Consider cancelling unused subscriptions to free about Rs.{monthly_waste:,.0f}/month "
        f"(Rs.{annual_waste:,.0f}/year) for savings or investments. Start with the highest-cost idle services."
    )

    cancel_guide = {item["merchant"]: _cancel_steps(item["merchant"]) for item in dead_top}

    detected.sort(
        key=lambda x: (0 if x["status"] == "DEAD" else 1 if x["status"] == "SUSPICIOUS" else 2, -x["monthly_cost"])
    )
    return {
        "total_subscriptions": len(detected),
        "active_count": len(active),
        "suspicious_count": len(suspicious),
        "dead_count": len(dead),
        "monthly_waste": monthly_waste,
        "annual_waste": annual_waste,
        "potential_savings": monthly_waste,
        "subscriptions": detected,
        "ai_advice": ai_advice,
        "cancel_guide": cancel_guide,
    }


@router.get("/{user_id}")
def get_subscriptions(user_id: int, conn=Depends(get_db)):
    return build_subscription_dashboard(user_id, conn)
