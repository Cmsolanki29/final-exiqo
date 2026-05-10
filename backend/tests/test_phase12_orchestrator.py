"""Phase 12 — Orchestrator + LLM-as-Judge unit tests.

Database-touching paths (the ``_persist`` helper, and Phase 9 / 11
integration) are short-circuited by monkey-patching get_pool to None.
LLM calls are entirely mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# --------------------------------------------------------------------- #
# 1. Routing policy is pure logic — exercise every branch
# --------------------------------------------------------------------- #


def _policy(**overrides):
    from services.phase_12_orchestrator.routing_policy import RoutingPolicy
    base = dict(
        enabled=True,
        auto_investigate=True,
        judge_enabled=True,
        sync_investigation=False,
        tier0_max=30,
        tier1_max=60,
        tier2_max=75,
        tier3_max=85,
        dnn_disagree_delta=25.0,
    )
    base.update(overrides)
    return RoutingPolicy(**base)


def test_routing_tier0_below_threshold():
    from services.phase_12_orchestrator.routing_policy import Tier, route
    decision = route(risk_score=10, signals={}, rule_overrides=[], policy=_policy())
    assert decision.tier == Tier.TIER_0_RULES
    assert decision.invoke_judge is False
    assert decision.invoke_investigation is False


def test_routing_tier1_standard_band():
    from services.phase_12_orchestrator.routing_policy import Tier, route
    decision = route(risk_score=45, signals={}, rule_overrides=[], policy=_policy())
    assert decision.tier == Tier.TIER_1_XGB
    assert decision.invoke_judge is False


def test_routing_tier2_requires_gnn_signal():
    from services.phase_12_orchestrator.routing_policy import Tier, route
    # 65 lands in [60,75) — Tier 2 only when GNN embedding signal is present.
    with_gnn = route(
        risk_score=65,
        signals={"gnn_emb_dim": 64, "gnn_emb_norm": 1.0},
        rule_overrides=[],
        policy=_policy(),
    )
    assert with_gnn.tier == Tier.TIER_2_GNN

    without_gnn = route(risk_score=65, signals={}, rule_overrides=[], policy=_policy())
    assert without_gnn.tier == Tier.TIER_1_XGB


def test_routing_tier3_requires_dnn_shadow():
    from services.phase_12_orchestrator.routing_policy import Tier, route
    decision = route(
        risk_score=80,
        signals={"dnn_shadow_score": 78, "gnn_emb_dim": 64},
        rule_overrides=[],
        policy=_policy(),
    )
    assert decision.tier == Tier.TIER_3_DNN
    # Tier 3 always invokes the judge per policy.
    assert decision.invoke_judge is True


def test_routing_tier4_high_risk_invokes_judge_and_optionally_investigation():
    from services.phase_12_orchestrator.routing_policy import Tier, route

    high = route(risk_score=92, signals={}, rule_overrides=[], policy=_policy())
    assert high.tier == Tier.TIER_4_LLM_AGENT
    assert high.invoke_judge is True
    assert high.invoke_investigation is False  # sync_investigation off by default

    sync_high = route(
        risk_score=92, signals={}, rule_overrides=[],
        policy=_policy(sync_investigation=True),
    )
    assert sync_high.invoke_investigation is True


def test_routing_judge_fires_on_rules_vs_ml_conflict():
    """Low score but a rule override fired → judge should be consulted."""
    from services.phase_12_orchestrator.routing_policy import route
    decision = route(
        risk_score=20,
        signals={},
        rule_overrides=["blacklisted_entity"],
        policy=_policy(),
    )
    assert decision.invoke_judge is True
    assert "rules_vs_ml_conflict" in decision.reason


def test_routing_judge_fires_on_dnn_divergence():
    from services.phase_12_orchestrator.routing_policy import route
    # Score 45 (Tier 1) + DNN says 80 → divergence = 35 > delta 25.
    decision = route(
        risk_score=45,
        signals={"dnn_shadow_score": 80},
        rule_overrides=[],
        policy=_policy(dnn_disagree_delta=25.0),
    )
    assert decision.invoke_judge is True
    assert "dnn_divergence" in decision.reason


def test_routing_disabled_never_invokes_judge():
    from services.phase_12_orchestrator.routing_policy import route
    decision = route(
        risk_score=92,
        signals={"dnn_shadow_score": 50},  # divergence
        rule_overrides=["whatever"],
        policy=_policy(enabled=False),
    )
    assert decision.invoke_judge is False
    assert decision.invoke_investigation is False


# --------------------------------------------------------------------- #
# 2. Action ladder: judge can only escalate, never relax
# --------------------------------------------------------------------- #


def test_action_ladder_escalation_check():
    from services.phase_12_orchestrator.orchestrator import _is_escalation
    assert _is_escalation("allow", "review") is True
    assert _is_escalation("review", "challenge") is True
    assert _is_escalation("challenge", "block") is True
    assert _is_escalation("block", "challenge") is False
    assert _is_escalation("allow", "allow") is False
    assert _is_escalation("review", "allow") is False


# --------------------------------------------------------------------- #
# 3. LLM-as-Judge: mocked Groq returns shaped JSON
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_judge_returns_parsed_payload(monkeypatch):
    from services.phase_12_orchestrator import llm_judge as J

    fake_text = (
        '{"agree": false, "confidence": 0.83, '
        '"concerns": ["DNN shadow 89 disagrees with baseline 55"], '
        '"suggested_action": "review", "narrative": "Recommend review."}'
    )

    fake_message = type("M", (), {"content": fake_text, "tool_calls": None})()
    fake_result = type("R", (), {})()
    fake_result.message = fake_message
    fake_result.input_tokens = 120
    fake_result.output_tokens = 80
    fake_result.model = "llama-3.3-70b-versatile"
    fake_result.finish_reason = "stop"
    fake_result.latency_ms = 50
    fake_result.text_content = fake_text

    monkeypatch.setattr(J.groq, "is_available", lambda: True)
    monkeypatch.setattr(J.groq, "chat", AsyncMock(return_value=fake_result))
    monkeypatch.setattr(J.groq, "parse_json_response",
                        lambda text: __import__("json").loads(text))

    # Stub out budget guard (no DB in tests).
    class _StubGuard:
        async def check_and_reserve(self, *a, **kw): return True
        async def record_actual(self, *a, **kw): return None

    monkeypatch.setattr(J, "_guard", _StubGuard())

    result = await J.judge_decision(
        transaction={"amount": 12000, "merchant": "TestMerchant"},
        baseline_score=55,
        baseline_action="allow",
        baseline_reasons=["Score below threshold"],
        baseline_overrides=[],
        signals={"dnn_shadow_score": 89},
        investigation=None,
    )
    assert result.invoked is True
    assert result.agree is False
    assert result.confidence == pytest.approx(0.83)
    assert result.suggested_action == "review"
    assert result.cost_usd > 0
    assert result.input_tokens == 120


@pytest.mark.asyncio
async def test_judge_returns_unavailable_when_groq_missing(monkeypatch):
    from services.phase_12_orchestrator import llm_judge as J

    monkeypatch.setattr(J.groq, "is_available", lambda: False)
    result = await J.judge_decision(
        transaction={}, baseline_score=70, baseline_action="review",
        baseline_reasons=[], baseline_overrides=[], signals={}, investigation=None,
    )
    assert result.invoked is False
    assert result.error == "groq_unavailable"


@pytest.mark.asyncio
async def test_judge_clamps_invalid_confidence(monkeypatch):
    from services.phase_12_orchestrator import llm_judge as J

    fake_text = '{"agree": true, "confidence": "not a float", "narrative": ""}'
    fake_message = type("M", (), {"content": fake_text, "tool_calls": None})()
    fake_result = type("R", (), {})()
    fake_result.message = fake_message
    fake_result.input_tokens = 50
    fake_result.output_tokens = 10
    fake_result.model = "llama-3.3-70b-versatile"
    fake_result.finish_reason = "stop"
    fake_result.latency_ms = 12
    fake_result.text_content = fake_text

    monkeypatch.setattr(J.groq, "is_available", lambda: True)
    monkeypatch.setattr(J.groq, "chat", AsyncMock(return_value=fake_result))
    monkeypatch.setattr(J.groq, "parse_json_response",
                        lambda text: __import__("json").loads(text))

    class _StubGuard:
        async def check_and_reserve(self, *a, **kw): return True
        async def record_actual(self, *a, **kw): return None
    monkeypatch.setattr(J, "_guard", _StubGuard())

    result = await J.judge_decision(
        transaction={}, baseline_score=40, baseline_action="allow",
        baseline_reasons=[], baseline_overrides=[], signals={}, investigation=None,
    )
    assert 0.0 <= result.confidence <= 1.0
    assert result.suggested_action is None  # not present in payload → None


# --------------------------------------------------------------------- #
# 4. End-to-end orchestrator with everything mocked
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_orchestrator_passthrough_when_disabled(monkeypatch):
    """When PHASE_12_ORCHESTRATOR_ENABLED is False, the final action must
    equal the baseline action — no judge, no investigation."""
    from services.phase_12_orchestrator import orchestrator as orch
    from schemas.score import ScoreResult
    from schemas.decision import Decision

    monkeypatch.setenv("PHASE_12_ORCHESTRATOR_ENABLED", "false")
    from core import config as core_cfg
    core_cfg.get_settings.cache_clear()  # type: ignore[attr-defined]

    fake_score = ScoreResult.cold_start(detector_version="test", latency_ms=1)
    fake_decision = Decision(
        action="review", score=70,
        reasons=["test"], rule_overrides=[], challenge_type="otp",
    )

    async def _fake_score(*a, **kw): return fake_score
    async def _fake_decide(*a, **kw): return fake_decision
    async def _fake_persist(**kw): return "fake-uuid"

    monkeypatch.setattr(orch.hybrid_scorer, "score", _fake_score)
    monkeypatch.setattr(orch.decision_engine, "decide", _fake_decide)
    monkeypatch.setattr(orch, "_persist", _fake_persist)

    out = await orch.decide(
        user_id=42, txn={"id": 1, "merchant": "Test"}, user={"id": 42},
    )
    assert out.final_action == "review"
    assert out.judge is None
    assert out.investigation is None


@pytest.mark.asyncio
async def test_orchestrator_judge_can_escalate_with_high_confidence(monkeypatch):
    """When enabled and the judge says 'block' with high confidence, the
    final action must escalate from baseline 'review' → 'block'."""
    from services.phase_12_orchestrator import orchestrator as orch
    from services.phase_12_orchestrator.llm_judge import JudgeResult
    from schemas.score import ScoreResult
    from schemas.decision import Decision

    monkeypatch.setenv("PHASE_12_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.setenv("PHASE_12_JUDGE_ENABLED", "true")
    monkeypatch.setenv("PHASE_12_AUTO_INVESTIGATE", "false")
    monkeypatch.setenv("PHASE_12_JUDGE_MIN_CONFIDENCE", "0.7")
    from core import config as core_cfg
    core_cfg.get_settings.cache_clear()  # type: ignore[attr-defined]

    # Force a score in the Tier-3 band so the judge is invoked.
    score = ScoreResult.cold_start(detector_version="test", latency_ms=1)
    score.risk_score = 80  # type: ignore[attr-defined]
    score.signals = {"dnn_shadow_score": 82}  # type: ignore[attr-defined]
    baseline = Decision(
        action="review", score=80,
        reasons=["baseline"], rule_overrides=[], challenge_type=None,
    )

    fake_judge = JudgeResult(
        invoked=True, agree=False, confidence=0.85,
        concerns=["x"], suggested_action="block",
        narrative="block it", model="m", input_tokens=10, output_tokens=10,
        cost_usd=0.0001, latency_ms=10,
    )

    async def _score(*a, **kw): return score
    async def _decide(*a, **kw): return baseline
    async def _judge(**kw): return fake_judge
    async def _persist(**kw): return "fake-uuid"

    monkeypatch.setattr(orch.hybrid_scorer, "score", _score)
    monkeypatch.setattr(orch.decision_engine, "decide", _decide)
    monkeypatch.setattr(orch, "judge_decision", _judge)
    monkeypatch.setattr(orch, "_persist", _persist)

    out = await orch.decide(
        user_id=1, txn={"id": 99, "merchant": "x"}, user={"id": 1},
    )
    assert out.final_action == "block"
    assert any("escalated to block" in r for r in out.final_reasons)
    assert out.judge is not None
    assert out.judge.confidence == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_orchestrator_judge_low_confidence_does_not_override(monkeypatch):
    from services.phase_12_orchestrator import orchestrator as orch
    from services.phase_12_orchestrator.llm_judge import JudgeResult
    from schemas.score import ScoreResult
    from schemas.decision import Decision

    monkeypatch.setenv("PHASE_12_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.setenv("PHASE_12_JUDGE_ENABLED", "true")
    monkeypatch.setenv("PHASE_12_AUTO_INVESTIGATE", "false")
    monkeypatch.setenv("PHASE_12_JUDGE_MIN_CONFIDENCE", "0.7")
    from core import config as core_cfg
    core_cfg.get_settings.cache_clear()  # type: ignore[attr-defined]

    score = ScoreResult.cold_start(detector_version="test", latency_ms=1)
    score.risk_score = 88  # type: ignore[attr-defined]
    baseline = Decision(
        action="review", score=88,
        reasons=["baseline"], rule_overrides=[], challenge_type=None,
    )
    timid_judge = JudgeResult(
        invoked=True, agree=False, confidence=0.55,  # below 0.7 cutoff
        concerns=["meh"], suggested_action="block", narrative="",
        model="m", input_tokens=1, output_tokens=1, cost_usd=0, latency_ms=1,
    )

    async def _score(*a, **kw): return score
    async def _decide(*a, **kw): return baseline
    async def _judge(**kw): return timid_judge
    async def _persist(**kw): return "id"

    monkeypatch.setattr(orch.hybrid_scorer, "score", _score)
    monkeypatch.setattr(orch.decision_engine, "decide", _decide)
    monkeypatch.setattr(orch, "judge_decision", _judge)
    monkeypatch.setattr(orch, "_persist", _persist)

    out = await orch.decide(
        user_id=1, txn={"id": 11, "merchant": "x"}, user={"id": 1},
    )
    # Judge ran but its low-confidence opinion was logged-only.
    assert out.final_action == "review"
    assert out.judge.confidence == pytest.approx(0.55)
