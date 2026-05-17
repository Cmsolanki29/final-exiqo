"""OpenAI GPT-4o-mini — SmartSpend AI Insights Engine (Phase 4)."""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from db import get_connection
from services.dashboard_scope import normalize_dashboard_mode

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

_client: OpenAI | None = None
_client_init_failed: bool = False

# Optional token metering (e.g. insight_test)
_meter_prompt: int = 0
_meter_completion: int = 0


def meter_reset() -> None:
    global _meter_prompt, _meter_completion
    _meter_prompt = 0
    _meter_completion = 0


def meter_totals() -> tuple[int, int, int]:
    return _meter_prompt, _meter_completion, _meter_prompt + _meter_completion


def _get_client() -> OpenAI | None:
    global _client, _client_init_failed
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or _client_init_failed:
        return None
    if _client is None:
        try:
            _client = OpenAI(api_key=key, timeout=40.0)
        except Exception:
            _client_init_failed = True
            return None
    return _client


# ---------------------------------------------------------------------------
# Safe GPT call with retry
# ---------------------------------------------------------------------------


def _call_groq_sync(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
    json_mode: bool = True,
    *,
    temperature: float = 0.7,
) -> dict[str, Any] | str:
    """Synchronous Groq using the OpenAI-compatible SDK."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return {} if json_mode else ""
    try:
        from openai import OpenAI as _OAI  # Groq uses the same SDK
        _gc = _OAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1", timeout=40.0)
        model = os.getenv("GROQ_CHAT_MODEL", os.getenv("PHASE_9_DEFAULT_MODEL", "llama-3.3-70b-versatile")).strip()
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = _gc.chat.completions.create(**kwargs)
        content = (resp.choices[0].message.content or "").strip()
        if json_mode:
            return json.loads(content) if content else {}
        return content
    except Exception as exc:
        print(f"[call_groq_sync] Groq error: {exc}")
        return {} if json_mode else ""


def _openai_insights_model() -> str:
    """Model for dashboard insights, health narrative, recommendations (cost vs quality)."""
    return os.getenv("OPENAI_INSIGHTS_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def call_gpt(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
    json_mode: bool = True,
    *,
    model: str | None = None,
) -> dict[str, Any] | str:
    client = _get_client()
    if client is None:
        return _call_groq_sync(system_prompt, user_prompt, max_tokens, json_mode)

    mdl = (model or _openai_insights_model()).strip() or "gpt-4o-mini"

    for attempt in range(2):
        try:
            kwargs: dict[str, Any] = {
                "model": mdl,
                "max_tokens": max_tokens,
                "temperature": 0.45,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            usage = getattr(response, "usage", None)
            if usage is not None:
                global _meter_prompt, _meter_completion
                _meter_prompt += int(getattr(usage, "prompt_tokens", 0) or 0)
                _meter_completion += int(getattr(usage, "completion_tokens", 0) or 0)
            content = (response.choices[0].message.content or "").strip()
            if json_mode:
                return json.loads(content) if content else {}
            return content
        except Exception as exc:
            if attempt == 0:
                time.sleep(1)
                continue
            print(f"[call_gpt] OpenAI error after retry: {exc}")
            return _call_groq_sync(system_prompt, user_prompt, max_tokens, json_mode)


def _call_openai_json_only(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    temperature: float = 0.45,
) -> dict[str, Any]:
    """OpenAI-only JSON completion (primary path for dashboard insights)."""
    client = _get_client()
    if client is None:
        return {}
    try:
        kwargs: dict[str, Any] = {
            "model": _openai_insights_model(),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        response = client.chat.completions.create(**kwargs)
        content = (response.choices[0].message.content or "").strip()
        return json.loads(content) if content else {}
    except Exception as exc:
        print(f"[_call_openai_json_only] {exc}")
        return {}


def call_dashboard_json_openai_then_groq(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 800,
    temperature: float = 0.35,
) -> dict[str, Any]:
    """Dashboard JSON: OpenAI (gpt-4o-mini) first; Groq only if OpenAI returns empty or errors."""
    o = _call_openai_json_only(system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)
    if isinstance(o, dict) and o:
        return o
    try:
        g = _call_groq_sync(
            system_prompt, user_prompt, max_tokens, True, temperature=temperature
        )
        if isinstance(g, dict) and g:
            return g
    except Exception as exc:
        print(f"[call_dashboard_json_openai_then_groq] Groq: {exc}")
    return {}


# ---------------------------------------------------------------------------
# Postgres insight cache (6 hours default)
# ---------------------------------------------------------------------------

_INSIGHT_CACHE_TTL_HOURS = 6


def _insight_cache_identity(user_data: dict[str, Any]) -> tuple[int, int, int, str]:
    uid = int(user_data.get("user_id") or 0)
    m = int(user_data.get("insight_month") or date.today().month)
    y = int(user_data.get("insight_year") or date.today().year)
    scope = normalize_dashboard_mode(user_data.get("insight_scope"))
    return uid, m, y, scope


def get_cached_insight(conn, user_id: int, month: int, year: int, scope: str) -> Any | None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT payload
            FROM insight_cache
            WHERE user_id = %s AND month = %s AND year = %s AND scope = %s
              AND generated_at > NOW() - INTERVAL '6 hours';
            """,
            (user_id, month, year, normalize_dashboard_mode(scope)),
        )
        row = cur.fetchone()
        if not row:
            return None
        payload = row[0]
        if isinstance(payload, str):
            return json.loads(payload)
        return payload
    except Exception as exc:
        print(f"[get_cached_insight] {exc}")
        return None
    finally:
        cur.close()


