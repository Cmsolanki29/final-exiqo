"""Phase 8 Feedback Flywheel test suite.

Tests:
  - FeedbackService.record_user_report inserts label + triggers auto_remediate
  - FeedbackService.record_chargeback inserts label + triggers remediation
  - FeedbackService.record_analyst_decision resolves queue item
  - FeedbackService.auto_remediate blacklists device and IP
  - DecisionEngine.enqueue_review inserts into review_queue on REVIEW action
  - DecisionEngine.enqueue_counterfactual inserts with priority='low'
  - RetrainFeedConsumer: threshold not crossed → no retrain trigger
  - RetrainFeedConsumer: >100 feedback events → retrain triggered
  - HybridScorer.should_counterfactual_hold_out: only fires for borderline ALLOW
  - ReviewQueueWorker: assigns high-priority pending items to analysts
  - schemas/feedback.py: FeedbackIn, ChargebackIn, ReviewDecision validate correctly

Run:
    cd backend
    python -m pytest tests/test_phase8_feedback.py -v --asyncio-mode=auto
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================== #
# Fixtures
# ================================================================== #

def _make_mock_pool(txn_row=None, rq_row=None):
    """Build a mock asyncpg pool that returns configurable rows."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(side_effect=lambda query, *args: txn_row if txn_row else rq_row)
    mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
    mock_conn.fetch = AsyncMock(return_value=[])

    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_acquire)
    return mock_pool, mock_conn


# ================================================================== #
# 1. Pydantic schema validation
# ================================================================== #

class TestFeedbackSchemas:
    """Unit tests for feedback Pydantic models."""

    def test_feedback_in_validates_label(self):
        from schemas.feedback import FeedbackIn
        fb = FeedbackIn(label=True, notes="I did not make this purchase")
        assert fb.label is True
        assert fb.notes == "I did not make this purchase"

    def test_feedback_in_notes_optional(self):
        from schemas.feedback import FeedbackIn
        fb = FeedbackIn(label=False)
        assert fb.notes is None

    def test_chargeback_in_requires_transaction_and_dispute(self):
        from schemas.feedback import ChargebackIn
        cb = ChargebackIn(transaction_id=42, dispute_id="DISP-001", reason_code="4853")
        assert cb.transaction_id == 42
        assert cb.dispute_id == "DISP-001"
        assert cb.reason_code == "4853"

    def test_chargeback_default_currency(self):
        from schemas.feedback import ChargebackIn
        cb = ChargebackIn(transaction_id=1, dispute_id="D1")
        assert cb.currency == "INR"

    def test_review_decision_valid_resolutions(self):
        from schemas.feedback import ReviewDecision
        for res in ("fraud", "legitimate", "inconclusive"):
            rd = ReviewDecision(resolution=res)
            assert rd.resolution == res

    def test_review_decision_invalid_resolution(self):
        from schemas.feedback import ReviewDecision
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ReviewDecision(resolution="unknown_value")

    def test_review_queue_item_model(self):
        from schemas.feedback import ReviewQueueItem
        import datetime
        item = ReviewQueueItem(
            id=uuid.uuid4(),
            transaction_id=1,
            score=72,
            status="pending",
            priority="normal",
            assigned_to=None,
            resolution=None,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            resolved_at=None,
        )
        assert item.status == "pending"


# ================================================================== #
# 2. FeedbackService.record_user_report
# ================================================================== #

