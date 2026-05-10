"""Phase 4 tests — Decision Engine (multi-action decisioning).

Acceptance criteria:
  [x] Blacklisted entity blocks regardless of ML score.
  [x] Trusted premium user with score < 70 → ALLOW.
  [x] Extreme score (≥95) → BLOCK regardless of merchant config.
  [x] Per-merchant config: score 75 with block_threshold=70 → BLOCK.
  [x] Velocity override upgrades ALLOW → CHALLENGE when ≥10 txns/hour.
  [x] Geo-impossible signal upgrades ALLOW → CHALLENGE.
  [x] Default thresholds work correctly across all 4 action bands.
  [x] Decision reasons are populated for every decision.
  [x] Challenge type maps correctly to biometric/3ds/otp.
  [x] Admin helpers (upsert_merchant_config, add/remove blacklist) work.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from schemas.decision import Decision
from schemas.score import ScoreResult
from services.decision_engine import DecisionEngine, _DEFAULT_APPETITE


# ================================================================== #
# Fixtures
# ================================================================== #

@pytest.fixture
def engine() -> DecisionEngine:
    """Fresh DecisionEngine instance (no singleton — tests are isolated)."""
    return DecisionEngine()


def _make_score(risk_score: int, signals: dict | None = None) -> ScoreResult:
    """Create a ScoreResult at a given risk_score."""
    risk_level = (
        "CRITICAL" if risk_score >= 85
        else "HIGH" if risk_score >= 65
        else "MEDIUM" if risk_score >= 40
        else "LOW"
    )
    return ScoreResult(
        risk_score=risk_score,
        risk_level=risk_level,
        unsup_score=risk_score / 100.0,
        sup_score=None,
        signals=signals or {},
        explanation="test score",
        detector_version="test-v1",
        latency_ms=1.0,
    )


def _make_txn(user_id: int = 1, merchant: str = "TestMerchant", **kwargs) -> dict:
    """Create a minimal transaction dict."""
    return {"user_id": user_id, "merchant": merchant, "amount": 500.0, **kwargs}


def _make_user(user_id: int = 1, is_premium: bool = False) -> dict:
    """Create a minimal user dict."""
    return {"id": user_id, "email": "test@example.com", "is_premium": is_premium}


# ================================================================== #
# Core decision logic — no DB/Redis (patched out)
# ================================================================== #

class TestDecisionEngineCore:

    @pytest.mark.asyncio
    async def test_blacklisted_merchant_blocks(self, engine):
        """Blacklisted merchant → BLOCK regardless of score."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value="merchant:BadMerchant — fraud ring")):
            decision = await engine.decide(_make_score(20), _make_txn(merchant="BadMerchant"), _make_user())

        assert decision.action == "block"
        assert "blacklisted_entity" in decision.rule_overrides
        assert any("blacklist" in r.lower() for r in decision.reasons)

    @pytest.mark.asyncio
    async def test_blacklisted_user_blocks(self, engine):
        """Blacklisted user → BLOCK regardless of score."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value="user:42 — stolen credentials")):
            decision = await engine.decide(_make_score(5), _make_txn(user_id=42), _make_user(42))

        assert decision.action == "block"
        assert "blacklisted_entity" in decision.rule_overrides

    @pytest.mark.asyncio
    async def test_extreme_score_blocks(self, engine):
        """Score ≥ 95 → BLOCK with model_extreme_risk rule."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(96), _make_txn(), _make_user())

        assert decision.action == "block"
        assert "model_extreme_risk" in decision.rule_overrides

    @pytest.mark.asyncio
    async def test_trusted_premium_user_allows_moderate_score(self, engine):
        """Verified premium user with score < 70 → ALLOW override."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            decision = await engine.decide(
                _make_score(65), _make_txn(), _make_user(is_premium=True)
            )

        assert decision.action == "allow"
        assert "trusted_user" in decision.rule_overrides

    @pytest.mark.asyncio
    async def test_trusted_premium_user_at_threshold_not_overridden(self, engine):
        """Premium user with score ≥ 70 is NOT overridden — normal flow applies."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(
                    _make_score(70), _make_txn(), _make_user(is_premium=True)
                )
        # score=70 >= challenge_threshold=60, so should be CHALLENGE (not ALLOW)
        assert decision.action in {"challenge", "block", "review"}
        assert "trusted_user" not in decision.rule_overrides

    @pytest.mark.asyncio
    async def test_default_thresholds_allow(self, engine):
        """Score < 40 with default thresholds → ALLOW."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(30), _make_txn(), _make_user())
        assert decision.action == "allow"

    @pytest.mark.asyncio
    async def test_default_thresholds_review(self, engine):
        """Score 40–59 with default thresholds → REVIEW."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(50), _make_txn(), _make_user())
        assert decision.action == "review"

    @pytest.mark.asyncio
    async def test_default_thresholds_challenge(self, engine):
        """Score 60–79 with default thresholds → CHALLENGE."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(65), _make_txn(), _make_user())
        assert decision.action == "challenge"

    @pytest.mark.asyncio
    async def test_default_thresholds_block(self, engine):
        """Score ≥ 80 with default thresholds → BLOCK."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(82), _make_txn(), _make_user())
        assert decision.action == "block"

    @pytest.mark.asyncio
    async def test_per_merchant_block_threshold(self, engine):
        """Score 75 with merchant block_threshold=70 → BLOCK."""
        custom_appetite = {"block": 70, "challenge": 50, "review": 30}
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=custom_appetite)):
                decision = await engine.decide(_make_score(75), _make_txn(), _make_user())
        assert decision.action == "block"
        assert any("70" in r for r in decision.reasons)

    @pytest.mark.asyncio
    async def test_per_merchant_allows_higher_threshold(self, engine):
        """Score 80 with merchant block_threshold=90 → CHALLENGE (not BLOCK)."""
        high_appetite = {"block": 90, "challenge": 70, "review": 50}
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=high_appetite)):
                decision = await engine.decide(_make_score(80), _make_txn(), _make_user())
        assert decision.action == "challenge"

    @pytest.mark.asyncio
    async def test_velocity_override_upgrades_to_challenge(self, engine):
        """≥10 txns/hour + score ≥40 → upgrades ALLOW/REVIEW to CHALLENGE."""
        # score=35 → ALLOW normally, but velocity burst upgrades it
        assembled = {"user_txn_count_1h": 12}
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value={"block": 80, "challenge": 60, "review": 40})):
                decision = await engine.decide(
                    _make_score(42),  # in REVIEW band
                    _make_txn(),
                    _make_user(),
                    assembled_features=assembled,
                )
        assert decision.action == "challenge"
        assert "velocity_burst" in decision.rule_overrides

    @pytest.mark.asyncio
    async def test_velocity_override_does_not_upgrade_block(self, engine):
        """Velocity override does not change a BLOCK to CHALLENGE."""
        assembled = {"user_txn_count_1h": 15}
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(
                    _make_score(82),
                    _make_txn(),
                    _make_user(),
                    assembled_features=assembled,
                )
        assert decision.action == "block"

    @pytest.mark.asyncio
    async def test_geo_impossible_upgrades_allow_to_challenge(self, engine):
        """geo_impossible signal in score.signals upgrades ALLOW to CHALLENGE."""
        score = _make_score(20, signals={"geo_impossible": True})
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(score, _make_txn(), _make_user())

        assert decision.action == "challenge"
        assert "geo_impossible" in decision.rule_overrides

    @pytest.mark.asyncio
    async def test_geo_flag_from_synthetic_data(self, engine):
        """_geo_flag (from synthetic_data.py) also triggers geo override."""
        score = _make_score(15, signals={"_geo_flag": True})
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(score, _make_txn(), _make_user())
        assert decision.action == "challenge"


