"""Predict upcoming subscription / dark-pattern charges from real transaction history."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from psycopg2.extensions import connection as PgConnection

from services.dashboard_scope import fetch_dashboard_mode, transaction_scope_sql


def _to_dt(d: date, t: Any) -> datetime:
    if isinstance(t, datetime):
        return t
    return datetime.combine(d, t)


def _fetch_txns(conn: PgConnection, user_id: int, months: int = 8) -> list[dict[str, Any]]:
    """Transactions visible in the user's current dashboard mode."""
    cur = conn.cursor()
    try:
        mode = fetch_dashboard_mode(cur, user_id)
        scope = transaction_scope_sql("t", mode)
        cur.execute(
            f"""
            SELECT t.id, t.transaction_date, t.transaction_time, t.amount::float,
                   COALESCE(t.type, ''), COALESCE(t.merchant, ''), COALESCE(t.description, '')
            FROM transactions t
            WHERE t.user_id = %s
              AND t.transaction_date >= (CURRENT_DATE - (%s || ' months')::interval)
              AND ({scope})
            ORDER BY t.transaction_date ASC, t.transaction_time ASC;
            """,
            (user_id, int(months)),
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    out: list[dict[str, Any]] = []
    for rid, d, tm, amt, tx_type, merchant, desc in rows:
        out.append(
            {
                "id": int(rid),
                "date": d,
                "time": tm,
                "dt": _to_dt(d, tm),
                "amount": float(amt or 0),
                "type": (tx_type or "").strip().upper(),
                "merchant": (merchant or "").strip(),
                "description": (desc or "").strip(),
            }
        )
    return out


def _trial_merchant(merchant: str) -> bool:
    low = merchant.lower()
    return any(
        k in low
        for k in (
            "cloud",
            "vpn",
            "secure",
            "trial",
            "pro",
            "app",
            "fit",
            "plus",
            "apple",
            "bill",
            "micro auth",
            "hotstar",
            "youtube",
            "netflix",
            "prime",
            "openai",
            "spotify",
            "google play",
            "paytm",
        )
    )


def _micro_auth_merchant(merchant: str) -> bool:
    low = merchant.lower()
    return any(
        k in low
        for k in ("micro auth", "apple.com", ".com/bill", "verify", "google *play", "play store")
    )


def _amounts_similar(a: float, b: float, tolerance: float = 0.12) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= tolerance


def predict_upcoming_charges(conn: PgConnection, user_id: int) -> list[dict[str, Any]]:
    """Return alert dicts ready for INSERT into pattern_alerts."""
    today = date.today()
    txns = _fetch_txns(conn, user_id, months=8)
    alerts: list[dict[str, Any]] = []

    debits = [t for t in txns if t["type"] == "DEBIT" and t["merchant"]]
    by_merchant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in debits:
        by_merchant[t["merchant"]].append(t)
    for m in by_merchant:
        by_merchant[m].sort(key=lambda x: x["dt"])

    scheduled: set[tuple[str, str]] = set()

    # --- Free trial ending ---
    for merchant, items in by_merchant.items():
        if not _trial_merchant(merchant) and not _micro_auth_merchant(merchant):
            continue
        for i, tx in enumerate(items):
            if tx["amount"] > 10 or tx["amount"] < 0.5:
                continue
            follow = None
            for nxt in items[i + 1 :]:
                if nxt["amount"] >= 99 and (nxt["date"] - tx["date"]).days >= 3:
                    follow = nxt
                    break
            if follow:
                gap = max(7, min((follow["date"] - tx["date"]).days, 90))
                next_charge = follow["date"] + timedelta(days=gap)
                if next_charge > today:
                    key = (merchant, "free_trial_ending")
                    if key not in scheduled:
                        scheduled.add(key)
                        alerts.append(
                            _alert_row(
                                user_id,
                                "free_trial_ending",
                                merchant,
                                float(follow["amount"]),
                                next_charge,
                                follow["id"],
                                0.82,
                                {
                                    "trial_anchor": tx["date"].isoformat(),
                                    "last_paid": follow["date"].isoformat(),
                                },
                            )
                        )
            else:
                for days in (7, 14, 30):
                    end = tx["date"] + timedelta(days=days)
                    if end > today:
                        est = _estimate_avg_debit(conn, user_id, merchant) or _default_followup_amount(merchant)
                        key = (merchant, "free_trial_ending")
                        if key not in scheduled:
                            scheduled.add(key)
                            alerts.append(
                                _alert_row(
                                    user_id,
                                    "free_trial_ending",
                                    merchant,
                                    float(est),
                                    end,
                                    tx["id"],
                                    0.65,
                                    {"trial_start": tx["date"].isoformat(), "assumed_days": days},
                                )
                            )
                        break

    # --- Monthly renewal (same amount, ~26–35 day gaps) ---
    for merchant, items in by_merchant.items():
        if len(items) < 2:
            continue
        deb = sorted([x for x in items if x["amount"] >= 49], key=lambda x: x["dt"])
        if len(deb) < 2:
            continue
        last_amt = round(deb[-1]["amount"], 2)
        same = [x for x in deb if round(x["amount"], 2) == last_amt]
        if len(same) < 2:
            continue
        dates = [x["date"] for x in same]
        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        if not intervals or not all(26 <= iv <= 35 for iv in intervals):
            continue
        next_d = dates[-1] + timedelta(days=30)
        if next_d > today:
            key = (merchant, "renewal_upcoming")
            if key not in scheduled:
                scheduled.add(key)
                alerts.append(
                    _alert_row(
                        user_id,
                        "renewal_upcoming",
                        merchant,
                        float(last_amt),
                        next_d,
                        same[-1]["id"],
                        0.9,
                        {"frequency": "monthly", "history_count": len(same)},
                    )
                )

    # --- One-rupee trap predicted (skip if free-trial alert already scheduled) ---
    for merchant, items in by_merchant.items():
        if (merchant, "free_trial_ending") in scheduled:
            continue
        for tx in items:
            if tx["amount"] > 1.0 or tx["type"] != "DEBIT":
                continue
            large_later = any(
                y["merchant"] == merchant and y["amount"] > 100 and y["date"] > tx["date"] for y in items
            )
            if large_later:
                continue
            pred = tx["date"] + timedelta(days=7)
            if pred > today:
                est = _estimate_avg_debit(conn, user_id, merchant) or _default_followup_amount(merchant)
                alerts.append(
                    _alert_row(
                        user_id,
                        "one_rupee_trap_predicted",
                        merchant,
                        float(est),
                        pred,
                        tx["id"],
                        0.55,
                        {
                            "verification_date": tx["date"].isoformat(),
                            "verification_amount": tx["amount"],
                        },
                    )
                )
                break

    # --- Price increase: recurring baseline then higher last charge ---
    for merchant, items in by_merchant.items():
        deb = sorted([x for x in items if x["type"] == "DEBIT" and x["amount"] >= 49], key=lambda x: x["dt"])
        if len(deb) < 3:
            continue
        last = deb[-1]
        if (today - last["date"]).days > 60:
            continue
        hist = deb[:-1]
        rounded = [round(x["amount"], 0) for x in hist]
        common_amt, cnt = Counter(rounded).most_common(1)[0]
        if cnt < 2:
            continue
        baseline = float(common_amt)
        if last["amount"] <= baseline * 1.1:
            continue
        inc_pct = (last["amount"] - baseline) / max(baseline, 1) * 100
        if inc_pct <= 10:
            continue
        next_d = last["date"] + timedelta(days=30)
        if next_d <= today:
            next_d = today + timedelta(days=7)
        alerts.append(
            _alert_row(
                user_id,
                "price_increase",
                merchant,
                float(last["amount"]),
                next_d,
                last["id"],
                0.88,
                {
                    "old_price": baseline,
                    "new_price": float(last["amount"]),
                    "increase_pct": round(inc_pct, 1),
                },
            )
        )

    keyed: dict[tuple[str, date, str], dict[str, Any]] = {}
    for a in alerts:
        k = (a["merchant_name"], a["charge_date"], a["pattern_type"])
        if k not in keyed or (a["predicted_confidence"] or 0) > (keyed[k].get("predicted_confidence") or 0):
            keyed[k] = a
    return sorted(keyed.values(), key=lambda x: (x["charge_date"], -float(x["predicted_confidence"] or 0)))


def _default_followup_amount(merchant: str) -> float:
    low = merchant.lower()
    if "openai" in low:
        return 1999.0
    if "apple" in low or "bill" in low:
        return 499.0
    if "youtube" in low or "hotstar" in low:
        return 299.0
    if "prime" in low or "amazon" in low:
        return 125.0
    return 499.0


def _alert_row(
    user_id: int,
    pattern_type: str,
    merchant: str,
    charge_amount: float,
    charge_date: date,
    source_txn_id: int | None,
    confidence: float,
    details: dict[str, Any],
) -> dict[str, Any]:
    first = charge_date - timedelta(days=3)
    deadline = datetime.combine(charge_date, datetime.min.time()) - timedelta(hours=12)
    return {
        "user_id": user_id,
        "pattern_type": pattern_type,
        "merchant_name": merchant[:250],
        "charge_amount": round(charge_amount, 2),
        "charge_date": charge_date,
        "action_deadline": deadline,
        "first_alert_date": first,
        "source_transaction_id": source_txn_id,
        "predicted_confidence": round(min(0.99, max(0.05, confidence)), 2),
        "details_json": details,
    }


def _estimate_avg_debit(conn: PgConnection, user_id: int, merchant: str) -> float | None:
    cur = conn.cursor()
    try:
        mode = fetch_dashboard_mode(cur, user_id)
        scope = transaction_scope_sql("t", mode)
        cur.execute(
            f"""
            SELECT AVG(t.amount)::float FROM transactions t
            WHERE t.user_id = %s AND t.type = 'DEBIT' AND t.merchant = %s AND t.amount > 15
              AND ({scope});
            """,
            (user_id, merchant),
        )
        r = cur.fetchone()
        return float(r[0]) if r and r[0] is not None else None
    finally:
        cur.close()


def prune_alerts_outside_scope(conn: PgConnection, user_id: int) -> int:
    """Expire pending alerts that no longer match dashboard-visible transactions."""
    cur = conn.cursor()
    try:
        mode = fetch_dashboard_mode(cur, user_id)
        scope = transaction_scope_sql("t", mode)
        cur.execute(
            f"""
            UPDATE pattern_alerts pa
            SET status = 'expired', updated_at = NOW()
            WHERE pa.user_id = %s
              AND pa.status IN ('pending', 'snoozed')
              AND (
                (
                  pa.source_transaction_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM transactions t
                    WHERE t.id = pa.source_transaction_id
                      AND t.user_id = pa.user_id
                      AND ({scope})
                  )
                )
                OR NOT EXISTS (
                  SELECT 1 FROM transactions t
                  WHERE t.user_id = pa.user_id
                    AND LOWER(TRIM(COALESCE(t.merchant, ''))) = LOWER(TRIM(pa.merchant_name))
                    AND t.type = 'DEBIT'
                    AND ({scope})
                    AND t.transaction_date >= (CURRENT_DATE - INTERVAL '8 months')
                )
              );
            """,
            (user_id,),
        )
        return cur.rowcount or 0
    finally:
        cur.close()


def upsert_pattern_alerts(conn: PgConnection, alerts: list[dict[str, Any]]) -> int:
    if not alerts:
        return 0
    cur = conn.cursor()
    n = 0
    try:
        for a in alerts:
            cur.execute(
                """
                INSERT INTO pattern_alerts (
                  user_id, pattern_type, merchant_name, charge_amount, charge_date,
                  action_deadline, first_alert_date, source_transaction_id,
                  predicted_confidence, details_json, status, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'pending', NOW())
                ON CONFLICT (user_id, pattern_type, merchant_name, charge_date) DO NOTHING
                RETURNING id;
                """,
                (
                    a["user_id"],
                    a["pattern_type"],
                    a["merchant_name"],
                    a["charge_amount"],
                    a["charge_date"],
                    a["action_deadline"],
                    a["first_alert_date"],
                    a.get("source_transaction_id"),
                    a.get("predicted_confidence"),
                    json.dumps(a.get("details_json") or {}),
                ),
            )
            if cur.fetchone():
                n += 1
    finally:
        cur.close()
    return n


def expire_stale_alerts(conn: PgConnection, user_id: int | None = None) -> int:
    cur = conn.cursor()
    try:
        if user_id is not None:
            cur.execute(
                """
                UPDATE pattern_alerts SET status = 'expired', updated_at = NOW()
                WHERE user_id = %s AND status IN ('pending', 'snoozed')
                  AND charge_date < CURRENT_DATE;
                """,
                (user_id,),
            )
        else:
            cur.execute(
                """
                UPDATE pattern_alerts SET status = 'expired', updated_at = NOW()
                WHERE status IN ('pending', 'snoozed') AND charge_date < CURRENT_DATE;
                """
            )
        return cur.rowcount or 0
    finally:
        cur.close()
