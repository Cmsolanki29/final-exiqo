"""EMI Trap Detector routes."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from statistics import median
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from db import get_db
from services.openai_service import call_gpt

router = APIRouter(prefix="/emi", tags=["EMI Detector"])


def _month_index(d: date) -> int:
    return d.year * 12 + d.month


def _longest_consecutive_month_streak(dates: list[date]) -> tuple[int, date, date]:
    if not dates:
        return 0, date.today(), date.today()
    ordered = sorted(dates)
    unique_months = sorted({_month_index(d) for d in ordered})
    best = 1
    cur = 1
    best_end_idx = unique_months[0]
    for i in range(1, len(unique_months)):
        if unique_months[i] == unique_months[i - 1] + 1:
            cur += 1
            if cur > best:
                best = cur
                best_end_idx = unique_months[i]
        else:
            cur = 1
    best_start_idx = best_end_idx - best + 1
    start_candidates = [d for d in ordered if _month_index(d) == best_start_idx]
    end_candidates = [d for d in ordered if _month_index(d) == best_end_idx]
    return best, min(start_candidates), max(end_candidates)


def _classify_emi_type(merchant: str, category: str, amount: float, description_blob: str) -> str:
    text = f"{merchant} {description_blob}".lower()
    cat = (category or "").lower()
    if any(k in text for k in ("home", "housing", "mortgage", "lic housing")):
        return "HOME_LOAN"
    if any(k in text for k in ("car", "vehicle", "auto", "bmw")):
        return "VEHICLE EMI"
    if any(k in text for k in ("phone", "mobile", "gadget", "bajaj")):
        return "PHONE/GADGET EMI"
    if "credit card" in text or "min due" in text:
        return "CREDIT_CARD"
    if any(k in text for k in ("loan", "emi", "equated", "installment", "installment")):
        return "LOAN"
    if "finance" in cat:
        return "INVESTMENT_EMI"
    if 1000 <= amount <= 5000:
        return "PHONE/GADGET EMI"
    if 5000 < amount <= 15000:
        return "VEHICLE EMI"
    if amount > 15000:
        return "HOME_LOAN"
    return "OTHER"


def _next_due_date(payment_day: int, today: date) -> date:
    year, month = today.year, today.month
    days_in_month = calendar.monthrange(year, month)[1]
    candidate = date(year, month, min(payment_day, days_in_month))
    if candidate <= today:
        month = month + 1
        if month == 13:
            year += 1
            month = 1
        days_in_month = calendar.monthrange(year, month)[1]
        candidate = date(year, month, min(payment_day, days_in_month))
    return candidate


def _danger_from_ratio(ratio: float) -> str:
    if ratio < 20:
        return "SAFE"
    if ratio < 30:
        return "WARNING"
    if ratio <= 40:
        return "DANGER"
    return "CRITICAL"


def _build_emi_detection(conn, user_id: int) -> dict[str, Any]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT name, monthly_income::float
            FROM users
            WHERE id = %s;
            """,
            (user_id,),
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user_name, monthly_income = user[0], float(user[1] or 0)

        cur.execute(
            """
            SELECT merchant, amount::float, transaction_date,
                   COALESCE(category, ''), COALESCE(description, '')
            FROM transactions
            WHERE user_id = %s
              AND type = 'DEBIT'
              AND transaction_date >= (CURRENT_DATE - INTERVAL '6 months')
              AND merchant IS NOT NULL
              AND merchant <> '';
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for merchant, amount, tx_date, category, description in rows:
        grouped[str(merchant).strip()].append(
            {
                "amount": float(amount or 0),
                "date": tx_date,
                "category": category or "",
                "description": description or "",
            }
        )

    emi_entries: list[dict[str, Any]] = []
    for merchant, txns in grouped.items():
        txns_sorted = sorted(txns, key=lambda x: x["date"])
        if len(txns_sorted) < 3:
            continue

        amounts = [x["amount"] for x in txns_sorted]
        dates = [x["date"] for x in txns_sorted]
        categories = [x["category"] for x in txns_sorted]
        descriptions = [x["description"] for x in txns_sorted]

        med_amount = float(median(amounts))
        med_day = int(round(median([d.day for d in dates])))
        if med_amount <= 0:
            continue

        amount_ok = all(abs(a - med_amount) / med_amount <= 0.05 for a in amounts)
        date_ok = all(abs(d.day - med_day) <= 3 for d in dates)
        streak, streak_start, streak_end = _longest_consecutive_month_streak(dates)
        keyword_blob = f"{merchant} {' '.join(descriptions)}".lower()
        has_keyword = any(k in keyword_blob for k in ("emi", "loan", "equated", "installment"))
        merchant_blob = merchant.lower()
        if any(k in merchant_blob for k in ("premium", "spotify", "netflix", "zee", "linkedin", "swiggy")):
            continue
        merchant_emi_pattern = any(
            k in merchant_blob for k in ("emi", "loan", "finserv", "capital", "housing", "financial", "min due")
        )
        finance_category = any("finance" in (c or "").lower() for c in categories) and any(
            k in merchant_blob for k in ("loan", "emi", "capital", "financial", "housing", "bank")
        )

        if streak >= 3 and amount_ok and date_ok and (has_keyword or finance_category) and merchant_emi_pattern:
            emi_type = _classify_emi_type(
                merchant=merchant,
                category=categories[0] if categories else "",
                amount=med_amount,
                description_blob=" ".join(descriptions),
            )
            emi_entries.append(
                {
                    "merchant": merchant,
                    "amount": round(med_amount, 2),
                    "payment_date": med_day,
                    "category": categories[0] if categories else "",
                    "emi_type": emi_type,
                    "months_detected": streak,
                    "first_detected": streak_start.isoformat(),
                    "last_detected": streak_end.isoformat(),
                    "next_due": _next_due_date(med_day, date.today()).isoformat(),
                }
            )

    emi_entries.sort(key=lambda x: x["amount"], reverse=True)
    total_burden = round(sum(x["amount"] for x in emi_entries), 2)
    ratio = round((total_burden / monthly_income * 100), 1) if monthly_income > 0 else 0.0
    danger = _danger_from_ratio(ratio)
    over_limit = round(max(0.0, ratio - 30.0), 1)
    max_new_emi = round(monthly_income * 0.30 - total_burden, 2)

    verdict: str
    if not emi_entries:
        verdict = "No fixed EMI pattern detected in the last 6 months."
    elif max_new_emi < 0:
        verdict = (
            f"You are Rs.{abs(int(round(max_new_emi))):,} over the safe EMI limit. "
            "Do NOT take any new loans."
        )
    else:
        verdict = (
            f"You can safely take up to Rs.{int(round(max_new_emi)):,} additional EMI "
            "while staying under RBI's 30% guideline."
        )

    advice_prompt = f"""
User: {user_name}
Monthly income: Rs.{monthly_income:,.0f}
Detected EMIs: {emi_entries}
Total EMI burden: Rs.{total_burden:,.0f}
Debt-to-income ratio: {ratio}%
Danger level: {danger}
RBI safe limit: 30%
Give concise practical Indian personal-finance advice in 2-3 sentences.
"""
    advice = call_gpt(
        system_prompt=(
            "You are SmartSpend EMI advisor. Analyze EMI burden and give clear advice in professional English. "
            "Reference specific rupee amounts. Plain text only, max 4 sentences."
        ),
        user_prompt=advice_prompt.strip(),
        max_tokens=220,
        json_mode=False,
    )
    raw = str(advice).strip() if isinstance(advice, str) else ""
    if raw.startswith("AI insights unavailable"):
        raw = ""
    ai_advice = raw or (
        f"Your debt-to-income ratio is {ratio:.1f}%. Keep total EMI commitments under 30% of monthly income "
        f"for stability. With Rs.{total_burden:,.0f} in EMIs on Rs.{monthly_income:,.0f} income, "
        "avoid new loans until the ratio improves."
    )

    return {
        "user_name": user_name,
        "monthly_income": round(monthly_income, 2),
        "emis_detected": emi_entries,
        "total_emi_burden": total_burden,
        "debt_to_income_ratio": ratio,
        "danger_level": danger,
        "rbi_safe_limit": 30,
        "over_limit_by": over_limit,
        "max_new_emi_allowed": max_new_emi,
        "verdict": verdict,
        "ai_advice": ai_advice,
    }


@router.get("/{user_id}")
def get_emi_report(user_id: int, conn=Depends(get_db)):
    try:
        return _build_emi_detection(conn, user_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"EMI detector error: {exc}") from exc


@router.post("/{user_id}/scan")
def scan_and_store_emi(user_id: int, conn=Depends(get_db)):
    try:
        report = _build_emi_detection(conn, user_id)
        entries = report["emis_detected"]
        cur = conn.cursor()
        try:
            cur.execute("UPDATE emi_records SET is_active = FALSE WHERE user_id = %s;", (user_id,))
            for item in entries:
                cur.execute(
                    """
                    INSERT INTO emi_records (
                        user_id, merchant, detected_amount, payment_date, category, emi_type,
                        months_detected, is_active, first_detected, last_detected
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s)
                    ON CONFLICT (user_id, merchant) DO UPDATE SET
                        detected_amount = EXCLUDED.detected_amount,
                        payment_date = EXCLUDED.payment_date,
                        category = EXCLUDED.category,
                        emi_type = EXCLUDED.emi_type,
                        months_detected = EXCLUDED.months_detected,
                        is_active = TRUE,
                        first_detected = EXCLUDED.first_detected,
                        last_detected = EXCLUDED.last_detected;
                    """,
                    (
                        user_id,
                        item["merchant"],
                        item["amount"],
                        item["payment_date"],
                        item["category"],
                        item["emi_type"],
                        item["months_detected"],
                        item["first_detected"],
                        item["last_detected"],
                    ),
                )
        finally:
            cur.close()
        return {
            "user_id": user_id,
            "emi_detected_count": len(entries),
            "total_emi_burden": report["total_emi_burden"],
            "debt_to_income_ratio": report["debt_to_income_ratio"],
            "danger_level": report["danger_level"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"EMI scan error: {exc}") from exc