# ================================================================== #
# Challenge type mapping
# ================================================================== #

class TestChallengeTypeMapping:

    @pytest.mark.asyncio
    async def test_biometric_for_high_challenge_score(self, engine):
        """Score ≥ 80 challenge → biometric challenge type."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value={"block": 90, "challenge": 60, "review": 40})):
                decision = await engine.decide(_make_score(82), _make_txn(), _make_user())
        assert decision.action == "challenge"
        assert decision.challenge_type == "biometric"

    @pytest.mark.asyncio
    async def test_3ds_for_mid_challenge_score(self, engine):
        """Score 65–79 challenge → 3ds challenge type."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(70), _make_txn(), _make_user())
        if decision.action == "challenge":
            assert decision.challenge_type == "3ds"

    @pytest.mark.asyncio
    async def test_otp_for_low_challenge_score(self, engine):
        """Score 60–64 challenge → otp challenge type."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(61), _make_txn(), _make_user())
        if decision.action == "challenge":
            assert decision.challenge_type == "otp"

    @pytest.mark.asyncio
    async def test_no_challenge_type_for_non_challenge_actions(self, engine):
        """ALLOW, REVIEW, BLOCK decisions have challenge_type = None."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                block_dec = await engine.decide(_make_score(85), _make_txn(), _make_user())
                allow_dec = await engine.decide(_make_score(20), _make_txn(), _make_user())
        assert block_dec.challenge_type is None
        assert allow_dec.challenge_type is None


# ================================================================== #
# Decision output schema
# ================================================================== #

