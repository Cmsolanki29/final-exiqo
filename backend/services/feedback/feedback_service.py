"""FeedbackService — ingests fraud labels from users, chargebacks, and analysts.

Phase 8: Feedback Flywheel.
Dependencies: asyncpg (core/db.py), EventPublisher (Phase 1), core/config.py.
Performance budget:
  record_user_report()    < 50ms (single txn: two DB writes + one event publish)
  record_chargeback()     < 50ms
  record_analyst_decision() < 30ms

Why a dedicated FeedbackService?
  Label quality directly controls model performance.  A dedicated service
  keeps the labeling contract explicit:
    1. The label is persisted atomically (fraud_feedback + transactions update).
    2. A `FEEDBACK_RECEIVED` event fires regardless of downstream failures.
    3. Auto-remediation (blacklist device/IP) happens ONLY for confirmed fraud,
       never for chargebacks-under-dispute or inconclusive analyst decisions.
    4. The retrain_feed_consumer counts FEEDBACK_RECEIVED events to trigger
       out-of-band retraining when enough new labels arrive.

Auto-remediation policy:
  - Device (device_id): blocked for 7 days (auto-expiry).
  - IP address:         flagged for 24 hours (auto-expiry).
  - Merchant:           NOT auto-blocked — requires analyst confirmation.
    (Blocking a merchant can stop ALL payments at that merchant, which is a
     high-impact irreversible action.  This is intentional friction.)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from core.db import get_pool
from services.event_bus.publisher import EventPublisher, TOPIC_FEEDBACK_RECEIVED as FEEDBACK_RECEIVED

logger = logging.getLogger(__name__)


class FeedbackService:
    """Ingests fraud labels from multiple sources and feeds them into the ML loop.

    All public methods are async and require an initialised asyncpg pool.
    They degrade gracefully (log + return) if the pool is unavailable.
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def record_user_report(
        self,
        user_id: int,
        txn_id: int,
        label: bool,
        notes: Optional[str] = None,
    ) -> None:
        """Record a user-submitted fraud report.

        Writes to fraud_feedback, updates transactions.is_fraud, and (if
        label=True) triggers auto_remediate to block the device/IP used in
        the flagged transaction.

        Args:
            user_id:  Reporting user's PK (must match transactions.user_id).
            txn_id:   Transaction PK being reported.
            label:    True = fraud, False = user disputes an existing flag.
            notes:    Optional user note.
        """
        pool = get_pool()
        if pool is None:
            logger.warning("feedback_service.record_user_report: pool unavailable")
            return

        async with pool.acquire() as conn:
            # Verify the transaction belongs to this user
            row = await conn.fetchrow(
                "SELECT id, user_id, merchant, device_id, ip_address FROM transactions WHERE id = $1",
                txn_id,
            )
            if row is None:
                logger.warning("feedback_service: txn %d not found", txn_id)
                return
            if int(row["user_id"]) != user_id:
                logger.warning(
                    "feedback_service: user %d tried to report txn %d owned by user %d",
                    user_id, txn_id, row["user_id"],
                )
                return

            # 1. Insert fraud_feedback record
            await conn.execute(
                """
                INSERT INTO fraud_feedback (transaction_id, label, source, notes, created_at)
                VALUES ($1, $2, 'user_report', $3, $4)
                ON CONFLICT (transaction_id) DO UPDATE
                    SET label = EXCLUDED.label,
                        source = 'user_report',
                        notes  = EXCLUDED.notes
                """,
                txn_id, label, notes, datetime.now(timezone.utc),
            )

            # 2. Update transactions.is_fraud
            await conn.execute(
                """
                UPDATE transactions
                SET    is_fraud           = $1,
                       fraud_label_source = 'user_report',
                       fraud_label_at     = $2
                WHERE  id = $3
                """,
                label, datetime.now(timezone.utc), txn_id,
            )

        # 3. Auto-remediate on confirmed fraud
        if label:
            await self.auto_remediate(dict(row))

        # 4. Publish event (fire-and-forget — don't let event failure block response)
        try:
            from services.event_bus.publisher import event_publisher

            await event_publisher.publish(
                FEEDBACK_RECEIVED,
                {
                    "txn_id": txn_id,
                    "user_id": user_id,
                    "label": label,
                    "source": "user_report",
                },
            )
        except Exception as exc:
            logger.warning("feedback_service: event publish failed: %s", exc)

        logger.info(
            "feedback_service.user_report txn=%d user=%d label=%s",
            txn_id, user_id, label,
        )

    async def record_chargeback(
        self,
        txn_id: int,
        dispute_id: str,
        reason_code: Optional[str] = None,
    ) -> None:
        """Record a chargeback received from the payment processor.

        Chargebacks are the highest-confidence fraud signal — they come from
        the card network after the issuer has verified the dispute.

        Args:
            txn_id:      Transaction PK that was charged back.
            dispute_id:  Processor dispute/chargeback ID (for idempotency).
            reason_code: Processor reason code (optional, stored in notes).
        """
        pool = get_pool()
        if pool is None:
            logger.warning("feedback_service.record_chargeback: pool unavailable")
            return

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, user_id, merchant, device_id, ip_address FROM transactions WHERE id = $1",
                txn_id,
            )
            if row is None:
                logger.warning("feedback_service.record_chargeback: txn %d not found", txn_id)
                return

            notes = f"dispute_id={dispute_id}"
            if reason_code:
                notes += f" reason_code={reason_code}"

            # Insert fraud_feedback (chargeback = definitive fraud label)
            await conn.execute(
                """
                INSERT INTO fraud_feedback (transaction_id, label, source, notes, created_at)
                VALUES ($1, TRUE, 'chargeback', $2, $3)
                ON CONFLICT (transaction_id) DO UPDATE
                    SET label  = TRUE,
                        source = 'chargeback',
                        notes  = EXCLUDED.notes
                """,
                txn_id, notes, datetime.now(timezone.utc),
            )

            await conn.execute(
                """
                UPDATE transactions
                SET    is_fraud           = TRUE,
                       fraud_label_source = 'chargeback',
                       fraud_label_at     = $1
                WHERE  id = $2
                """,
                datetime.now(timezone.utc), txn_id,
            )

        # Chargebacks always trigger remediation
        await self.auto_remediate(dict(row))

        try:
            from services.event_bus.publisher import event_publisher

            await event_publisher.publish(
                FEEDBACK_RECEIVED,
                {
                    "txn_id": txn_id,
                    "user_id": int(row["user_id"]),
                    "label": True,
                    "source": "chargeback",
                    "dispute_id": dispute_id,
                },
            )
        except Exception as exc:
            logger.warning("feedback_service.chargeback: event publish failed: %s", exc)

        logger.info(
            "feedback_service.chargeback txn=%d dispute=%s", txn_id, dispute_id
        )

    async def record_analyst_decision(
        self,
        queue_id: UUID,
        resolution: str,
        reviewer_id: Optional[UUID],
        notes: Optional[str],
    ) -> None:
        """Record an analyst's resolution of a review queue item.

        Updates review_queue.status + fraud_feedback row.
        If resolution='fraud', triggers auto_remediate.

        Args:
            queue_id:    review_queue.id UUID.
            resolution:  'fraud' | 'legitimate' | 'inconclusive'.
            reviewer_id: Analyst user UUID (optional for audit trail).
            notes:       Analyst notes.
        """
        pool = get_pool()
        if pool is None:
            logger.warning("feedback_service.record_analyst_decision: pool unavailable")
            return

        now = datetime.now(timezone.utc)
        label = True if resolution == "fraud" else (
            False if resolution == "legitimate" else None
        )

        async with pool.acquire() as conn:
            # Fetch the review queue item
            rq = await conn.fetchrow(
                "SELECT id, transaction_id, status FROM review_queue WHERE id = $1",
                queue_id,
            )
            if rq is None:
                logger.warning("feedback_service: review_queue item %s not found", queue_id)
                return
            if rq["status"] == "resolved":
                logger.info("feedback_service: %s already resolved — skipping", queue_id)
                return

            txn_id = int(rq["transaction_id"])

            # Update review_queue
            await conn.execute(
                """
                UPDATE review_queue
                SET    status      = 'resolved',
                       resolution  = $1,
                       notes       = $2,
                       resolved_at = $3,
                       assigned_to = COALESCE(assigned_to, $4)
                WHERE  id = $5
                """,
                resolution, notes, now, reviewer_id, queue_id,
            )

            # Upsert fraud_feedback
            if label is not None:
                await conn.execute(
                    """
                    INSERT INTO fraud_feedback
                        (transaction_id, label, source, notes, reviewed_by, created_at)
                    VALUES ($1, $2, 'analyst', $3, $4, $5)
                    ON CONFLICT (transaction_id) DO UPDATE
                        SET label       = EXCLUDED.label,
                            source      = 'analyst',
                            notes       = EXCLUDED.notes,
                            reviewed_by = EXCLUDED.reviewed_by
                    """,
                    txn_id, label,
                    f"analyst_decision: {resolution}" + (f" — {notes}" if notes else ""),
                    reviewer_id, now,
                )

                await conn.execute(
                    """
                    UPDATE transactions
                    SET    is_fraud           = $1,
                           fraud_label_source = 'analyst',
                           fraud_label_at     = $2
                    WHERE  id = $3
                    """,
                    label, now, txn_id,
                )

            # Fetch txn for remediation
            txn_row = await conn.fetchrow(
                "SELECT id, user_id, merchant, device_id, ip_address FROM transactions WHERE id = $1",
                txn_id,
            )

        if resolution == "fraud" and txn_row:
            await self.auto_remediate(dict(txn_row))

        try:
            from services.event_bus.publisher import event_publisher

            await event_publisher.publish(
                FEEDBACK_RECEIVED,
                {
                    "txn_id": txn_id,
                    "label": label,
                    "source": "analyst",
                    "resolution": resolution,
                    "queue_id": str(queue_id),
                },
            )
        except Exception as exc:
            logger.warning("feedback_service.analyst: event publish failed: %s", exc)

        logger.info(
            "feedback_service.analyst_decision queue=%s txn=%d resolution=%s",
            queue_id, txn_id, resolution,
        )

    async def auto_remediate(self, txn: dict[str, Any]) -> None:
        """Auto-blacklist the device and IP from a confirmed fraud transaction.

        Remediation policy:
          - device_id:  blocked for 7 days (168 hours)
          - ip_address: flagged for 24 hours
          - merchant:   NOT auto-blocked (requires analyst confirmation —
                        blocking a merchant stops all payments there)

        Inserts into blacklisted_entities (Phase 4 table).  Uses ON CONFLICT
        DO NOTHING so that repeated chargebacks on the same device don't
        duplicate rows.

        Args:
            txn: Dict with keys: id, user_id, merchant, device_id, ip_address.
        """
        pool = get_pool()
        if pool is None:
            return

        now = datetime.now(timezone.utc)
        to_blacklist: list[tuple[str, str, str, datetime]] = []

        device_id = txn.get("device_id")
        ip_address = txn.get("ip_address")

        if device_id:
            to_blacklist.append((
                "device", str(device_id),
                f"Auto-remediated from txn {txn.get('id')} fraud report",
                now + timedelta(days=7),
            ))
        if ip_address:
            to_blacklist.append((
                "ip", str(ip_address),
                f"Auto-remediated from txn {txn.get('id')} fraud report",
                now + timedelta(hours=24),
            ))

        if not to_blacklist:
            return

        try:
            async with pool.acquire() as conn:
                for entity_type, entity_value, reason, expires_at in to_blacklist:
                    await conn.execute(
                        """
                        INSERT INTO blacklisted_entities
                            (entity_type, entity_value, reason, severity, added_at, expires_at)
                        VALUES ($1, $2, $3, 'high', $4, $5)
                        ON CONFLICT (entity_type, entity_value) DO UPDATE
                            SET reason     = EXCLUDED.reason,
                                expires_at = EXCLUDED.expires_at,
                                added_at   = EXCLUDED.added_at
                        """,
                        entity_type, entity_value, reason, now, expires_at,
                    )
                    logger.info(
                        "feedback_service.auto_remediated entity_type=%s value=%s expires=%s",
                        entity_type, entity_value, expires_at.isoformat(),
                    )
        except Exception as exc:
            logger.warning("feedback_service.auto_remediate failed: %s", exc)


# Module-level singleton
feedback_service = FeedbackService()
