"""Phase 12 — pure routing policy.

Given a baseline ``ScoreResult`` and the live feature flags, decide:

* which conceptual *tier* the decision belongs to (used for analytics
  and the UI badge),
* whether the LLM-as-Judge should be invoked,
* whether a synchronous Phase 9 investigation should be triggered.

This module has **zero I/O** — no DB, no Redis, no LLM, no HTTP.  It is
fully unit-testable and deterministic.  Side-effects live in
``orchestrator.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class Tier(str, Enum):
    """Routing tiers in increasing cost order.

    The integer value is intentional — higher tier = more compute spent.
    """

    TIER_0_RULES = "tier_0_rules"
    TIER_1_XGB = "tier_1_xgb"
    TIER_2_GNN = "tier_2_gnn"
    TIER_3_DNN = "tier_3_dnn"
    TIER_4_LLM_AGENT = "tier_4_llm_agent"
    TIER_5_JUDGE = "tier_5_judge"


@dataclass(frozen=True)
class RoutingDecision:
    """Output of :func:`route` — what the orchestrator should *do* next."""

    tier: Tier
    reason: str
    invoke_judge: bool
    invoke_investigation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "tier_label": tier_to_human(self.tier),
            "reason": self.reason,
            "invoke_judge": self.invoke_judge,
            "invoke_investigation": self.invoke_investigation,
        }


@dataclass(frozen=True)
class RoutingPolicy:
    """All thresholds + flags needed by :func:`route`.

    Held as a dataclass so tests can construct one directly without
    monkey-patching :func:`get_settings`.
    """

    enabled: bool
    auto_investigate: bool
    judge_enabled: bool
    sync_investigation: bool
    tier0_max: int
    tier1_max: int
    tier2_max: int
    tier3_max: int
    dnn_disagree_delta: float

    @classmethod
    def from_settings(cls, settings: Any) -> "RoutingPolicy":
        return cls(
            enabled=bool(getattr(settings, "PHASE_12_ORCHESTRATOR_ENABLED", False)),
            auto_investigate=bool(getattr(settings, "PHASE_12_AUTO_INVESTIGATE", True)),
            judge_enabled=bool(getattr(settings, "PHASE_12_JUDGE_ENABLED", True)),
            sync_investigation=bool(getattr(settings, "PHASE_12_SYNC_INVESTIGATION", False)),
            tier0_max=int(getattr(settings, "PHASE_12_TIER0_MAX", 30)),
            tier1_max=int(getattr(settings, "PHASE_12_TIER1_MAX", 60)),
            tier2_max=int(getattr(settings, "PHASE_12_TIER2_MAX", 75)),
            tier3_max=int(getattr(settings, "PHASE_12_TIER3_MAX", 85)),
            dnn_disagree_delta=float(getattr(settings, "PHASE_12_DNN_DISAGREE_DELTA", 25.0)),
        )


# --------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------- #


def route(
    *,
    risk_score: int,
    signals: dict[str, Any],
    rule_overrides: list[str],
    policy: RoutingPolicy,
) -> RoutingDecision:
    """Return a :class:`RoutingDecision`.

    Tier ladder
    -----------
    * ``score < tier0_max``                   → ``TIER_0_RULES``
    * ``tier0_max ≤ score < tier1_max``       → ``TIER_1_XGB``
    * ``tier1_max ≤ score < tier2_max``       → ``TIER_2_GNN``      (if GNN signal present)
    * ``tier2_max ≤ score < tier3_max``       → ``TIER_3_DNN``      (if DNN shadow present)
    * ``score ≥ tier3_max``                   → ``TIER_4_LLM_AGENT``

    Judge invocation rules (TIER_5 is a *modifier*, not a replacement)
    -----------------------------------------------------------------
    The judge is invoked when:

    1. The orchestrator is enabled AND ``judge_enabled``, AND
    2. Any of:
        a. Tier ≥ TIER_3 (high-stakes decision), OR
        b. ``rule_overrides`` triggered while ``risk_score < tier1_max``
           (rules and ML disagree about a low-risk score), OR
        c. The DNN shadow score diverges from the prod score by at least
           ``dnn_disagree_delta``.

    Investigation invocation rules
    ------------------------------
    Only when both feature flags are on AND the tier is TIER_4 (or
    above).  The synchronous variant additionally requires
    ``sync_investigation``.  The async variant is handled in
    :class:`workers.alert_consumer.AlertConsumer` and is independent.
    """
    # ---- Tier selection ----
    has_gnn = bool(signals.get("gnn_emb_dim"))
    has_dnn_shadow = signals.get("dnn_shadow_score") is not None

    if risk_score < policy.tier0_max:
        tier = Tier.TIER_0_RULES
        reason = f"score {risk_score} < tier0_max {policy.tier0_max} - rules-only path"
    elif risk_score < policy.tier1_max:
        tier = Tier.TIER_1_XGB
        reason = f"score {risk_score} in [tier0_max, tier1_max) - standard hybrid"
    elif risk_score < policy.tier2_max:
        tier = Tier.TIER_2_GNN if has_gnn else Tier.TIER_1_XGB
        reason = (
            f"score {risk_score} in [tier1_max, tier2_max) - graph-augmented"
            if has_gnn
            else f"score {risk_score} in [tier1_max, tier2_max) - gnn unavailable, hybrid only"
        )
    elif risk_score < policy.tier3_max:
        tier = Tier.TIER_3_DNN if has_dnn_shadow else Tier.TIER_2_GNN if has_gnn else Tier.TIER_1_XGB
        reason = (
            f"score {risk_score} in [tier2_max, tier3_max) - DNN shadow available"
            if has_dnn_shadow
            else f"score {risk_score} in [tier2_max, tier3_max) - DNN unavailable"
        )
    else:
        tier = Tier.TIER_4_LLM_AGENT
        reason = f"score {risk_score} >= tier3_max {policy.tier3_max} - LLM investigation tier"

    # ---- Disagreement / divergence detection ----
    dnn_score = signals.get("dnn_shadow_score")
    dnn_delta = (
        abs(float(dnn_score) - float(risk_score))
        if isinstance(dnn_score, (int, float))
        else 0.0
    )
    rules_vs_ml_conflict = (
        bool(rule_overrides) and risk_score < policy.tier1_max
    )

    # ---- Judge gating ----
    invoke_judge = False
    if policy.enabled and policy.judge_enabled:
        if tier in (Tier.TIER_3_DNN, Tier.TIER_4_LLM_AGENT):
            invoke_judge = True
            reason += " | judge:high_stakes"
        elif rules_vs_ml_conflict:
            invoke_judge = True
            reason += " | judge:rules_vs_ml_conflict"
        elif dnn_delta >= policy.dnn_disagree_delta:
            invoke_judge = True
            reason += f" | judge:dnn_divergence({dnn_delta:.1f})"

    # ---- Investigation gating ----
    invoke_investigation = bool(
        policy.enabled
        and policy.auto_investigate
        and policy.sync_investigation
        and tier == Tier.TIER_4_LLM_AGENT
    )

    return RoutingDecision(
        tier=tier,
        reason=reason,
        invoke_judge=invoke_judge,
        invoke_investigation=invoke_investigation,
    )


def tier_to_human(tier: Tier) -> str:
    """One-line human-readable name for the tier (used by the UI badge)."""
    return {
        Tier.TIER_0_RULES: "Rules only",
        Tier.TIER_1_XGB: "Hybrid (XGBoost + Isolation Forest)",
        Tier.TIER_2_GNN: "Hybrid + Graph Neural Network",
        Tier.TIER_3_DNN: "Hybrid + GNN + Deep Neural Network",
        Tier.TIER_4_LLM_AGENT: "Full ensemble + LLM Investigation",
        Tier.TIER_5_JUDGE: "Full ensemble + LLM-as-Judge",
    }.get(tier, tier.value)
