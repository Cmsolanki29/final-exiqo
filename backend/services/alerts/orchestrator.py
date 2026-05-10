"""Alert orchestrator — persists to DB and fans out to delivery channels.

Phase 1: Real-time event-driven scoring.
Dependencies: asyncpg, structlog.
Performance budget: dispatch() should complete in <20ms (one DB INSERT + fan-out stubs).

Severity → channel mapping:
  CRITICAL → websocket + push + email + sms (all 4)
  HIGH     → websocket + push + email
  MEDIUM   → websocket + push
  LOW      → websocket only

Channel implementations are stubs in Phase 1; real connectors arrive in later phases.
The fan-out is always fire-and-forget via asyncio.gather() so dispatch() never blocks
on a slow notification provider.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Channel tier mappings — add keys as channels are implemented.
_SEVERITY_CHANNELS: dict[str, list[str]] = {
    "CRITICAL": ["websocket", "push", "email", "sms"],
    "HIGH": ["websocket", "push", "email"],
    "MEDIUM": ["websocket", "push"],
    "LOW": ["websocket"],
}


class AlertOrchestrator:
    """Writes alert rows and fans out to delivery channels.

    Designed to be used both directly (from alert_consumer.py) and in future
    from a webhook ingestion path.  Pool is injected after creation so the
    singleton can be imported at module import time.
    """

    def __init__(self, db_pool=None) -> None:
        self._pool = db_pool

    def set_pool(self, pool) -> None:
        """Inject asyncpg pool (called during lifespan init)."""
        self._pool = pool

    async def dispatch(self, event: dict[str, Any]) -> None:
        """Persist alert and fan out to channels based on severity.

        Args:
            event: The decoded TRANSACTIONS_SCORED payload containing at minimum:
                   txn_id, user_id, risk_score, risk_level, reason, action.
        """
        user_id = event.get("user_id")
        txn_id = event.get("txn_id")
        risk_score = event.get("risk_score", 0)
        risk_level = event.get("risk_level", "LOW")
        reason = event.get("reason", "Anomaly detected")
        action = event.get("action", "accepted")

        # Persist to alerts table (same table used by existing /alerts endpoints)
        alert_id = await self._persist_alert(
            user_id=user_id,
            txn_id=txn_id,
            risk_score=risk_score,
            risk_level=risk_level,
            reason=reason,
        )

        # Fan out to delivery channels (fire-and-forget)
        channels = _SEVERITY_CHANNELS.get(risk_level, ["websocket"])
        await asyncio.gather(
            *[self._dispatch_channel(ch, user_id, txn_id, risk_level, reason) for ch in channels],
            return_exceptions=True,  # never let a failed channel crash dispatch
        )

        logger.info(
            "alert_dispatched alert_id=%s user_id=%s txn_id=%s risk_level=%s channels=%s",
            alert_id,
            user_id,
            txn_id,
            risk_level,
            channels,
        )

    async def _persist_alert(
        self,
        user_id: int,
        txn_id: int | None,
        risk_score: int,
        risk_level: str,
        reason: str,
    ) -> int | None:
        """Insert a row into the alerts table.  Returns new alert id or None on failure."""
        if self._pool is None:
            logger.debug("alert_persist_skipped no_pool")
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO alerts (
                        user_id, transaction_id, alert_type, severity,
                        message, is_read, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, FALSE, $6)
                    RETURNING id
                    """,
                    user_id,
                    txn_id,
                    "RISK_SCORE",
                    risk_level,
                    f"[{risk_level}] Risk score {risk_score}/100 — {reason}",
                    datetime.now(timezone.utc),
                )
                return row["id"] if row else None
        except Exception as exc:
            logger.error(
                "alert_persist_failed user_id=%s txn_id=%s error=%s",
                user_id,
                txn_id,
                exc,
            )
            return None

    async def _dispatch_channel(
        self,
        channel: str,
        user_id: int | None,
        txn_id: int | None,
        risk_level: str,
        reason: str,
    ) -> None:
        """Route to the appropriate channel handler.

        Stub in Phase 1; real implementations in later phases:
          websocket — Phase 1+: can integrate with FastAPI WebSocket routes
          push      — Phase 2+: FCM / APNs via external service
          email     — Phase 3+: SendGrid / SES
          sms       — Phase 4+: Twilio / AWS SNS
        """
        try:
            if channel == "websocket":
                await self._send_websocket(user_id, txn_id, risk_level, reason)
            elif channel == "push":
                await self._send_push(user_id, risk_level, reason)
            elif channel == "email":
                await self._send_email(user_id, risk_level, reason)
            elif channel == "sms":
                await self._send_sms(user_id, risk_level, reason)
        except Exception as exc:
            logger.warning(
                "channel_dispatch_failed channel=%s user_id=%s error=%s",
                channel,
                user_id,
                exc,
            )

    async def _send_websocket(
        self, user_id: int | None, txn_id: int | None, risk_level: str, reason: str
    ) -> None:
        """Stub: broadcast via WebSocket room for user.

        Phase 1 logs; Phase 2 connects to an in-process connection manager.
        """
        logger.debug(
            "ws_alert_stub user_id=%s txn_id=%s risk_level=%s", user_id, txn_id, risk_level
        )

    async def _send_push(
        self, user_id: int | None, risk_level: str, reason: str
    ) -> None:
        """Stub: send mobile push notification."""
        logger.debug("push_alert_stub user_id=%s risk_level=%s", user_id, risk_level)

    async def _send_email(
        self, user_id: int | None, risk_level: str, reason: str
    ) -> None:
        """Stub: send transactional email."""
        logger.debug("email_alert_stub user_id=%s risk_level=%s", user_id, risk_level)

    async def _send_sms(
        self, user_id: int | None, risk_level: str, reason: str
    ) -> None:
        """Stub: send SMS."""
        logger.debug("sms_alert_stub user_id=%s risk_level=%s", user_id, risk_level)


# Module-level singleton
alert_orchestrator = AlertOrchestrator()