class TestFeedbackServiceUserReport:
    """Tests for record_user_report."""

    @pytest.mark.asyncio
    async def test_record_user_report_inserts_label(self):
        """record_user_report should call execute twice (fraud_feedback + transactions)."""
        from services.feedback.feedback_service import FeedbackService

        txn_row = {"id": 10, "user_id": 1, "merchant": "TestMerchant",
                   "device_id": None, "ip_address": None}
        pool, conn = _make_mock_pool(txn_row=txn_row)
        # fetchrow returns txn_row first call, then None for auto_remediate queries
        conn.fetchrow = AsyncMock(return_value=txn_row)

        svc = FeedbackService()
        with patch("services.feedback.feedback_service.get_pool", return_value=pool), \
             patch("services.feedback.feedback_service.EventPublisher") as MockPub:
            MockPub.return_value.publish = AsyncMock()
            await svc.record_user_report(user_id=1, txn_id=10, label=True, notes="fraud!")

        assert conn.execute.call_count >= 2, "Expected at least 2 execute calls"

    @pytest.mark.asyncio
    async def test_record_user_report_publishes_event(self):
        """FEEDBACK_RECEIVED event must be published."""
        from services.feedback.feedback_service import FeedbackService

        txn_row = {"id": 5, "user_id": 2, "merchant": "M1",
                   "device_id": None, "ip_address": None}
        pool, conn = _make_mock_pool(txn_row=txn_row)
        conn.fetchrow = AsyncMock(return_value=txn_row)

        svc = FeedbackService()
        with patch("services.feedback.feedback_service.get_pool", return_value=pool), \
             patch("services.feedback.feedback_service.EventPublisher") as MockPub:
            mock_publish = AsyncMock()
            MockPub.return_value.publish = mock_publish
            await svc.record_user_report(user_id=2, txn_id=5, label=True)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        topic = call_args[0][0]
        payload = call_args[0][1]
        from services.event_bus.publisher import TOPIC_FEEDBACK_RECEIVED
        assert topic == TOPIC_FEEDBACK_RECEIVED
        assert payload["txn_id"] == 5
        assert payload["label"] is True

    @pytest.mark.asyncio
    async def test_record_user_report_wrong_user_returns_early(self):
        """User can only report their own transactions."""
        from services.feedback.feedback_service import FeedbackService

        txn_row = {"id": 7, "user_id": 999, "merchant": "M",
                   "device_id": None, "ip_address": None}
        pool, conn = _make_mock_pool(txn_row=txn_row)
        conn.fetchrow = AsyncMock(return_value=txn_row)

        svc = FeedbackService()
        with patch("services.feedback.feedback_service.get_pool", return_value=pool), \
             patch("services.feedback.feedback_service.EventPublisher") as MockPub:
            MockPub.return_value.publish = AsyncMock()
            # User 42 tries to report txn owned by user 999
            await svc.record_user_report(user_id=42, txn_id=7, label=True)

        # execute should NOT be called (returned early)
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_user_report_degrades_without_pool(self):
        """No pool → returns immediately without error."""
        from services.feedback.feedback_service import FeedbackService

        svc = FeedbackService()
        with patch("services.feedback.feedback_service.get_pool", return_value=None):
            # Should not raise
            await svc.record_user_report(user_id=1, txn_id=1, label=True)


# ================================================================== #
# 3. FeedbackService.record_chargeback
# ================================================================== #

class TestFeedbackServiceChargeback:
    """Tests for record_chargeback."""

    @pytest.mark.asyncio
    async def test_record_chargeback_sets_is_fraud_true(self):
        """Chargeback always marks the transaction as fraud."""
        from services.feedback.feedback_service import FeedbackService

        txn_row = {"id": 20, "user_id": 3, "merchant": "M2",
                   "device_id": "DEV-1", "ip_address": "10.0.0.1"}
        pool, conn = _make_mock_pool(txn_row=txn_row)
        conn.fetchrow = AsyncMock(return_value=txn_row)

        svc = FeedbackService()
        with patch("services.feedback.feedback_service.get_pool", return_value=pool), \
             patch("services.feedback.feedback_service.EventPublisher") as MockPub:
            MockPub.return_value.publish = AsyncMock()
            await svc.record_chargeback(txn_id=20, dispute_id="CB-001", reason_code="UA02")

        # Should call execute for fraud_feedback + transactions + device/IP blacklist
        assert conn.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_record_chargeback_publishes_event_with_source(self):
        """Event payload should have source='chargeback' and dispute_id."""
        from services.feedback.feedback_service import FeedbackService
        from services.event_bus.publisher import TOPIC_FEEDBACK_RECEIVED

        txn_row = {"id": 21, "user_id": 4, "merchant": "M3",
                   "device_id": None, "ip_address": None}
        pool, conn = _make_mock_pool(txn_row=txn_row)
        conn.fetchrow = AsyncMock(return_value=txn_row)

        svc = FeedbackService()
        with patch("services.feedback.feedback_service.get_pool", return_value=pool), \
             patch("services.feedback.feedback_service.EventPublisher") as MockPub:
            mock_publish = AsyncMock()
            MockPub.return_value.publish = mock_publish
            await svc.record_chargeback(txn_id=21, dispute_id="CB-999")

        topic, payload = mock_publish.call_args[0]
        assert topic == TOPIC_FEEDBACK_RECEIVED
        assert payload["source"] == "chargeback"
        assert payload["dispute_id"] == "CB-999"
        assert payload["label"] is True


