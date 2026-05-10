"""Decision schema — output of the Decision Engine (Phase 4).

Phase 1: stub schema so routes can reference it immediately.
Full implementation in Phase 4 (decision_engine.py).

The four-way action classification mirrors Stripe Radar's allow/review/block
plus a challenge tier for 3DS/OTP prompts.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field


class Decision(BaseModel):
    """Result of the multi-action decision engine.

    action         — what the system does with the transaction.
    score          — snapshot of risk_score at decision time.
    reasons        — list of human-readable reasons (rule + model).
    rule_overrides — named hard rules that fired (e.g. 'blacklisted_device').
    explainer      — partial SHAP dict (Phase 7); empty dict until then.
    challenge_type — which challenge to present when action=='challenge'.
    """

    action: Literal["allow", "review", "challenge", "block"]
    score: Annotated[int, Field(ge=0, le=100)]
    reasons: list[str] = Field(default_factory=list)
    rule_overrides: list[str] = Field(default_factory=list)
    explainer: dict = Field(default_factory=dict)
    challenge_type: Optional[Literal["otp", "3ds", "biometric"]] = None
