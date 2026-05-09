"""OpenAI GPT-4o-mini — SmartSpend AI Insights Engine (Phase 4)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

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
            _client = OpenAI(api_key=key)
        except Exception:
            _client_init_failed = True
            return None
    return _client


# ---------------------------------------------------------------------------
# Safe GPT call with retry
# ---------------------------------------------------------------------------


def call_gpt(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
    json_mode: bool = True,
) -> dict[str, Any] | str:
    client = _get_client()
    if client is None:
        return {} if json_mode else ""

    for attempt in range(2):
        try:
            kwargs: dict[str, Any] = {
                "model": "gpt-4o-mini",
                "max_tokens": max_tokens,
                "temperature": 0.7,
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
            return {} if json_mode else ""


# ---------------------------------------------------------------------------
# In-memory cache (1 hour default)
# ---------------------------------------------------------------------------

_cache: dict[str, dict[str, Any]] = {}


def get_cached(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and entry["expires_at"] > time.time():
        return entry["data"]
    return None


def set_cached(key: str, data: Any, ttl_seconds: int = 3600) -> None:
    _cache[key] = {"data": data, "expires_at": time.time() + ttl_seconds}


# ---------------------------------------------------------------------------
# Feature 1: Monthly financial insights
# ---------------------------------------------------------------------------


def generate_monthly_insights(user_data: dict[str, Any]) -> dict[str, Any]:
    cache_key = f"insights_{user_data.get('user_id')}_{user_data.get('current_month')}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    system_prompt = """You are SmartSpend AI, a personal financial advisor for Indian users.
Analyze financial data and provide personalized insights in JSON format.
Be specific with rupee amounts. Use friendly, conversational tone.
Reference the user by name. Always respond with valid JSON only."""

    user_prompt = f"""Analyze this Indian user's financial data for {user_data.get('current_month')}:

Name: {user_data.get('name')}
Monthly Income: ₹{user_data.get('monthly_income', 0):,.0f}
Savings Goal: ₹{user_data.get('savings_goal', 0):,.0f}
This Month Income: ₹{user_data.get('total_income', 0):,.0f}
This Month Expense: ₹{user_data.get('total_expense', 0):,.0f}
Amount Saved: ₹{user_data.get('total_saved', 0):,.0f}
Savings Rate: {user_data.get('savings_rate', 0)}%
Health Score: {user_data.get('health_score', 0)}/100
Suspicious Transactions: {user_data.get('anomaly_count', 0)}

Spending Breakdown:
{json.dumps(user_data.get('category_breakdown', []), indent=2)}

Top Merchants this month: {', '.join(user_data.get('top_merchants', []))}
Last Month Expense: ₹{user_data.get('last_month_expense', 0):,.0f}
Last Month Saved: ₹{user_data.get('last_month_saved', 0):,.0f}

Respond with JSON containing:
- summary (2-3 sentences)
- key_insights (list of 4 specific observations with rupee amounts)
- warnings (list of 2-3 risks)
- recommendations (list of 4 actionable tips with specific amounts)
- positive_highlights (list of 1-2 things done well)
- spending_verdict: one of GOOD/AVERAGE/NEEDS_IMPROVEMENT/CRITICAL"""

    result = call_gpt(system_prompt, user_prompt, max_tokens=1200, json_mode=True)
    if not isinstance(result, dict) or not result:
        result = {
            "summary": (
                f"{user_data.get('name')} saved Rs.{user_data.get('total_saved', 0):,.0f} this month "
                f"with a {user_data.get('savings_rate', 0)}% savings rate."
            ),
            "key_insights": [f"Health score is {user_data.get('health_score', 0)}/100"],
            "warnings": [],
            "recommendations": ["Review your top spending categories", "Set a weekly UPI limit"],
            "positive_highlights": ["You are tracking spend in SmartSpend"],
            "spending_verdict": "AVERAGE",
        }

    set_cached(cache_key, result, ttl_seconds=3600)
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

    result = call_gpt(system_prompt, user_prompt, max_tokens=1200, json_mode=True)
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