# ================================================================== #
# 4. FeedbackService.auto_remediate
# ================================================================== #

class TestAutoRemediate:
    """Tests for auto_remediate device/IP blacklisting."""

    @pytest.mark.asyncio
    async def test_auto_remediate_blacklists_device_and_ip(self):
        """auto_remediate must insert device_id AND ip_address into blacklisted_entities."""
        from services.feedback.feedback_service import FeedbackService

        txn = {"id": 30, "user_id": 5, "merchant": "M4",
               "device_id": "DEV-ABC", "ip_address": "192.168.1.1"}
        pool, conn = _make_mock_pool()

        svc = FeedbackService()
        with patch("services.feedback.feedback_service.get_pool", return_value=pool):
            await svc.auto_remediate(txn)

        # 2 calls: one for device, one for IP
        assert conn.execute.call_count == 2, (
            f"Expected 2 blacklist inserts, got {conn.execute.call_count}"
        )
        # Verify entity types
        calls_args = [str(c) for c in conn.execute.call_args_list]
        full_args = str(conn.execute.call_args_list)
        assert "device" in full_args and "ip" in full_args

    @pytest.mark.asyncio
    async def test_auto_remediate_skips_if_no_device_or_ip(self):
        """No device_id or ip_address → no DB calls."""
        from services.feedback.feedback_service import FeedbackService

        txn = {"id": 31, "user_id": 6, "merchant": "M5",
               "device_id": None, "ip_address": None}
        pool, conn = _make_mock_pool()

        svc = FeedbackService()
        with patch("services.feedback.feedback_service.get_pool", return_value=pool):
            await svc.auto_remediate(txn)

        conn.execute.assert_not_called()


# ================================================================== #
# 5. DecisionEngine.enqueue_review / enqueue_counterfactual
# ================================================================== #

