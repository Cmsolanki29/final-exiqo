"""ReviewQueueWorker — auto-assignment of pending high-priority review items.

Phase 8: Feedback Flywheel.
Dependencies: asyncpg pool (Phase 1), APScheduler (Phase 2), core/config.py.
Performance budget: assignment loop < 500ms for up to 100 pending items.

Why auto-assignment?
  Without auto-assignment, analysts only pick up items they notice on a dashboard.
  Round-robin assignment ensures equitable load distribution and reduces the
  mean time-to-review for high-priority fraud cases.

Assignment policy:
  - Only 'pending' + 'high' priority items are auto-assigned (low/normal items
    wait for analysts to pick up via the dashboard or next 5-minute cycle).
  - Analysts are listed in REVIEW_ANALYSTS env var as a comma-separated list
    of UUIDs.  If the env var is not set, auto-assignment is skipped.
  - Round-robin by item creation order to give each analyst a fair share.
  - Items already assigned (assigned_to IS NOT NULL) are skipped.

Schedule: runs every 5 minutes via APScheduler.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from core.db import get_pool  # module-level so tests can patch

logger = logging.getLogger(__name__)


def _get_analyst_pool() -> list[str]:
    """Load analyst UUIDs from environment variable.

    Format: REVIEW_ANALYSTS="uuid1,uuid2,uuid3"
    Returns empty list if not configured (auto-assignment disabled).
    """
    raw = os.getenv("REVIEW_ANALYSTS", "")
    return [a.strip() for a in raw.split(",") if a.strip()]


async def _assign_pending_items(pool, analysts: list[str]) -> int:
    """Assign unassigned high-priority review items in round-robin order.

    Args:
        pool:     asyncpg connection pool.
        analysts: List of analyst UUID strings.

    Returns:
        Number of items assigned this cycle.
    """
    if not analysts:
        return 0

    from datetime import datetime, timezone

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id
            FROM   review_queue
            WHERE  status      = 'pending'
              AND  priority    = 'high'
              AND  assigned_to IS NULL
            ORDER  BY created_at ASC
            LIMIT  100
            """
        )

        assigned = 0
        now = datetime.now(timezone.utc)
        for i, row in enumerate(rows):
            analyst = analysts[i % len(analysts)]
            await conn.execute(
                """
                UPDATE review_queue
                SET    assigned_to  = $1::uuid,
                       assigned_at  = $2,
                       status       = 'in_review'
                WHERE  id = $3
                  AND  status = 'pending'
                """,
                analyst, now, row["id"],
            )
            assigned += 1

        return assigned


async def run_assignment_cycle() -> None:
    """Main entry point called by APScheduler every 5 minutes.

    Degrades gracefully: if the pool is unavailable or REVIEW_ANALYSTS
    is not configured, logs and returns without error.
    """
    pool = get_pool()
    if pool is None:
        logger.debug("review_queue_worker: pool unavailable — skipping cycle")
        return

    analysts = _get_analyst_pool()
    if not analysts:
        logger.debug(
            "review_queue_worker: REVIEW_ANALYSTS not configured — auto-assignment disabled"
        )
        return

    try:
        assigned = await _assign_pending_items(pool, analysts)
        if assigned > 0:
            logger.info(
                "review_queue_worker.assigned count=%d analysts=%d",
                assigned, len(analysts),
            )
    except Exception as exc:
        logger.warning("review_queue_worker.error: %s", exc)
