"""LLM writes only the friendly recommendation paragraph — verdict is deterministic elsewhere."""
from __future__ import annotations

from services.openai_service import call_gpt


def fetch_recommendation_paragraph(
    *,
    name: str,
    monthly_cost: float,
    category: str,
    verdict: str,
    reason: str,
    usage_summary: str,
    substitute_name: str | None,
) -> str:
    sub_line = substitute_name or "none"
    user_prompt = f"""You are SmartSpend's subscription advisor. Given:
- Subscription: {name} (₹{monthly_cost:,.0f}/mo, category: {category})
- Verdict: {verdict}
- Reason: {reason}
- Usage trend: {usage_summary}
- Substitute detected: {sub_line}

Write ONE paragraph (max 3 sentences) recommending an action. Be warm, specific, and reference the exact numbers. If a substitute is detected, frame it as "you migrated" not "you abandoned". If upgrade verdict, suggest the specific pro plan and the value swap if relevant. Indian context — use ₹."""

    out = call_gpt(
        system_prompt="You are SmartSpend's subscription advisor. Plain text only, no markdown.",
        user_prompt=user_prompt.strip(),
        max_tokens=220,
        json_mode=False,
    )
    text = str(out).strip() if isinstance(out, str) else ""
    if text.startswith("AI insights unavailable") or not text:
        if substitute_name:
            return (
                f"You've clearly shifted time to {substitute_name} while {name} still bills ₹{monthly_cost:,.0f}/month — "
                f"cancelling the old subscription is the fastest win."
            )
        if verdict == "upgrade":
            return (
                f"Your {category} usage supports upgrading {name}: the deterministic model marked this as upgrade-worthy; "
                f"compare pro tiers against ₹{monthly_cost:,.0f}/mo you're paying today."
            )
        return f"{name} ({verdict}): {reason} — review renewal in app settings before the next debit."
    return text