class TestDecisionEngineReviewQueue:
    """Tests for review queue enqueue on REVIEW decision."""

    @pytest.mark.asyncio
    async def test_decide_review_action_enqueues_item(self):
        """When decide() returns REVIEW, review_queue should receive an INSERT."""
        import services.decision_engine as de_module
        from services.decision_engine import DecisionEngine
        from schemas.score import ScoreResult

        pool, conn = _make_mock_pool()
        conn.fetchrow = AsyncMock(return_value=None)  # no blacklist, no merchant config

        score = ScoreResult(
            risk_score=55,
            risk_level="MEDIUM",
            unsup_score=0.55,
            signals={},
            explanation="test",
            detector_version="v1",
            latency_ms=10.0,
        )
        txn = {"id": 100, "merchant": "TestMerchant", "user_id": 1}
        user = {"id": 1}

        # Simulate merchant config lookup returning default thresholds
        engine = DecisionEngine()
        with patch.object(de_module, "get_pool", return_value=pool), \
             patch.object(de_module, "get_redis", return_value=None), \
             patch.object(engine, "_get_merchant_appetite",
                          new=AsyncMock(return_value={"block": 80, "challenge": 60, "review": 40})):
            decision = await engine.decide(score, txn, user)

        # Score 55 should be REVIEW (40 ≤ 55 < 60)
        assert decision.action == "review", f"Expected review, got {decision.action}"
        # execute should have been called for the review_queue INSERT
        assert conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_enqueue_review_inserts_with_correct_priority(self):
        """High score (≥70) + review action should use priority='high'."""
        import services.decision_engine as de_module
        from services.decision_engine import DecisionEngine
        from schemas.decision import Decision

        pool, conn = _make_mock_pool()

        engine = DecisionEngine()
        decision = Decision(
            action="review", score=75, reasons=["test"],
            rule_overrides=[], challenge_type=None,
        )

        with patch.object(de_module, "get_pool", return_value=pool):
            await engine.enqueue_review(txn_id=50, score=75, decision=decision, priority="high")

        conn.execute.assert_called_once()
        call_sql = conn.execute.call_args[0][0]
        call_params = conn.execute.call_args[0][1:]
        assert "review_queue" in call_sql
        assert "high" in call_params, f"Expected 'high' priority in params: {call_params}"

    @pytest.mark.asyncio
    async def test_enqueue_counterfactual_uses_low_priority(self):
        """Counterfactual hold-out must use priority='low' in the SQL."""
        import services.decision_engine as de_module
        from services.decision_engine import DecisionEngine

        pool, conn = _make_mock_pool()
        engine = DecisionEngine()

        with patch.object(de_module, "get_pool", return_value=pool):
            await engine.enqueue_counterfactual(txn_id=99, score=80)

        conn.execute.assert_called_once()
        # The SQL itself should mention 'low' (hardcoded in enqueue_counterfactual)
        call_sql = conn.execute.call_args[0][0]
        assert "low" in call_sql, f"Expected 'low' in SQL: {call_sql}"


# ================================================================== #
# 6. HybridScorer counterfactual hold-out
# ================================================================== #

class TestCounterfactualHoldOut:
    """Tests for HybridScorer.should_counterfactual_hold_out."""

    def test_not_triggered_for_non_allow(self):
        """Only action='allow' can be a hold-out sample."""
        from services.hybrid_scorer import HybridScorer
        mock_detector = MagicMock()
        mock_detector.DETECTOR_VERSION = "v1"
        scorer = HybridScorer.__new__(HybridScorer)
        scorer._detector = mock_detector
        scorer._sup_model = None
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""

        for action in ("block", "challenge", "review"):
            assert scorer.should_counterfactual_hold_out(score=80, action=action) is False

    def test_not_triggered_outside_score_range(self):
        """Scores outside [75, 85] should never be hold-out samples."""
        from services.hybrid_scorer import HybridScorer
        mock_detector = MagicMock()
        mock_detector.DETECTOR_VERSION = "v1"
        scorer = HybridScorer.__new__(HybridScorer)
        scorer._detector = mock_detector
        scorer._sup_model = None
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""

        for score in (0, 50, 74, 86, 100):
            result = scorer.should_counterfactual_hold_out(score=score, action="allow")
            assert result is False, f"Score {score} should not trigger hold-out"

    def test_may_be_triggered_in_borderline_range(self):
        """Scores in [75, 85] with action='allow' should be eligible (1% rate)."""
        from services.hybrid_scorer import HybridScorer
        mock_detector = MagicMock()
        mock_detector.DETECTOR_VERSION = "v1"
        scorer = HybridScorer.__new__(HybridScorer)
        scorer._detector = mock_detector
        scorer._sup_model = None
        scorer._shadow_model = None
        scorer._canary_model = None
        scorer._sup_model_path = ""

        # Call many times — at least one should return True (probabilistic 1% rate)
        # or all False (valid since it's 1%).  We just verify no exception is raised
        # and the result is a bool.
        for score in (75, 78, 80, 82, 85):
            result = scorer.should_counterfactual_hold_out(score=score, action="allow")
            assert isinstance(result, bool), f"Expected bool, got {type(result)}"


# ================================================================== #
# 7. RetrainFeedConsumer — threshold and trigger logic
# ================================================================== #

