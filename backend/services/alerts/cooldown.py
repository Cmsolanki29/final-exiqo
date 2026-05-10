"""Redis-backed alert cooldown manager.

Phase 1: Real-time event-driven scoring.
Dependencies: redis[hiredis].
Performance budget: should_send_alert() must complete in <5ms (two Redis GETs).

Why cooldowns?
  Without them a single transaction can trigger an alert storm: the consumer
  fires, writes to alerts, re-publishes, consumer fires again, etc.
  Cooldowns also respect user attention — more than 5 alerts/hour in digest
  mode prevents notification fatigue.

Graceful degradation:
  If Redis is unavailable, should_send_alert() returns True (allow all alerts)
  and record_alert() is a no-op.  This is the safe side — we'd rather over-alert
  than silently suppress alerts when the cooldown store is down.
"""

from __future__ import annotations

import logging

from core.config import get_settings
from core.redis import get_redis

logger = logging.getLogger(__name__)


class CooldownManager:
    """Redis-backed per-user, per-rule alert rate limiter.

    Keys used:
      cooldown:{user_id}:{rule_name}  — exists while cooldown is active (TTL = cooldown_sec)
      alert_count:{user_id}:1h        — sliding 1-hour counter (INCR + EXPIRE)
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def _cooldown_key(self, user_id: int, rule_name: str) -> str:
        return f"cooldown:{user_id}:{rule_name}"

    def _count_key(self, user_id: int) -> str:
        return f"alert_count:{user_id}:1h"

    async def should_send_alert(self, user_id: int, rule_name: str) -> bool:
        """Return True if an alert should be sent.

        Returns False (suppress) when:
          1. A cooldown key exists for this user+rule (same alert too soon).
          2. The user has received >= ALERT_HOURLY_CAP alerts in the last hour
             (digest mode — frontend should batch them).

        Args:
            user_id:   Integer user primary key.
            rule_name: Stable identifier for the alert rule (e.g. 'high_risk_txn').
        """
        redis = get_redis()
        if redis is None:
            return True  # degraded: allow all alerts

        try:
            # Check per-rule cooldown
            cooldown_key = self._cooldown_key(user_id, rule_name)
            if await redis.exists(cooldown_key):
                logger.debug(
                    "alert_suppressed_cooldown user_id=%d rule=%s", user_id, rule_name
                )
                return False

            # Check hourly cap
            count_key = self._count_key(user_id)
            count_raw = await redis.get(count_key)
            count = int(count_raw) if count_raw else 0
            if count >= self._settings.ALERT_HOURLY_CAP:
                logger.debug(
                    "alert_suppressed_hourly_cap user_id=%d count=%d", user_id, count
                )
                return False

            return True

        except Exception as exc:
            logger.warning("cooldown_check_failed user_id=%d error=%s", user_id, exc)
            return True  # degrade safely

    async def record_alert(
        self, user_id: int, rule_name: str, ttl_sec: int | None = None
    ) -> None:
        """Record that an alert was sent — sets cooldown key and increments hourly counter.

        Args:
            user_id:   Integer user primary key.
            rule_name: Stable rule identifier matching should_send_alert().
            ttl_sec:   Cooldown window in seconds.  Defaults to ALERT_COOLDOWN_SEC.
        """
        redis = get_redis()
        if redis is None:
            return

        ttl = ttl_sec if ttl_sec is not None else self._settings.ALERT_COOLDOWN_SEC

        try:
            pipe = redis.pipeline(transaction=False)
            # Set per-rule cooldown
            pipe.set(self._cooldown_key(user_id, rule_name), "1", ex=ttl)
            # Increment hourly counter
            count_key = self._count_key(user_id)
            pipe.incr(count_key)
            pipe.expire(count_key, 3600)  # sliding 1-hour window
            await pipe.execute()
        except Exception as exc:
            logger.warning("cooldown_record_failed user_id=%d error=%s", user_id, exc)


# Module-level singleton
cooldown_manager = CooldownManager()
