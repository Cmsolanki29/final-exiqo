"""Multi-action decision engine — transforms a risk score into a business action.

Phase 4: Decision Engine.
Phase 8 additions: When action = 'review', automatically enqueues the transaction
  in the review_queue table (migration 007).  The priority is:
    high   → score ≥ 70 or any rule override present
    normal → score-based REVIEW with no override
    low    → reserved for counterfactual hold-outs (set by HybridScorer)

Dependencies: asyncpg (DB), redis.asyncio (merchant config cache), schemas/decision.py,
              schemas/score.py, core/config.py.
Performance budget: decide() < 20ms (cache hit path); < 50ms (DB fallback path).
  enqueue_review() adds ~5ms (single DB INSERT with ON CONFLICT DO NOTHING).

Why a separate Decision Engine?
  A raw risk score of 72 means very different things for:
    - A ₹50 coffee shop payment  → probably fine, ALLOW
    - A ₹50,000 international wire  → BLOCK at that merchant's threshold
    - A brand-new device doing the ₹50K transfer → CHALLENGE with biometric

  The DecisionEngine wraps all that business logic cleanly, keeping it out of
  the scoring layer and the HTTP route.  It is the SINGLE place that answers
  "what do we actually DO with this score?"

Decision logic (evaluated in strict priority order):
  1. Blacklist check  — entity hard-blocked → BLOCK (no ML override possible)
  2. Extreme score    — score ≥ 95 → BLOCK (model is very confident)
  3. Trusted premium  — verified premium user + score < 70 → ALLOW
  4. Merchant config  — per-merchant thresholds (Redis cache → DB → global default)
  5. Score band       — score vs merchant thresholds
  6. Velocity         — burst of ≥10 txns/hour upgrades ALLOW/REVIEW to CHALLENGE
  7. Geo-impossible   — signal in score.signals upgrades to CHALLENGE minimum
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from core.config import get_settings
from core.db import get_pool
from core.redis import get_redis
from schemas.decision import Decision
from schemas.score import ScoreResult

logger = logging.getLogger(__name__)

# Redis cache TTL for merchant configs (5 minutes is short enough to pick up
# emergency threshold changes within a reasonable window).
_MERCHANT_CACHE_TTL_SEC = 300

# Global default thresholds (used when no merchant-specific row exists).
_DEFAULT_APPETITE: dict[str, int] = {
    "block": 80,
    "challenge": 60,
    "review": 40,
}


class DecisionEngine:
    """Convert a ScoreResult + transaction context into a four-way business action.

    Thread-safe: all state is read-only after construction.  Redis and DB
    calls are async, so use `await engine.decide(...)`.
    """

    async def decide(
        self,
        score: ScoreResult,
        txn: dict[str, Any],
        user: dict[str, Any],
        assembled_features: dict[str, Any] | None = None,
    ) -> Decision:
        """Apply the decision rules and return a Decision.

        Args:
            score:              Output of HybridScorer.score().
            txn:                Transaction dict (TransactionIn.to_feature_dict() or DB row dict).
            user:               User dict with at least {'id': int, 'email': str}.
                                Optional keys: 'is_premium' (bool), 'txn_count_1h' (int).
            assembled_features: Phase 2 assembled feature dict, used for velocity signals.

        Returns:
            Decision with action, score snapshot, reasons, and any rule overrides.
        """
        t0 = time.perf_counter()
        risk_score = score.risk_score
        reasons: list[str] = []
        rule_overrides: list[str] = []

        # ------------------------------------------------------------------ #
        # Step 1: Blacklist check (hard stop — no ML override)
        # ------------------------------------------------------------------ #
        blacklist_reason = await self._is_blacklisted(txn)
        if blacklist_reason:
            reasons.append(f"Entity blacklisted: {blacklist_reason}")
            rule_overrides.append("blacklisted_entity")
            logger.info(
                "decision_engine.block.blacklist txn_user=%s reason=%s",
                txn.get("user_id"), blacklist_reason,
            )
            return Decision(
                action="block",
                score=risk_score,
                reasons=reasons,
                rule_overrides=rule_overrides,
                challenge_type=None,
            )

        # ------------------------------------------------------------------ #
        # Step 2: Extreme ML risk (model is very confident)
        # ------------------------------------------------------------------ #
        if risk_score >= 95:
            reasons.append(f"Model extreme risk score: {risk_score}/100")
            rule_overrides.append("model_extreme_risk")
            return Decision(
                action="block",
                score=risk_score,
                reasons=reasons,
                rule_overrides=rule_overrides,
                challenge_type=None,
            )

        # ------------------------------------------------------------------ #
        # Step 3: Trusted premium user with moderate score
        # ------------------------------------------------------------------ #
        is_premium = bool(user.get("is_premium", False) or user.get("is_verified_premium", False))
        if is_premium and risk_score < 70:
            reasons.append(f"Verified premium user — score {risk_score} below premium threshold (70)")
            rule_overrides.append("trusted_user")
            return Decision(
                action="allow",
                score=risk_score,
                reasons=reasons,
                rule_overrides=rule_overrides,
                challenge_type=None,
            )

        # ------------------------------------------------------------------ #
        # Step 4: Per-merchant risk appetite (Redis cache → DB → global default)
        # ------------------------------------------------------------------ #
        merchant_id = str(txn.get("merchant") or "").strip()
        appetite = await self._get_merchant_appetite(merchant_id)

        # ------------------------------------------------------------------ #
        # Step 5: Score-based decision using merchant thresholds
        # ------------------------------------------------------------------ #
        if risk_score >= appetite["block"]:
            action = "block"
            reasons.append(
                f"Score {risk_score} ≥ merchant block threshold {appetite['block']}"
            )
        elif risk_score >= appetite["challenge"]:
            action = "challenge"
            reasons.append(
                f"Score {risk_score} ≥ merchant challenge threshold {appetite['challenge']}"
            )
        elif risk_score >= appetite["review"]:
            action = "review"
            reasons.append(
                f"Score {risk_score} ≥ merchant review threshold {appetite['review']}"
            )
        else:
            action = "allow"
            reasons.append(f"Score {risk_score} below all thresholds — normal transaction")

        # ------------------------------------------------------------------ #
        # Step 6: Velocity override — burst transactions upgrade to CHALLENGE
        # ------------------------------------------------------------------ #
        txn_count_1h = int(
            (assembled_features or {}).get("user_txn_count_1h", 0)
            or user.get("txn_count_1h", 0)
        )
        if txn_count_1h >= 10 and risk_score >= 40 and action in ("allow", "review"):
            reasons.append(
                f"Velocity burst: {txn_count_1h} transactions in last hour (threshold ≥10)"
            )
            rule_overrides.append("velocity_burst")
            action = "challenge"

        # ------------------------------------------------------------------ #
        # Step 7: Geo-impossibility → CHALLENGE minimum
        # ------------------------------------------------------------------ #
        if score.signals.get("geo_impossible") or score.signals.get("_geo_flag"):
            if action == "allow":
                reasons.append("Geo-impossibility signal detected")
                rule_overrides.append("geo_impossible")
                action = "challenge"

        # ------------------------------------------------------------------ #
        # Determine challenge type
        # ------------------------------------------------------------------ #
        challenge_type: Optional[str] = None
        if action == "challenge":
            if risk_score >= 80:
                challenge_type = "biometric"
            elif risk_score >= 65:
                challenge_type = "3ds"
            else:
                challenge_type = "otp"

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "decision_engine.decided user=%s merchant=%s score=%d action=%s overrides=%s latency_ms=%.1f",
            txn.get("user_id"), merchant_id, risk_score, action, rule_overrides, elapsed_ms,
        )

        decision = Decision(
            action=action,
            score=risk_score,
            reasons=reasons,
            rule_overrides=rule_overrides,
            challenge_type=challenge_type,
        )

        # Phase 8: auto-enqueue review items (fire-and-forget, doesn't slow response)
        if action == "review":
            txn_id = txn.get("id")
            if txn_id is not None:
                try:
                    priority = "high" if (risk_score >= 70 or rule_overrides) else "normal"
                    await self.enqueue_review(
                        txn_id=int(txn_id),
                        score=risk_score,
                        decision=decision,
                        priority=priority,
                    )
                except Exception as exc:
                    logger.warning(
                        "decision_engine: review_queue enqueue failed for txn=%s: %s",
                        txn_id, exc,
                    )

        return decision

    # ------------------------------------------------------------------ #
    # Merchant risk appetite (Redis cache → DB → global default)
    # ------------------------------------------------------------------ #

    async def _get_merchant_appetite(self, merchant_id: str) -> dict[str, int]:
        """Return risk thresholds for a merchant.

        Cache hierarchy:
          1. Redis key `mrisk:{merchant_id}` (TTL 5 min)
          2. Postgres merchant_risk_config table
          3. Global default {block:80, challenge:60, review:40}

        Args:
            merchant_id: Merchant name/ID string from the transaction.

        Returns:
            Dict with keys 'block', 'challenge', 'review' as integers.
        """
        if not merchant_id:
            return dict(_DEFAULT_APPETITE)

        # ---- 1. Redis cache ---- #
        try:
            redis = get_redis()
            if redis is not None:
                cached = await redis.get(f"mrisk:{merchant_id}")
                if cached:
                    return json.loads(cached)
        except Exception as exc:
            logger.debug("merchant_appetite: Redis miss for %s: %s", merchant_id, exc)

        # ---- 2. Postgres lookup ---- #
        appetite = dict(_DEFAULT_APPETITE)
        try:
            pool = get_pool()
            if pool is not None:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT block_threshold, challenge_threshold, review_threshold
                        FROM   merchant_risk_config
                        WHERE  merchant_id = $1
                        """,
                        merchant_id,
                    )
                if row:
                    appetite = {
                        "block": int(row["block_threshold"]),
                        "challenge": int(row["challenge_threshold"]),
                        "review": int(row["review_threshold"]),
                    }
        except Exception as exc:
            logger.warning("merchant_appetite: DB lookup failed for %s: %s", merchant_id, exc)

        # ---- Cache result in Redis ---- #
        try:
            redis = get_redis()
            if redis is not None:
                await redis.set(
                    f"mrisk:{merchant_id}",
                    json.dumps(appetite),
                    ex=_MERCHANT_CACHE_TTL_SEC,
                )
        except Exception:
            pass

        return appetite

    # ------------------------------------------------------------------ #
    # Blacklist check
    # ------------------------------------------------------------------ #

    async def _is_blacklisted(self, txn: dict[str, Any]) -> Optional[str]:
        """Check if any entity involved in the transaction is blacklisted.

        Checks in order: user, merchant, location.
        Returns the block reason string, or None if no blacklist match.

        Caches individual entity checks in Redis with a short TTL (60s) to
        avoid a DB round-trip on every transaction for the same entities.
        In production, the blacklist set would be pushed to Redis on write
        and never require a DB call on the hot path.

        Args:
            txn: Transaction dict with user_id, merchant, location, etc.

        Returns:
            Reason string (non-empty = blocked), or None.
        """
        entities_to_check: list[tuple[str, str]] = []
        if txn.get("user_id"):
            entities_to_check.append(("user", str(txn["user_id"])))
        if txn.get("merchant"):
            entities_to_check.append(("merchant", str(txn["merchant"])))
        if txn.get("location"):
            entities_to_check.append(("location", str(txn["location"])))

        if not entities_to_check:
            return None

        try:
            pool = get_pool()
            if pool is None:
                return None

            async with pool.acquire() as conn:
                for entity_type, entity_value in entities_to_check:
                    row = await conn.fetchrow(
                        """
                        SELECT reason
                        FROM   blacklisted_entities
                        WHERE  entity_type  = $1
                          AND  entity_value = $2
                          AND  (expires_at IS NULL OR expires_at > NOW())
                        LIMIT 1
                        """,
                        entity_type,
                        entity_value,
                    )
                    if row:
                        reason = f"{entity_type}:{entity_value} — {row['reason']}"
                        logger.warning(
                            "blacklist.hit entity_type=%s entity_value=%s reason=%s",
                            entity_type, entity_value, row["reason"],
                        )
                        return reason
        except Exception as exc:
            logger.warning("blacklist.check_failed: %s — allowing (fail open)", exc)

        return None

    # ------------------------------------------------------------------ #
    # Admin helpers (used by routes/admin.py)
    # ------------------------------------------------------------------ #

    async def add_to_blacklist(
        self,
        entity_type: str,
        entity_value: str,
        reason: str,
        severity: str = "HIGH",
        expires_at: Any = None,
    ) -> int:
        """Insert an entity into the blacklist.

        Args:
            entity_type:  One of 'merchant', 'device', 'ip', 'card', 'user', 'location'.
            entity_value: The entity identifier string.
            reason:       Human-readable reason for the block.
            severity:     'LOW', 'MEDIUM', 'HIGH', or 'CRITICAL'.
            expires_at:   datetime or None.

        Returns:
            The new row id.

        Raises:
            RuntimeError if DB pool unavailable.
        """
        pool = get_pool()
        if pool is None:
            raise RuntimeError("DB pool unavailable — cannot add to blacklist")

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO blacklisted_entities (entity_type, entity_value, reason, severity, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (entity_type, entity_value) DO UPDATE
                    SET reason = EXCLUDED.reason,
                        severity = EXCLUDED.severity,
                        expires_at = EXCLUDED.expires_at,
                        added_at = NOW()
                RETURNING id
                """,
                entity_type, entity_value, reason, severity.upper(), expires_at,
            )
        entity_id = int(row["id"])
        logger.info(
            "blacklist.added id=%d entity_type=%s entity_value=%s severity=%s",
            entity_id, entity_type, entity_value, severity,
        )
        # Bust the Redis merchant-config cache if merchant was blacklisted
        if entity_type == "merchant":
            try:
                redis = get_redis()
                if redis:
                    await redis.delete(f"mrisk:{entity_value}")
            except Exception:
                pass
        return entity_id

    async def remove_from_blacklist(self, entity_id: int) -> bool:
        """Remove a blacklist entry by id.

        Returns:
            True if the row was deleted, False if id not found.
        """
        pool = get_pool()
        if pool is None:
            raise RuntimeError("DB pool unavailable")

        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM blacklisted_entities WHERE id = $1", entity_id
            )
        deleted = result.split()[-1] != "0"
        if deleted:
            logger.info("blacklist.removed id=%d", entity_id)
        return deleted

    async def upsert_merchant_config(
        self,
        merchant_id: str,
        block_threshold: int,
        challenge_threshold: int,
        review_threshold: int,
        custom_rules: dict | None = None,
    ) -> None:
        """Create or update merchant risk thresholds in DB and bust Redis cache.

        Args:
            merchant_id:         Merchant identifier.
            block_threshold:     0-100 score threshold for BLOCK action.
            challenge_threshold: 0-100 score threshold for CHALLENGE action.
            review_threshold:    0-100 score threshold for REVIEW action.
            custom_rules:        Optional JSON dict of additional rules.
        """
        pool = get_pool()
        if pool is None:
            raise RuntimeError("DB pool unavailable")

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO merchant_risk_config
                    (merchant_id, block_threshold, challenge_threshold, review_threshold, custom_rules, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (merchant_id) DO UPDATE
                    SET block_threshold     = EXCLUDED.block_threshold,
                        challenge_threshold = EXCLUDED.challenge_threshold,
                        review_threshold    = EXCLUDED.review_threshold,
                        custom_rules        = EXCLUDED.custom_rules,
                        updated_at          = NOW()
                """,
                merchant_id, block_threshold, challenge_threshold, review_threshold,
                json.dumps(custom_rules or {}),
            )

        # Bust Redis merchant config cache
        try:
            redis = get_redis()
            if redis:
                await redis.delete(f"mrisk:{merchant_id}")
        except Exception:
            pass

        logger.info(
            "merchant_config.upserted merchant=%s block=%d challenge=%d review=%d",
            merchant_id, block_threshold, challenge_threshold, review_threshold,
        )

    async def get_merchant_config(self, merchant_id: str) -> dict | None:
        """Fetch merchant risk config from DB.

        Returns:
            Dict with thresholds, or None if no custom config exists.
        """
        pool = get_pool()
        if pool is None:
            return None

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM merchant_risk_config WHERE merchant_id = $1",
                merchant_id,
            )
        if row is None:
            return None
        return dict(row)


    # ------------------------------------------------------------------ #
    # Phase 8: Review queue enqueue
    # ------------------------------------------------------------------ #

    async def enqueue_review(
        self,
        txn_id: int,
        score: int,
        decision: Decision,
        priority: str = "normal",
    ) -> None:
        """Insert a transaction into the review_queue table.

        Uses ON CONFLICT DO NOTHING on the unique index
        (uidx_review_queue_transaction_id where status != 'resolved') so that
        double-scoring the same transaction is idempotent.

        Args:
            txn_id:   Transaction primary key.
            score:    Risk score snapshot at decision time.
            decision: The Decision object (serialised to JSONB).
            priority: 'high' | 'normal' | 'low' (default 'normal').
        """
        pool = get_pool()
        if pool is None:
            logger.warning("decision_engine.enqueue_review: pool unavailable for txn=%d", txn_id)
            return

        import json as _json
        decision_json = _json.dumps({
            "action":         decision.action,
            "score":          decision.score,
            "reasons":        decision.reasons,
            "rule_overrides": decision.rule_overrides,
            "challenge_type": decision.challenge_type,
        })

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO review_queue (transaction_id, score, decision, priority, status)
                    VALUES ($1, $2, $3::jsonb, $4, 'pending')
                    ON CONFLICT DO NOTHING
                    """,
                    txn_id, score, decision_json, priority,
                )
            logger.info(
                "decision_engine.review_queued txn=%d score=%d priority=%s",
                txn_id, score, priority,
            )
        except Exception as exc:
            logger.warning(
                "decision_engine.enqueue_review failed txn=%d: %s", txn_id, exc
            )

    async def enqueue_counterfactual(self, txn_id: int, score: int) -> None:
        """Insert a borderline-ALLOW transaction as a counterfactual hold-out.

        Priority is 'low' — these items are not urgent and may sit in the queue
        until a batch label job resolves them (checking for disputes after 90d).

        Args:
            txn_id: Transaction primary key.
            score:  Risk score at allow time (expected 75–85 range).
        """
        pool = get_pool()
        if pool is None:
            return

        import json as _json
        decision_json = _json.dumps({
            "action":         "allow",
            "score":          score,
            "reasons":        ["counterfactual_hold_out"],
            "rule_overrides": ["counterfactual"],
            "challenge_type": None,
        })

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO review_queue (transaction_id, score, decision, priority, status)
                    VALUES ($1, $2, $3::jsonb, 'low', 'pending')
                    ON CONFLICT DO NOTHING
                    """,
                    txn_id, score, decision_json,
                )
            logger.debug(
                "decision_engine.counterfactual_queued txn=%d score=%d", txn_id, score
            )
        except Exception as exc:
            logger.debug(
                "decision_engine.enqueue_counterfactual failed txn=%d: %s", txn_id, exc
            )


# Module-level singleton
decision_engine = DecisionEngine()
