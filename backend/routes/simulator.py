"""Transaction simulator — live fraud-scoring demo feed."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db import get_connection
from services.categorizer import resolve_category
from routes.fraud_shield import (
    _load_user_history,
    _parse_time_hhmm,
    calculate_fraud_risk_score,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulator", tags=["Fraud Simulator"])

DEMO_TRANSACTIONS = [
    {"amount": 280, "merchant": "Swiggy", "category": "food_delivery", "payment_method": "UPI", "description": "Swiggy order - Biryani + Coke", "upi_id": "swiggy@axisbank"},
    {"amount": 180, "merchant": "Uber", "category": "transport", "payment_method": "UPI", "description": "Uber ride - Koregaon Park to Hinjewadi", "upi_id": "uber@icici"},
    {"amount": 2500, "merchant": "Amazon", "category": "shopping", "payment_method": "card", "description": "Amazon - Boat earbuds", "upi_id": None},
    {"amount": 5000, "merchant": "CRED", "category": "bill_payment", "payment_method": "UPI", "description": "CRED credit card bill payment", "upi_id": "cred@axisbank"},
    {"amount": 450, "merchant": "Zepto", "category": "groceries", "payment_method": "UPI", "description": "Zepto - milk, bread, eggs", "upi_id": "zepto@yesbank"},
    {"amount": 49999, "merchant": "Unknown_UPI_7839201", "category": "transfer", "payment_method": "UPI", "description": "UPI transfer to unknown account", "upi_id": "unknown7839201@paytm", "_suspicious": True, "_force_time": "03:17"},
    {"amount": 380, "merchant": "Zomato", "category": "food_delivery", "payment_method": "UPI", "description": "Zomato - Pizza delivery", "upi_id": "zomato@hdfcbank"},
    {"amount": 499, "merchant": "PhonePe", "category": "recharge", "payment_method": "UPI", "description": "Jio prepaid recharge", "upi_id": "jio@phonepe"},
    {"amount": 25000, "merchant": "CryptoXchange_Deposit", "category": "investment", "payment_method": "netbanking", "description": "Crypto exchange deposit - urgent", "upi_id": None, "_suspicious": True, "_force_time": "02:45"},
    {"amount": 3200, "merchant": "DMart", "category": "groceries", "payment_method": "card", "description": "DMart monthly groceries", "upi_id": None},
    {"amount": 600, "merchant": "BookMyShow", "category": "entertainment", "payment_method": "UPI", "description": "Movie tickets - PVR Phoenix", "upi_id": "bookmyshow@upi"},
    {"amount": 15000, "merchant": "QuickLoan_App", "category": "transfer", "payment_method": "UPI", "description": "Loan repayment - QuickCash instant loan app", "upi_id": "quickloan@ybl", "_suspicious": True, "_force_time": "01:30"},
    {"amount": 1200, "merchant": "Myntra", "category": "shopping", "payment_method": "card", "description": "Myntra - T-shirt order", "upi_id": None},
    {"amount": 150, "merchant": "Chai Point", "category": "food_delivery", "payment_method": "UPI", "description": "Chai Point - 2 cutting chai", "upi_id": "chaipoint@icici"},
    {"amount": 4500, "merchant": "Flipkart", "category": "shopping", "payment_method": "card", "description": "Flipkart - phone case + charger", "upi_id": None},
    {"amount": 8000, "merchant": "Gaming_TopUp_Unknown", "category": "entertainment", "payment_method": "UPI", "description": "Gaming credits purchase - unknown platform", "upi_id": "gametopup_unknown@paytm", "_suspicious": True, "_force_time": "04:20"},
    {"amount": 350, "merchant": "Dunzo", "category": "groceries", "payment_method": "UPI", "description": "Dunzo delivery - medicines", "upi_id": "dunzo@hdfcbank"},
    {"amount": 999, "merchant": "Netflix", "category": "subscription", "payment_method": "card", "description": "Netflix monthly subscription", "upi_id": None},
    {"amount": 200, "merchant": "Metro Card", "category": "transport", "payment_method": "UPI", "description": "Pune Metro smart card recharge", "upi_id": "punemetro@sbi"},
    {"amount": 1800, "merchant": "BigBasket", "category": "groceries", "payment_method": "UPI", "description": "BigBasket weekly order", "upi_id": "bigbasket@icici"},
]

_simulator_task: Optional[asyncio.Task] = None
_is_running = False
_scored_results: list[dict[str, Any]] = []
_demo_transaction_ids: list[int] = []
_demo_alert_ids: list[int] = []
_current_index = 0
_stats = {"total": 0, "flagged": 0, "safe": 0}
_interval_seconds = 5
_demo_user_id = 1


class SimulatorStartRequest(BaseModel):
    interval_seconds: int = Field(default=5, ge=1, le=60)
    user_id: int = Field(default=1, ge=1)


def _recommendation(score: int) -> str:
    if score >= 85:
        return "BLOCK"
    if score >= 30:
        return "CAUTION"
    return "PROCEED"


def _reset_state() -> None:
    global _scored_results, _demo_transaction_ids, _demo_alert_ids, _current_index, _stats
    _scored_results = []
    _demo_transaction_ids = []
    _demo_alert_ids = []
    _current_index = 0
    _stats = {"total": 0, "flagged": 0, "safe": 0}


async def _stop_loop() -> None:
    global _simulator_task, _is_running
    _is_running = False
    if _simulator_task and not _simulator_task.done():
        _simulator_task.cancel()
        try:
            await _simulator_task
        except asyncio.CancelledError:
            pass
    _simulator_task = None


def _process_one_transaction(user_id: int, demo: dict[str, Any]) -> dict[str, Any] | None:
    """Insert, score, optionally alert. Returns event dict for frontend."""
    payee = (demo.get("upi_id") or demo.get("merchant") or "").strip()
    merchant_label = demo.get("merchant") or payee
    force_time = demo.get("_force_time")
    if force_time:
        hour, minute = _parse_time_hhmm(force_time)
    else:
        now = datetime.now()
        hour, minute = now.hour, now.minute

    at = datetime.combine(date.today(), datetime.min.time()).replace(hour=hour, minute=minute)
    txn_date = date.today()
    txn_time = at.time()
    amount = float(demo["amount"])
    description = f"[DEMO] {demo.get('description', '')}"
    category = resolve_category(merchant_label, demo.get("category"))
    payment_method = demo.get("payment_method") or "UPI"
    hod = hour
    dow = at.weekday()
    is_weekend = dow >= 5
    is_night = hod >= 23 or hod < 5

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE id = %s;", (user_id,))
        if not cur.fetchone():
            cur.close()
            return None

        uh = _load_user_history(conn, user_id, payee, at)

        cur.execute(
            """
            INSERT INTO transactions (
                user_id, transaction_date, transaction_time, amount, type,
                description, merchant, category, payment_method,
                hour_of_day, day_of_week, is_weekend, is_night_txn,
                anomaly_flag, risk_score, risk_level, ml_processed
            ) VALUES (
                %s, %s, %s, %s, 'DEBIT', %s, %s, %s, %s,
                %s, %s, %s, %s, FALSE, 0, 'LOW', FALSE
            )
            RETURNING id;
            """,
            (
                user_id,
                txn_date,
                txn_time,
                amount,
                description,
                merchant_label,
                category,
                payment_method,
                hod,
                dow,
                is_weekend,
                is_night,
            ),
        )
        txn_id = int(cur.fetchone()[0])
        _demo_transaction_ids.append(txn_id)

        tx = {
            "payee": payee,
            "merchant": payee,
            "amount": amount,
            "hour": hour,
            "minute": minute,
            "description": description,
            "payment_method": payment_method,
        }
        result = calculate_fraud_risk_score(tx, uh)
        risk_score_int = int(result["risk_score"])
        risk_level = result["risk_level"]
        risk_factors = result.get("risk_factors") or []
        pattern = result.get("pattern_matched")
        should_alert = bool(result.get("should_alert"))

        cur.execute(
            """
            UPDATE transactions
            SET risk_score = %s, risk_level = %s,
                anomaly_flag = %s,
                anomaly_reason = %s
            WHERE id = %s;
            """,
            (
                risk_score_int,
                risk_level,
                should_alert,
                "; ".join(risk_factors[:4]) if risk_factors else None,
                txn_id,
            ),
        )

        alert_id = None
        if should_alert:
            warning = (
                f"Risk {risk_score_int}/100 ({risk_level}). "
                + (f"Pattern: {pattern}. " if pattern else "")
                + "Review before proceeding."
            )
            cur.execute(
                """
                INSERT INTO fraud_alerts (
                    user_id, transaction_id, pattern_matched, risk_score,
                    amount_at_risk, warning_message, hinglish_explanation, user_action
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING')
                RETURNING id;
                """,
                (
                    user_id,
                    txn_id,
                    pattern or "SIMULATOR_DEMO",
                    risk_score_int,
                    amount,
                    warning,
                    "; ".join(risk_factors[:6]) if risk_factors else warning,
                ),
            )
            alert_id = int(cur.fetchone()[0])
            _demo_alert_ids.append(alert_id)

        conn.commit()
        cur.close()

        risk_norm = round(risk_score_int / 100.0, 3)
        rec = _recommendation(risk_score_int)
        event = {
            "id": f"{txn_id}-{uuid.uuid4().hex[:8]}",
            "transaction_id": txn_id,
            "alert_id": alert_id,
            "merchant": merchant_label,
            "amount": amount,
            "payment_method": payment_method,
            "category": category,
            "description": description,
            "timestamp": at.isoformat(),
            "risk_score": risk_norm,
            "risk_score_raw": risk_score_int,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "pattern_matched": pattern,
            "should_proceed": risk_score_int < 85,
            "recommendation": rec,
        }
        return event
    except Exception as exc:
        conn.rollback()
        logger.exception("Simulator transaction failed: %s", exc)
        return None
    finally:
        conn.close()


async def _simulator_loop(user_id: int, interval: float) -> None:
    global _current_index, _is_running, _scored_results, _stats

    while _is_running:
        try:
            if _current_index >= len(DEMO_TRANSACTIONS):
                _current_index = 0

            demo = DEMO_TRANSACTIONS[_current_index]
            _current_index += 1

            event = await asyncio.to_thread(_process_one_transaction, user_id, demo)
            if event:
                _scored_results.append(event)
                if len(_scored_results) > 50:
                    _scored_results = _scored_results[-50:]

                _stats["total"] += 1
                if event["risk_score"] >= 0.6:
                    _stats["flagged"] += 1
                else:
                    _stats["safe"] += 1
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Simulator loop error: %s", exc)

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break


@router.post("/start")
async def start_simulator(body: SimulatorStartRequest) -> dict[str, Any]:
    global _simulator_task, _is_running, _interval_seconds, _demo_user_id

    if _is_running:
        return {"running": True, "message": "Simulator already running"}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE id = %s;", (body.user_id,))
        if not cur.fetchone():
            raise HTTPException(404, f"User {body.user_id} not found")
        cur.close()
    finally:
        conn.close()

    _interval_seconds = body.interval_seconds
    _demo_user_id = body.user_id
    _is_running = True
    _simulator_task = asyncio.create_task(
        _simulator_loop(body.user_id, float(body.interval_seconds))
    )
    return {
        "running": True,
        "interval_seconds": body.interval_seconds,
        "user_id": body.user_id,
        "transactions_in_queue": len(DEMO_TRANSACTIONS),
    }


@router.post("/stop")
async def stop_simulator() -> dict[str, Any]:
    await _stop_loop()
    return {"running": False, "message": "Simulator stopped"}


@router.post("/reset")
async def reset_simulator() -> dict[str, Any]:
    await _stop_loop()

    txn_ids = list(_demo_transaction_ids)
    alert_ids = list(_demo_alert_ids)

    deleted_txns = 0
    deleted_alerts = 0

    if txn_ids or alert_ids:
        conn = get_connection()
        try:
            cur = conn.cursor()
            if txn_ids:
                for table in (
                    "risk_investigations",
                    "orchestration_decisions",
                    "review_queue",
                ):
                    try:
                        cur.execute(
                            f"DELETE FROM {table} WHERE transaction_id = ANY(%s);",
                            (txn_ids,),
                        )
                    except Exception as exc:
                        logger.warning("Reset cleanup %s: %s", table, exc)
                        conn.rollback()

                if alert_ids:
                    cur.execute("DELETE FROM fraud_alerts WHERE id = ANY(%s);", (alert_ids,))
                    deleted_alerts = cur.rowcount

                cur.execute(
                    "DELETE FROM fraud_alerts WHERE transaction_id = ANY(%s);",
                    (txn_ids,),
                )
                deleted_alerts += cur.rowcount

                cur.execute("DELETE FROM transactions WHERE id = ANY(%s);", (txn_ids,))
                deleted_txns = cur.rowcount

            conn.commit()
            cur.close()
        except Exception as exc:
            conn.rollback()
            logger.exception("Reset failed: %s", exc)
            raise HTTPException(500, f"Reset failed: {exc}") from exc
        finally:
            conn.close()

    _reset_state()
    return {
        "success": True,
        "deleted_transactions": deleted_txns,
        "deleted_alerts": deleted_alerts,
        "message": "Demo data cleared",
    }


@router.get("/status")
def simulator_status() -> dict[str, Any]:
    return {
        "running": _is_running,
        "stats": dict(_stats),
        "current_index": _current_index,
        "demo_transactions_inserted": len(_demo_transaction_ids),
        "demo_alerts_inserted": len(_demo_alert_ids),
        "interval_seconds": _interval_seconds,
        "user_id": _demo_user_id,
    }


@router.get("/recent")
def simulator_recent() -> dict[str, Any]:
    return {
        "events": list(_scored_results),
        "stats": dict(_stats),
        "running": _is_running,
    }
