"""Phase 9 — LLM Investigation Agent tests.

Strategy
--------
We never call the real Groq API in tests.  The OpenAI client is patched
at ``services.risk_common.groq_llm_client.get_client`` to return an
``AsyncMock`` whose ``chat.completions.create`` returns a hand-crafted
response sequence.

Tests cover:
  * PII redactor — happy path + edge cases.
  * Budget guard — over-cap raises BudgetExceeded; record_actual upserts.
  * Tool: FraudPatternTool — purely synchronous logic, no DB required.
  * Tool: BlacklistTool — static layer match.
  * Agent: end-to-end with one tool call then a final JSON reply.
  * Agent: graceful fall-back when LLM unavailable.
  * Agent: confidence < 0.6 forces decision='inconclusive'.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------- #
# PII redactor
# ---------------------------------------------------------------------- #
class TestPIIRedactor:
    def test_redacts_phone_email_pan_ip_account(self) -> None:
        from services.risk_common.pii_redactor import redact

        txt = (
            "Contact: rahul@example.com  Phone: +91 9876543210  "
            "PAN: ABCDE1234F  Aadhaar: 1234 5678 9012  "
            "IP: 203.0.113.42  Account: 123456789012"
        )
        out = redact(txt)
        assert "rahul@example.com" not in out
        assert "9876543210" not in out
        assert "ABCDE1234F" not in out
        assert "1234 5678 9012" not in out
        assert "203.0.113.42" not in out
        assert "<EMAIL>" in out
        assert "<PHONE>" in out
        assert "<PAN>" in out
        assert "<AADHAAR>" in out
        assert "<IP>" in out

    def test_redact_dict_recurses(self) -> None:
        from services.risk_common.pii_redactor import redact_dict

        payload = {
            "user": {"email": "x@y.com", "phone": "9988776655"},
            "history": [{"merchant": "test 9988776655 stuff"}],
            "amount": 1234.5,
            "is_fraud": False,
        }
        out = redact_dict(payload)
        assert out["user"]["email"] == "<EMAIL>"
        assert out["user"]["phone"] == "<PHONE>"
        assert "<PHONE>" in out["history"][0]["merchant"]
        # Non-string scalars unchanged
        assert out["amount"] == 1234.5
        assert out["is_fraud"] is False


# ---------------------------------------------------------------------- #
# Budget guard
# ---------------------------------------------------------------------- #
class TestBudgetGuard:
    @pytest.mark.asyncio
    async def test_over_cap_raises(self, monkeypatch) -> None:
        from services.risk_common import budget_guard as bg_mod

        # Patch the cap to a tiny number
        from core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "PHASE_9_DAILY_BUDGET_USD", 0.001)

        # Fake the asyncpg pool: row says we already spent $0.0009
        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value={"cost_usd": 0.0009})
        fake_conn.execute = AsyncMock()

        class _AcquireCtx:
            async def __aenter__(self) -> AsyncMock:
                return fake_conn
            async def __aexit__(self, *args) -> bool:
                return False

        fake_pool = MagicMock()
        fake_pool.acquire = MagicMock(return_value=_AcquireCtx())

        monkeypatch.setattr(bg_mod, "get_pool", lambda: fake_pool)

        with pytest.raises(bg_mod.BudgetExceeded):
            await bg_mod.budget_guard.check_and_reserve("llama-3.3-70b-versatile", 0.0005)

    @pytest.mark.asyncio
    async def test_within_cap_allows(self, monkeypatch) -> None:
        from services.risk_common import budget_guard as bg_mod
        from core.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "PHASE_9_DAILY_BUDGET_USD", 5.00)

        fake_conn = AsyncMock()
        fake_conn.fetchrow = AsyncMock(return_value=None)  # no spend today
        fake_conn.execute = AsyncMock()

        class _AcquireCtx:
            async def __aenter__(self) -> AsyncMock:
                return fake_conn
            async def __aexit__(self, *args) -> bool:
                return False

        fake_pool = MagicMock()
        fake_pool.acquire = MagicMock(return_value=_AcquireCtx())
        monkeypatch.setattr(bg_mod, "get_pool", lambda: fake_pool)

        ok = await bg_mod.budget_guard.check_and_reserve("llama-3.3-70b-versatile", 0.001)
        assert ok is True

    def test_cost_from_tokens_uses_pricing_table(self) -> None:
        from services.risk_common.budget_guard import cost_from_tokens
        # 1M input + 1M output @ $0.59 + $0.79
        cost = cost_from_tokens("llama-3.3-70b-versatile", 1_000_000, 1_000_000)
        assert abs(cost - (0.59 + 0.79)) < 1e-9


# ---------------------------------------------------------------------- #
# Tool: FraudPatternTool — pure logic, no DB
# ---------------------------------------------------------------------- #
class TestFraudPatternTool:
    @pytest.mark.asyncio
    async def test_kyc_scam_matches(self) -> None:
        from services.phase_9_agent.tools.fraud_pattern_tool import FraudPatternTool

        out = await FraudPatternTool().execute({
            "merchant": "kyc update agent",
            "category": "transfer",
            "amount": 4500,
        })
        assert out.success is True
        ids = [m["id"] for m in out.data["matches"]]
        assert "kyc_update_scam" in ids

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self) -> None:
        from services.phase_9_agent.tools.fraud_pattern_tool import FraudPatternTool

        out = await FraudPatternTool().execute({
            "merchant": "Swiggy",
            "category": "Food",
            "amount": 320,
        })
        assert out.success is True
        assert out.data["match_count"] == 0


# ---------------------------------------------------------------------- #
# Tool: BlacklistTool — static layer
# ---------------------------------------------------------------------- #
class TestBlacklistTool:
    @pytest.mark.asyncio
    async def test_static_hit(self, monkeypatch) -> None:
        from services.phase_9_agent.tools.blacklist_tool import BlacklistTool
        from services.phase_9_agent.tools import blacklist_tool as mod

        # Force the dynamic layer to be unavailable
        def _raise(*a, **kw):
            raise RuntimeError("no pool")
        monkeypatch.setattr(mod, "get_pool", _raise)

        out = await BlacklistTool().execute({"entity": "fake-kyc-update-agency"})
        assert out.success is True
        assert out.data["blacklisted"] is True
        assert any(h["match"] == "fake-kyc-update" for h in out.data["hits"])


# ---------------------------------------------------------------------- #
# Agent end-to-end (mocked Groq)
# ---------------------------------------------------------------------- #
def _make_mock_response(*, content: str | None = None,
                        tool_calls: list | None = None,
                        prompt_tokens: int = 100,
                        completion_tokens: int = 50,
                        finish_reason: str = "stop") -> SimpleNamespace:
    """Build an OpenAI-shaped response object."""
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    return SimpleNamespace(choices=[choice], usage=usage)


def _make_mock_tool_call(*, call_id: str, name: str, arguments_dict: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments_dict)),
    )


class TestAgent:
    @pytest.mark.asyncio
    async def test_agent_disabled_returns_inconclusive(self, monkeypatch) -> None:
        from services.phase_9_agent.agent import InvestigationAgent
        from core.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "PHASE_9_AGENT_ENABLED", False)

        agent = InvestigationAgent(tools=[])  # tools irrelevant when disabled
        result = await agent.investigate(
            transaction={"amount": 1000.0, "merchant": "X"},
            risk_score=80,
            user_id=1,
        )
        assert result["decision"] == "inconclusive"
        assert result["error"] == "phase_9_disabled"

    @pytest.mark.asyncio
    async def test_agent_llm_unavailable_returns_inconclusive(self, monkeypatch) -> None:
        from services.phase_9_agent.agent import InvestigationAgent
        from services.risk_common import groq_llm_client
        from core.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "PHASE_9_AGENT_ENABLED", True)
        monkeypatch.setattr(groq_llm_client, "is_available", lambda: False)

        agent = InvestigationAgent(tools=[])
        result = await agent.investigate(
            transaction={"amount": 1000.0, "merchant": "X"},
            risk_score=80,
            user_id=1,
        )
        assert result["decision"] == "inconclusive"
        assert result["error"] == "llm_unavailable"

    @pytest.mark.asyncio
    async def test_agent_end_to_end_one_tool_call_then_decision(self, monkeypatch) -> None:
        from services.phase_9_agent.agent import InvestigationAgent
        from services.phase_9_agent.tools.fraud_pattern_tool import FraudPatternTool
        from services.risk_common import groq_llm_client, budget_guard as bg_mod
        from core.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "PHASE_9_AGENT_ENABLED", True)

        # Two-step LLM scenario: round 1 -> tool call; round 2 -> final JSON
        first = _make_mock_response(
            content=None,
            finish_reason="tool_calls",
            tool_calls=[_make_mock_tool_call(
                call_id="call_1",
                name="check_fraud_patterns",
                arguments_dict={
                    "merchant": "kyc update", "category": "transfer", "amount": 4000,
                },
            )],
        )
        final_json = json.dumps({
            "decision": "fraud_confirmed",
            "confidence": 0.85,
            "narrative": "Matches KYC scam pattern with high confidence.",
            "key_evidence": ["kyc_update_scam"],
            "suggested_rules": [],
        })
        second = _make_mock_response(content=final_json)

        # Build a fake AsyncOpenAI client whose chat.completions.create
        # returns first, then second.
        async def _fake_create(**_kwargs) -> SimpleNamespace:
            return _fake_create.responses.pop(0)
        _fake_create.responses = [first, second]

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=_fake_create),
            ),
        )
        monkeypatch.setattr(groq_llm_client, "get_client", lambda: fake_client)
        monkeypatch.setattr(groq_llm_client, "is_available", lambda: True)

        # Mock budget guard to no-op (no DB)
        async def _ok(*_a, **_kw): return True
        async def _noop(*_a, **_kw): return None
        monkeypatch.setattr(bg_mod.budget_guard, "check_and_reserve", _ok)
        monkeypatch.setattr(bg_mod.budget_guard, "record_actual", _noop)

        agent = InvestigationAgent(tools=[FraudPatternTool()])
        result = await agent.investigate(
            transaction={
                "amount": 4000.0, "merchant": "KYC update", "category": "transfer",
                "description": "Bank KYC pending — please pay processing fee",
            },
            risk_score=72,
            user_id=1,
        )

        assert result["decision"] == "fraud_confirmed"
        assert 0.0 < result["confidence"] <= 1.0
        assert result["rounds_used"] == 2
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "check_fraud_patterns"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_agent_low_confidence_forced_inconclusive(self, monkeypatch) -> None:
        from services.phase_9_agent.agent import InvestigationAgent
        from services.risk_common import groq_llm_client, budget_guard as bg_mod
        from core.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "PHASE_9_AGENT_ENABLED", True)

        # Single LLM call returning low-confidence "fraud_confirmed"
        only = _make_mock_response(content=json.dumps({
            "decision": "fraud_confirmed",   # Model claims fraud...
            "confidence": 0.4,                # ...but is unsure.
            "narrative": "Not enough evidence.",
            "key_evidence": [],
            "suggested_rules": [],
        }))

        async def _fake_create(**_kwargs) -> SimpleNamespace:
            return only

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=_fake_create),
            ),
        )
        monkeypatch.setattr(groq_llm_client, "get_client", lambda: fake_client)
        monkeypatch.setattr(groq_llm_client, "is_available", lambda: True)

        async def _ok(*_a, **_kw): return True
        async def _noop(*_a, **_kw): return None
        monkeypatch.setattr(bg_mod.budget_guard, "check_and_reserve", _ok)
        monkeypatch.setattr(bg_mod.budget_guard, "record_actual", _noop)

        agent = InvestigationAgent(tools=[])
        result = await agent.investigate(
            transaction={"amount": 100.0, "merchant": "Coffee Shop"},
            risk_score=55,
            user_id=1,
        )
        # Even though the model said "fraud_confirmed", confidence < 0.6
        # forces "inconclusive" — this is our hard rule.
        assert result["decision"] == "inconclusive"