def set_cached_insight(
    conn,
    user_id: int,
    month: int,
    year: int,
    scope: str,
    data: Any,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO insight_cache (user_id, month, year, scope, payload, generated_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (user_id, month, year, scope)
            DO UPDATE SET payload = EXCLUDED.payload, generated_at = NOW();
            """,
            (
                user_id,
                month,
                year,
                normalize_dashboard_mode(scope),
                json.dumps(data, default=str),
            ),
        )
        conn.commit()
    except Exception as exc:
        print(f"[set_cached_insight] {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()


def invalidate_insight_cache(
    conn,
    user_id: int,
    month: int | None = None,
    year: int | None = None,
) -> None:
    """Delete cached insights for a user; optional month/year narrows the delete."""
    cur = conn.cursor()
    try:
        if month is not None and year is not None:
            cur.execute(
                "DELETE FROM insight_cache WHERE user_id = %s AND month = %s AND year = %s;",
                (user_id, month, year),
            )
        else:
            cur.execute("DELETE FROM insight_cache WHERE user_id = %s;", (user_id,))
        conn.commit()
    except Exception as exc:
        print(f"[invalidate_insight_cache] {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()


def get_cached(key: str) -> Any | None:
    """Legacy in-memory helper (unused by insight card; kept for compatibility)."""
    return None


def set_cached(key: str, data: Any, ttl_seconds: int = 3600) -> None:
    """Legacy in-memory helper (no-op)."""
    return


# ---------------------------------------------------------------------------
# Feature 1: Monthly financial insights
# ---------------------------------------------------------------------------


def _coerce_insight_card(raw: dict[str, Any], user_data: dict[str, Any]) -> dict[str, Any]:
    """Clamp list sizes and string lengths so the UI card stays compact."""

    def clip(s: object, max_len: int) -> str:
        t = str(s or "").strip()
        if len(t) <= max_len:
            return t
        return t[: max(0, max_len - 1)] + "…"

    verdict = str(raw.get("spending_verdict") or "AVERAGE").strip().upper()
    if verdict not in ("GOOD", "AVERAGE", "NEEDS_IMPROVEMENT", "CRITICAL"):
        verdict = "AVERAGE"

    ki = raw.get("key_insights")
    ki_list = [clip(x, 95) for x in ki] if isinstance(ki, list) else []
    ki_list = [x for x in ki_list if x][:3]
    while len(ki_list) < 3:
        ki_list.append(f"Health score {user_data.get('health_score', 0)}/100")

    warn = raw.get("warnings")
    w_list = [clip(x, 95) for x in warn] if isinstance(warn, list) else []
    w_list = [x for x in w_list if x][:2]

    rec = raw.get("recommendations")
    r_list = [clip(x, 105) for x in rec] if isinstance(rec, list) else []
    r_list = [x for x in r_list if x][:3]
    while len(r_list) < 3:
        r_list.append("Set a monthly budget for your top spending categories.")

    pos = raw.get("positive_highlights")
    p_list = [clip(x, 95) for x in pos] if isinstance(pos, list) else []
    p_list = [x for x in p_list if x][:2]
    if not p_list:
        p_list.append("You are actively tracking spend in SmartSpend.")

    summ = clip(raw.get("summary"), 240)
    if not summ:
        summ = clip(
            f"{user_data.get('name') or 'User'}, you saved ₹{user_data.get('total_saved', 0):,.0f} "
            f"this month ({user_data.get('savings_rate', 0)}% savings rate).",
            240,
        )

    return {
        "summary": summ,
        "key_insights": ki_list[:3],
        "warnings": w_list,
        "recommendations": r_list[:3],
        "positive_highlights": p_list[:2],
        "spending_verdict": verdict,
    }


def _normalize_llm_insight_minimal(raw: dict[str, Any]) -> dict[str, Any]:
    """Ensure keys expected by _coerce_insight_card exist (minimal analyst JSON omits some)."""
    if not isinstance(raw, dict):
        return {}
    out = dict(raw)
    if not isinstance(out.get("warnings"), list):
        out["warnings"] = []
    if not out.get("spending_verdict"):
        out["spending_verdict"] = "AVERAGE"
    return out


def generate_monthly_insights(user_data: dict[str, Any]) -> dict[str, Any]:
    uid, m, y, scope = _insight_cache_identity(user_data)
    conn = get_connection()
    try:
        cached = get_cached_insight(conn, uid, m, y, scope)
        if cached is not None:
            return cached
    finally:
        conn.close()

    system_prompt = """You are a financial analyst. Given transaction data, return a JSON object with these exact keys:
{
  "summary": "2 sentence overview of the user's financial month",
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "recommendations": ["action 1", "action 2", "action 3"],
  "positive_highlights": ["highlight 1"]
}
All text must be in plain English. Be specific with numbers. Return only valid JSON, no markdown."""

    snap = {
        "month": user_data.get("current_month"),
        "name": user_data.get("name"),
        "monthly_income_profile_inr": user_data.get("monthly_income"),
        "savings_goal_inr": user_data.get("savings_goal"),
        "income_inr": user_data.get("total_income"),
        "expense_inr": user_data.get("total_expense"),
        "saved_inr": user_data.get("total_saved"),
        "savings_rate_pct": user_data.get("savings_rate"),
        "health_score": user_data.get("health_score"),
        "anomaly_count": user_data.get("anomaly_count"),
        "category_breakdown": user_data.get("category_breakdown") or [],
        "top_merchants": user_data.get("top_merchants") or [],
        "last_month_expense_inr": user_data.get("last_month_expense"),
        "last_month_saved_inr": user_data.get("last_month_saved"),
    }
    user_prompt = "Use only these facts (do not invent). Data:\n" + json.dumps(snap, indent=2)

    result = call_dashboard_json_openai_then_groq(
        system_prompt, user_prompt, max_tokens=800, temperature=0.25
    )
    if not isinstance(result, dict) or not result:
        nm = user_data.get("name") or "User"
        result = {
            "summary": (
                f"{nm}, you saved ₹{user_data.get('total_saved', 0):,.0f} this month "
                f"({user_data.get('savings_rate', 0)}% savings rate) — here is your financial overview."
            )[:240],
            "key_insights": [
                f"Health score {user_data.get('health_score', 0)}/100",
                "Review your top spending categories",
                f"Flagged transactions this month: {user_data.get('anomaly_count', 0)}",
            ],
            "warnings": [],
            "recommendations": [
                "Set weekly caps on your top 2 spending categories",
                "Reconcile your EMIs and subscriptions",
                "Enable UPI spend alerts for the next 7 days",
            ],
            "positive_highlights": ["Your transactions are being tracked — great habit!"],
            "spending_verdict": "AVERAGE",
        }
    else:
        merged = _normalize_llm_insight_minimal(result)
        result = _coerce_insight_card(merged, user_data)

    conn = get_connection()
    try:
        set_cached_insight(conn, uid, m, y, scope, result)
    finally:
        conn.close()
    return result


# ---------------------------------------------------------------------------
# Feature 2: Anomaly explanation (plain English)
# ---------------------------------------------------------------------------


def explain_anomaly_transaction(transaction: dict[str, Any]) -> str:
    system_prompt = """You are SmartSpend consumer protection advisor.
Explain why a transaction was flagged in clear, professional English.
Reference specific amounts and dates. Be actionable in under 4 sentences.
Plain text only — no JSON."""

    user_prompt = f"""Explain why this transaction is suspicious to {transaction.get('user_name', 'the user')}:

Merchant: {transaction.get('merchant')}
Amount (INR): {float(transaction.get('amount', 0)):,.0f}
Date/Time: {transaction.get('transaction_date')} at {transaction.get('transaction_time')}
Category: {transaction.get('category')}
Risk Level: {transaction.get('risk_level')}
Why flagged: {transaction.get('anomaly_reason')}
Payment: {transaction.get('payment_method')}"""

    out = call_gpt(system_prompt, user_prompt, max_tokens=220, json_mode=False)
    if isinstance(out, dict):
        return (
            f"This ₹{float(transaction.get('amount', 0)):,.0f} payment to {transaction.get('merchant')} "
            f"looks unusual ({transaction.get('anomaly_reason', 'flagged')}). "
            "Verify with your bank before proceeding."
        )
    text = str(out).strip()
    if text:
        return text
    return (
        f"{transaction.get('user_name', 'User')}, this ₹{float(transaction.get('amount', 0)):,.0f} "
        f"transaction to {transaction.get('merchant')} was flagged: {transaction.get('anomaly_reason', 'review required')}. "
        "Confirm on your bank's official app or helpline before paying."
    )


def explain_anomaly_hinglish(transaction: dict[str, Any]) -> str:
    """Deprecated alias — use explain_anomaly_transaction."""
    return explain_anomaly_transaction(transaction)


# ---------------------------------------------------------------------------
# Feature 3: Scenario simulation
# ---------------------------------------------------------------------------


def simulate_financial_scenario(user_data: dict[str, Any], scenario: str) -> dict[str, Any]:
    system_prompt = """You are SmartSpend AI financial simulator for Indian users.
Calculate realistic financial projections based on scenarios.
Use actual numbers provided. Respond in JSON format only.
Be specific with rupee amounts in Indian context."""

    user_prompt = f"""Simulate this financial scenario for {user_data.get('name')}:

SCENARIO: {scenario}

CURRENT FINANCIAL STATE:
- Monthly Income: ₹{user_data.get('monthly_income', 0):,.0f}
- Monthly Expense: ₹{user_data.get('total_expense', 0):,.0f}
- Monthly Savings: ₹{user_data.get('total_saved', 0):,.0f}
- Savings Rate: {user_data.get('savings_rate', 0)}%
- Health Score: {user_data.get('health_score', 0)}/100
- Savings Goal: ₹{user_data.get('savings_goal', 0):,.0f}

Spending Breakdown:
{json.dumps(user_data.get('category_breakdown', [])[:12], indent=2)}

Calculate exact impact and respond with JSON:
- scenario_title
- current_state (monthly_savings, health_score, savings_rate)
- projected_state (monthly_savings, health_score, savings_rate)
- impact (savings_change, savings_change_pct, health_score_change, annual_impact)
- verdict: MANAGEABLE/RISKY/CRITICAL
- advice (3-4 sentences with specific amounts)
- alternatives (2 better options as strings)"""

    result = call_gpt(system_prompt, user_prompt, max_tokens=1000, json_mode=True)
    if not isinstance(result, dict) or not result:
        return {
            "scenario_title": scenario,
            "current_state": {
                "monthly_savings": user_data.get("total_saved", 0),
                "health_score": user_data.get("health_score", 0),
                "savings_rate": user_data.get("savings_rate", 0),
            },
            "projected_state": {},
            "impact": {},
            "verdict": "UNKNOWN",
            "advice": "Unable to simulate at this time. Please try again.",
            "alternatives": [],
        }
    return result


# ---------------------------------------------------------------------------
# Feature 4: Personalized recommendations
# ---------------------------------------------------------------------------


def get_personalized_recommendations(user_data: dict[str, Any]) -> dict[str, Any]:
    system_prompt = """You are SmartSpend AI giving personalized financial advice for Indian users.
Give SPECIFIC recommendations based on actual spending data.
Reference real merchants (Swiggy, Zomato, Amazon India etc).
Suggest specific rupee amounts. Respond in JSON format only."""

    user_prompt = f"""Give personalized financial recommendations for {user_data.get('name')}:

Income: ₹{user_data.get('monthly_income', 0):,.0f}/month
Current Savings: ₹{user_data.get('total_saved', 0):,.0f} ({user_data.get('savings_rate', 0)}%)
Savings Goal: ₹{user_data.get('savings_goal', 0):,.0f}/month
Health Score: {user_data.get('health_score', 0)}/100

Top Spending Categories:
{json.dumps(user_data.get('category_breakdown', [])[:5], indent=2)}

Top Merchants: {', '.join(user_data.get('top_merchants', [])[:5])}

Provide specific, actionable recommendations in JSON:
- priority_actions (list of 4, each with action, potential_saving, difficulty EASY/MEDIUM/HARD, category, impact HIGH/MEDIUM/LOW)
- quick_wins (3 easy things this week)
- long_term_goals (2 goals for next 3-6 months)
- budget_suggestion (object: category string keys to INR monthly numbers)
- monthly_challenge (one string)"""

    result = call_dashboard_json_openai_then_groq(
        system_prompt, user_prompt, max_tokens=1200, temperature=0.35
    )
    if not isinstance(result, dict) or not result:
        return {
            "priority_actions": [],
            "quick_wins": [
                "Track daily UPI totals",
                "Set category budgets",
                "Review subscriptions",
            ],
            "long_term_goals": [
                "Build 3-month emergency fund",
                "Start monthly SIP",
            ],
            "budget_suggestion": {},
            "monthly_challenge": "Try to save 10% more than last month",
        }
    return result


# ---------------------------------------------------------------------------
# Feature 5: Financial health narrative
# ---------------------------------------------------------------------------


def generate_health_narrative(
    user_data: dict[str, Any], health_details: dict[str, Any]
) -> dict[str, Any]:
    comp = health_details.get("components") or {}

    system_prompt = """You are SmartSpend AI explaining financial health scores to Indian users.
Make complex financial metrics easy to understand.
Be encouraging but honest. Use simple language.
Respond in JSON format only."""

    user_prompt = f"""Explain this financial health score to {user_data.get('name')}:

Overall Score: {health_details.get('score', 0)}/100 (Grade: {health_details.get('grade', 'N/A')})
Trend: {health_details.get('trend', 'STABLE')}

Score Breakdown:
- Savings Rate Score: {comp.get('savings_rate_score', 0)}/30
- Anomaly/Security Score: {comp.get('anomaly_penalty', 0)}/20
- Expense Ratio Score: {comp.get('expense_ratio_score', 0)}/25
- Consistency Score: {comp.get('consistency_score', 0)}/15
- Category Diversity Score: {comp.get('diversity_score', 0)}/10

User Context:
- Monthly Income: ₹{user_data.get('monthly_income', 0):,.0f}
- Savings Rate: {user_data.get('savings_rate', 0)}%
- Anomalies This Month: {user_data.get('anomaly_count', 0)}

Generate JSON with:
- headline (punchy, specific to their score)
- score_explanation (why this exact score)
- strongest_area (what they do best)
- weakest_area (what needs work)
- score_breakdown_narrative (plain English for each component)
- next_month_target (specific action to gain 5+ points)
- motivational_message (encouraging, use their name)"""

    result = call_gpt(system_prompt, user_prompt, max_tokens=1000, json_mode=True)
    if not isinstance(result, dict) or not result:
        return {
            "headline": f"Health Score: {health_details.get('score', 0)}/100",
            "score_explanation": "Based on savings rate, spending patterns, and security signals.",
            "strongest_area": "Regular income tracking",
            "weakest_area": "Savings consistency or anomaly activity",
            "score_breakdown_narrative": "Keep reviewing flagged transactions and category mix.",
            "next_month_target": "Aim to improve savings rate by 3–5 percentage points",
            "motivational_message": f"Keep going {user_data.get('name')}! Every rupee saved counts.",
        }
    return result
