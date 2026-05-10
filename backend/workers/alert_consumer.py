"""Alert consumer — listens on TRANSACTIONS_SCORED stream, fires alerts.

Phase 1: Real-time event-driven scoring.
Dependencies: redis[hiredis], asyncpg.

Flow:
  1. Receive TRANSACTIONS_SCORED event.
  2. If risk_level in (HIGH, CRITICAL): check cooldown.
  3. If cooldown allows: call AlertOrchestrator.dispatch.
  4. Record cooldown so duplicate alerts are suppressed for ALERT_COOLDOWN_SEC.

Performance budget: handle() < 30ms (Redis cooldown check + DB insert).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.config import get_settings
from services.alerts.cooldown import cooldown_manager
from services.alerts.orchestrator import alert_orchestrator
from services.event_bus.consumer_base import BaseConsumer
from services.event_bus.publisher import TOPIC_TRANSACTIONS_SCORED

logger = logging.getLogger(__name__)

# Risk levels that trigger alert dispatch
ALERT_RISK_LEVELS = {"HIGH", "CRITICAL"}


class AlertConsumer(BaseConsumer):
    """Consumes TRANSACTIONS_SCORED events and dispatches alerts.

    Consumer group 'alert_workers' allows horizontal scaling: deploy multiple
    instances and each message is processed by exactly one instance.
    """

    topic = TOPIC_TRANSACTIONS_SCORED
    group_name = "alert_workers"
    consumer_name = "alert_worker_0"

    async def handle(self, payload: dict[str, Any]) -> None:
        """Process a scored transaction event and conditionally fire an alert.

        Args:
            payload: Dict with keys: txn_id, user_id, risk_score, risk_level,
                     reason, action, detector_version, latency_ms.
        """
        risk_level = payload.get("risk_level", "LOW")

        if risk_level not in ALERT_RISK_LEVELS:
            # LOW and MEDIUM do not need immediate alerts
            return

        user_id = payload.get("user_id")
        txn_id = payload.get("txn_id")
        risk_score = payload.get("risk_score", 0)

        if user_id is None:
            logger.warning("alert_consumer_missing_user_id payload=%s", payload)
            return

        # Rule name encodes risk_level so different levels have separate cooldowns.
        rule_name = f"txn_risk_{risk_level.lower()}"

        if not await cooldown_manager.should_send_alert(user_id, rule_name):
            logger.debug(
                "alert_consumer_suppressed user_id=%s txn_id=%s rule=%s",
                user_id,
                txn_id,
                rule_name,
            )
            return

        await alert_orchestrator.dispatch(payload)
        await cooldown_manager.record_alert(user_id, rule_name)

        logger.info(
            "alert_consumer_dispatched user_id=%s txn_id=%s risk_level=%s score=%d",
            user_id,
            txn_id,
            risk_level,
            risk_score,
        )

        # ── Phase 9: auto-trigger LLM investigation on high-risk score ──
        # Fire-and-forget so the alert path stays under its latency budget.
        settings = get_settings()
        if (
            settings.PHASE_9_AGENT_ENABLED
            and isinstance(risk_score, (int, float))
            and risk_score >= settings.PHASE_9_AUTO_TRIGGER_SCORE
            and txn_id is not None
        ):
            try:
                from services.phase_9_agent.investigation_service import (
                    investigate_transaction,
                )
                asyncio.create_task(
                    investigate_transaction(
                        transaction_id=int(txn_id),
                        user_id=int(user_id),
                        triggered_by="auto_high_risk",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("phase_9 auto-trigger skipped: %s", exc)


# Module-level singleton (started in main.py lifespan)
alert_consumer = AlertConsumer()