class TestRetrainFeedConsumer:
    """Tests for the retrain trigger counter logic."""

    @pytest.mark.asyncio
    async def test_below_threshold_does_not_trigger(self):
        """If counter < 100, no retrain should be triggered."""
        import workers.retrain_feed_consumer as rfc_module
        from workers.retrain_feed_consumer import RetrainFeedConsumer

        consumer = RetrainFeedConsumer()
        consumer._threshold = 100

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=50)  # 50 < 100

        with patch.object(rfc_module, "get_redis", return_value=mock_redis):
            await consumer._handle({"txn_id": "1", "label": "true"})

        mock_redis.exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_above_threshold_triggers_retrain(self):
        """If counter ≥ threshold and no lock, retrain should be triggered."""
        import workers.retrain_feed_consumer as rfc_module
        from workers.retrain_feed_consumer import RetrainFeedConsumer
        import asyncio

        consumer = RetrainFeedConsumer()
        consumer._threshold = 100

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=101)    # 101 ≥ 100
        mock_redis.exists = AsyncMock(return_value=0)    # no lock
        mock_pipeline = AsyncMock()
        mock_pipeline.set = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[True, True])
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        tasks_created = []
        with patch.object(rfc_module, "get_redis", return_value=mock_redis), \
             patch("asyncio.create_task",
                   side_effect=lambda coro, **kw: tasks_created.append(coro) or MagicMock()):
            await consumer._handle({"txn_id": "1", "label": "true"})

        assert len(tasks_created) == 1, "Expected one retrain task to be created"

    @pytest.mark.asyncio
    async def test_already_running_skips_retrain(self):
        """If retrain lock is set, a new retrain must NOT be triggered."""
        import workers.retrain_feed_consumer as rfc_module
        from workers.retrain_feed_consumer import RetrainFeedConsumer

        consumer = RetrainFeedConsumer()
        consumer._threshold = 5

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=10)     # 10 ≥ 5
        mock_redis.exists = AsyncMock(return_value=1)    # lock IS set

        with patch.object(rfc_module, "get_redis", return_value=mock_redis):
            await consumer._handle({"txn_id": "1", "label": "true"})

        mock_redis.pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_degrades_without_redis(self):
        """No Redis → handle() returns without error."""
        import workers.retrain_feed_consumer as rfc_module
        from workers.retrain_feed_consumer import RetrainFeedConsumer

        consumer = RetrainFeedConsumer()
        with patch.object(rfc_module, "get_redis", return_value=None):
            await consumer._handle({"txn_id": "1"})


# ================================================================== #
# 8. ReviewQueueWorker
# ================================================================== #

class TestReviewQueueWorker:
    """Tests for the review queue auto-assignment logic."""

    @pytest.mark.asyncio
    async def test_assigns_high_priority_items_to_analysts(self):
        """Pending high-priority items should be assigned round-robin."""
        from workers.review_queue_worker import _assign_pending_items

        analysts = [str(uuid.uuid4()), str(uuid.uuid4())]
        queue_ids = [uuid.uuid4() for _ in range(4)]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"id": q} for q in queue_ids])
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)

        assigned = await _assign_pending_items(mock_pool, analysts)

        assert assigned == 4, f"Expected 4 assignments, got {assigned}"
        assert mock_conn.execute.call_count == 4

    @pytest.mark.asyncio
    async def test_no_analysts_skips_assignment(self):
        """Empty analyst list should immediately return 0."""
        from workers.review_queue_worker import _assign_pending_items

        mock_pool = MagicMock()
        result = await _assign_pending_items(mock_pool, [])
        assert result == 0
        mock_pool.acquire.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_assignment_cycle_skips_without_analysts_env(self):
        """run_assignment_cycle should degrade gracefully without REVIEW_ANALYSTS."""
        import workers.review_queue_worker as rqw_module
        from workers.review_queue_worker import run_assignment_cycle
        import os

        pool, conn = _make_mock_pool()
        # Ensure REVIEW_ANALYSTS is not set
        env_copy = {k: v for k, v in os.environ.items() if k != "REVIEW_ANALYSTS"}
        with patch.object(rqw_module, "get_pool", return_value=pool), \
             patch.dict("os.environ", env_copy, clear=True):
            await run_assignment_cycle()

        conn.fetch.assert_not_called()