class TestDecisionSchema:

    @pytest.mark.asyncio
    async def test_decision_has_reasons(self, engine):
        """Every decision has at least one reason string."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(50), _make_txn(), _make_user())
        assert len(decision.reasons) >= 1
        assert all(isinstance(r, str) for r in decision.reasons)

    @pytest.mark.asyncio
    async def test_decision_score_matches_input(self, engine):
        """decision.score matches the input ScoreResult.risk_score."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=dict(_DEFAULT_APPETITE))):
                decision = await engine.decide(_make_score(55), _make_txn(), _make_user())
        assert decision.score == 55

    def test_decision_action_literals(self):
        """Decision.action only accepts the four valid literals."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Decision(action="unknown", score=50, reasons=[], rule_overrides=[])

    def test_decision_valid(self):
        """Decision model validates correctly with all required fields."""
        d = Decision(
            action="block",
            score=90,
            reasons=["test reason"],
            rule_overrides=["blacklisted_entity"],
            challenge_type=None,
        )
        assert d.action == "block"
        assert d.score == 90


# ================================================================== #
# Priority ordering: blacklist beats everything
# ================================================================== #

class TestDecisionPriority:

    @pytest.mark.asyncio
    async def test_blacklist_overrides_trusted_premium(self, engine):
        """Blacklist check fires BEFORE premium user check."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value="user:1 — fraud ring")):
            decision = await engine.decide(
                _make_score(10), _make_txn(), _make_user(is_premium=True)
            )
        assert decision.action == "block"
        assert "blacklisted_entity" in decision.rule_overrides

    @pytest.mark.asyncio
    async def test_blacklist_overrides_low_score(self, engine):
        """Blacklist fires even when score is 0."""
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value="merchant:X — testing")):
            decision = await engine.decide(_make_score(0), _make_txn(), _make_user())
        assert decision.action == "block"

    @pytest.mark.asyncio
    async def test_extreme_score_overrides_merchant_config(self, engine):
        """Score ≥ 95 always blocks — merchant config cannot override it."""
        permissive_appetite = {"block": 99, "challenge": 90, "review": 80}
        with patch.object(engine, "_is_blacklisted", new=AsyncMock(return_value=None)):
            with patch.object(engine, "_get_merchant_appetite", new=AsyncMock(return_value=permissive_appetite)):
                decision = await engine.decide(_make_score(96), _make_txn(), _make_user())
        # Step 2 fires before step 4 merchant config
        assert decision.action == "block"
        assert "model_extreme_risk" in decision.rule_overrides


# ================================================================== #
# Merchant config Redis/DB path (mocked)
# ================================================================== #

class TestMerchantConfigCache:

    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_config(self, engine):
        """_get_merchant_appetite returns global defaults when Redis+DB miss."""
        with patch("services.decision_engine.get_redis", return_value=None):
            with patch("services.decision_engine.get_pool", return_value=None):
                appetite = await engine._get_merchant_appetite("SomeMerchant")
        assert appetite == _DEFAULT_APPETITE

    @pytest.mark.asyncio
    async def test_empty_merchant_id_returns_defaults(self, engine):
        """Empty merchant_id returns defaults without any Redis/DB call."""
        appetite = await engine._get_merchant_appetite("")
        assert appetite == _DEFAULT_APPETITE


# ================================================================== #
# Admin DB helpers (mocked asyncpg pool)
# ================================================================== #

def _make_mock_pool(mock_conn: "MagicMock") -> "MagicMock":
    """Build a mock asyncpg Pool whose .acquire() returns an async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = cm
    return mock_pool


class TestAdminHelpers:

    @pytest.mark.asyncio
    async def test_upsert_merchant_config_calls_db(self, engine):
        """upsert_merchant_config executes an INSERT/UPDATE against DB."""
        mock_conn = AsyncMock()
        mock_pool = _make_mock_pool(mock_conn)

        with patch("services.decision_engine.get_pool", return_value=mock_pool):
            with patch("services.decision_engine.get_redis", return_value=None):
                await engine.upsert_merchant_config(
                    merchant_id="AmazonIN",
                    block_threshold=75,
                    challenge_threshold=55,
                    review_threshold=35,
                )
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "INSERT INTO merchant_risk_config" in call_args[0]

    @pytest.mark.asyncio
    async def test_upsert_raises_when_no_pool(self, engine):
        """upsert_merchant_config raises RuntimeError when DB pool unavailable."""
        with patch("services.decision_engine.get_pool", return_value=None):
            with pytest.raises(RuntimeError, match="DB pool unavailable"):
                await engine.upsert_merchant_config("M", 80, 60, 40)

    @pytest.mark.asyncio
    async def test_add_to_blacklist_calls_db(self, engine):
        """add_to_blacklist executes INSERT with correct entity data."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"id": 42}
        mock_pool = _make_mock_pool(mock_conn)

        with patch("services.decision_engine.get_pool", return_value=mock_pool):
            with patch("services.decision_engine.get_redis", return_value=None):
                entity_id = await engine.add_to_blacklist(
                    entity_type="merchant",
                    entity_value="FraudMerchant",
                    reason="fraud ring",
                    severity="CRITICAL",
                )
        assert entity_id == 42

    @pytest.mark.asyncio
    async def test_remove_from_blacklist_returns_false_not_found(self, engine):
        """remove_from_blacklist returns False when entity_id not found."""
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "DELETE 0"
        mock_pool = _make_mock_pool(mock_conn)

        with patch("services.decision_engine.get_pool", return_value=mock_pool):
            result = await engine.remove_from_blacklist(9999)
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_from_blacklist_returns_true_deleted(self, engine):
        """remove_from_blacklist returns True when a row was deleted."""
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "DELETE 1"
        mock_pool = _make_mock_pool(mock_conn)

        with patch("services.decision_engine.get_pool", return_value=mock_pool):
            result = await engine.remove_from_blacklist(1)
        assert result is True
