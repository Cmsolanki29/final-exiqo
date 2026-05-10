"""PSI-based drift monitoring for SmartSpend fraud ML models.

Phase 5: MLOps.
Dependencies: numpy, asyncpg (core/db.py), feature_store/catalog.py.
Performance budget: check_feature_drift() < 30s (runs hourly in background).

Why PSI?
  Population Stability Index is the industry-standard measure used by banks
  (Basel III model validation, Freddie Mac, Stripe Radar) for monitoring
  covariate shift.  It is:
    - Symmetric (unlike KL divergence)
    - Zero for identical distributions
    - Interpretable: PSI > 0.25 = significant shift requiring investigation

PSI interpretation thresholds:
  PSI < 0.10  → no significant change
  PSI 0.10-0.25 → some change, monitor
  PSI > 0.25  → significant change → alert + consider retraining

Reference distribution strategy:
  We compare the **previous 30-day window** (days -60 to -30) against the
  **current 30-day window** (days -30 to now).  This avoids needing to store
  a separate "training distribution" snapshot and naturally detects gradual
  drift.  When a model is first deployed, the two windows will be similar;
  drift manifests over time.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np

from core.db import get_pool

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Pure math functions (no I/O — fully testable)
# ------------------------------------------------------------------ #

def population_stability_index(
    reference: np.ndarray,
    current: np.ndarray,
    bins: int = 10,
) -> float:
    """Compute PSI between two 1-D numeric distributions.

    Args:
        reference: 1-D array of reference (baseline) values.
        current:   1-D array of current values.
        bins:      Number of equal-width bins computed from reference.

    Returns:
        PSI float ≥ 0.  Returns 0.0 if either array is empty.

    PSI = Σ (current_pct − ref_pct) × ln(current_pct / ref_pct)
    Small epsilon (1e-6) is added to each bin fraction to avoid log(0).
    Bins are defined on the reference distribution, clipped to [min, max].
    """
    if len(reference) == 0 or len(current) == 0:
        return 0.0

    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)

    # Remove NaN/inf
    ref = ref[np.isfinite(ref)]
    cur = cur[np.isfinite(cur)]
    if len(ref) == 0 or len(cur) == 0:
        return 0.0

    # Build bin edges from reference distribution
    min_val = ref.min()
    max_val = ref.max()
    if min_val == max_val:
        # Constant feature — no drift possible
        return 0.0

    edges = np.linspace(min_val, max_val, bins + 1)
    edges[-1] += 1e-9  # right-open on the last bin

    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)

    eps = 1e-6
    ref_pct = (ref_counts / len(ref)) + eps
    cur_pct = (cur_counts / len(cur)) + eps

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return round(psi, 6)


def kl_divergence(
    reference: np.ndarray,
    current: np.ndarray,
    bins: int = 10,
) -> float:
    """Compute KL divergence D_KL(reference || current).

    Note: KL is asymmetric.  We use reference as P and current as Q.
    Returns 0.0 if either array is empty.
    """
    if len(reference) == 0 or len(current) == 0:
        return 0.0

    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)

    ref = ref[np.isfinite(ref)]
    cur = cur[np.isfinite(cur)]
    if len(ref) == 0 or len(cur) == 0:
        return 0.0

    min_val = min(ref.min(), cur.min())
    max_val = max(ref.max(), cur.max())
    if min_val == max_val:
        return 0.0

    edges = np.linspace(min_val, max_val, bins + 1)
    edges[-1] += 1e-9

    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)

    eps = 1e-6
    p = (ref_counts / len(ref)) + eps
    q = (cur_counts / len(cur)) + eps

    kl = float(np.sum(p * np.log(p / q)))
    return round(kl, 6)


# ------------------------------------------------------------------ #
# DriftMonitor class
# ------------------------------------------------------------------ #

class DriftMonitor:
    """Hourly drift monitoring for SmartSpend fraud features.

    Methods:
        check_feature_drift()   — PSI for every numeric user/merchant feature.
        check_prediction_drift() — PSI on risk_score distribution.
        check_online_offline_consistency() — MAE between online and offline stores.

    All methods are async and require the asyncpg pool to be initialized.
    They degrade gracefully (return {}) if the pool is unavailable.
    """

    PSI_ALERT_THRESHOLD = 0.25
    WINDOW_DAYS = 30           # size of each comparison window
    REFERENCE_OFFSET_DAYS = 60  # reference = [now-60d, now-30d]

    def __init__(self) -> None:
        self._numeric_features: list[str] = []
        self._feature_names_loaded = False

    def _load_feature_names(self) -> list[str]:
        """Lazy-load numeric user/merchant feature names from the catalog."""
        if self._feature_names_loaded:
            return self._numeric_features
        try:
            from services.feature_store.catalog import FEATURE_CATALOG
            self._numeric_features = [
                spec.name
                for spec in FEATURE_CATALOG
                if spec.entity_type in ("user", "merchant")
                and spec.dtype in (int, float)
                and spec.source_query is not None
            ]
        except Exception as exc:
            logger.warning("drift.load_feature_names failed: %s", exc)
            self._numeric_features = []
        self._feature_names_loaded = True
        return self._numeric_features

    async def _fetch_feature_values(
        self,
        feature_name: str,
        since: datetime,
        until: datetime,
    ) -> np.ndarray:
        """Pull per-entity feature values from feature_snapshots table.

        Queries the most recent snapshot per entity in the time window.
        Returns a numpy array of float values (possibly empty).
        """
        pool = get_pool()
        if pool is None:
            return np.array([])
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (entity_id)
                           (features->>$1)::text AS val
                    FROM   feature_snapshots
                    WHERE  entity_type = 'user'
                      AND  computed_at >= $2
                      AND  computed_at <  $3
                    ORDER  BY entity_id, computed_at DESC
                    """,
                    feature_name,
                    since,
                    until,
                )
            values: list[float] = []
            for row in rows:
                try:
                    if row["val"] is not None:
                        values.append(float(row["val"]))
                except (TypeError, ValueError):
                    pass
            return np.array(values, dtype=float)
        except Exception as exc:
            logger.warning("drift.fetch_feature_values(%s) failed: %s", feature_name, exc)
            return np.array([])

    async def check_feature_drift(self) -> dict[str, float]:
        """Compute PSI for every numeric feature in the catalog.

        Compares the 30-day reference window (60-30 days ago) vs.
        current window (30-0 days ago) using feature_snapshots.

        Returns:
            Dict of feature_name → PSI value.
            Features with PSI > 0.25 log a warning.
        """
        now = datetime.now(timezone.utc)
        current_since = now - timedelta(days=self.WINDOW_DAYS)
        reference_since = now - timedelta(days=self.REFERENCE_OFFSET_DAYS)
        reference_until = now - timedelta(days=self.WINDOW_DAYS)

        feature_names = self._load_feature_names()
        if not feature_names:
            logger.warning("check_feature_drift: no numeric features found in catalog")
            return {}

        results: dict[str, float] = {}
        for fname in feature_names:
            ref_values = await self._fetch_feature_values(fname, reference_since, reference_until)
            cur_values = await self._fetch_feature_values(fname, current_since, now)
            if len(ref_values) < 10 or len(cur_values) < 10:
                # Not enough data for reliable PSI
                continue
            psi = population_stability_index(ref_values, cur_values)
            kl = kl_divergence(ref_values, cur_values)
            results[fname] = psi

            if psi > self.PSI_ALERT_THRESHOLD:
                logger.warning(
                    "drift.alert feature=%s psi=%.4f kl=%.4f threshold=%.2f",
                    fname, psi, kl, self.PSI_ALERT_THRESHOLD,
                )

        logger.info(
            "check_feature_drift: checked %d features, %d with data",
            len(feature_names), len(results),
        )
        return results

    async def check_prediction_drift(self) -> float:
        """PSI on risk_score distribution: last 30 days vs. previous 30 days.

        Returns:
            PSI float, or 0.0 if insufficient data.
        """
        pool = get_pool()
        if pool is None:
            return 0.0
        try:
            now = datetime.now(timezone.utc)
            current_since = now - timedelta(days=self.WINDOW_DAYS)
            reference_since = now - timedelta(days=self.REFERENCE_OFFSET_DAYS)
            reference_until = current_since

            async with pool.acquire() as conn:
                ref_rows = await conn.fetch(
                    "SELECT risk_score FROM transactions WHERE created_at >= $1 AND created_at < $2",
                    reference_since, reference_until,
                )
                cur_rows = await conn.fetch(
                    "SELECT risk_score FROM transactions WHERE created_at >= $1",
                    current_since,
                )

            ref_scores = np.array([r["risk_score"] for r in ref_rows if r["risk_score"] is not None], dtype=float)
            cur_scores = np.array([r["risk_score"] for r in cur_rows if r["risk_score"] is not None], dtype=float)

            if len(ref_scores) < 50 or len(cur_scores) < 50:
                return 0.0

            psi = population_stability_index(ref_scores, cur_scores)
            logger.info(
                "check_prediction_drift: ref_n=%d cur_n=%d psi=%.4f",
                len(ref_scores), len(cur_scores), psi,
            )
            return psi
        except Exception as exc:
            logger.warning("check_prediction_drift failed: %s", exc)
            return 0.0

    async def check_online_offline_consistency(
        self,
        sample_size: int = 200,
    ) -> float:
        """Sample transactions and compare online vs offline feature values.

        Fetches up to sample_size recent user IDs, retrieves their features
        from both the online store (Redis) and offline store (Postgres snapshot),
        and returns the mean absolute error across overlapping numeric features.

        Returns:
            MAE float (0.0 = perfect consistency).
        """
        pool = get_pool()
        if pool is None:
            return 0.0
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT user_id
                    FROM   transactions
                    ORDER  BY RANDOM()
                    LIMIT  $1
                    """,
                    sample_size,
                )
            user_ids = [str(r["user_id"]) for r in rows]
            if not user_ids:
                return 0.0

            from services.feature_store.online_store import OnlineFeatureStore
            from services.feature_store.offline_store import OfflineFeatureStore

            online_store = OnlineFeatureStore()
            offline_store = OfflineFeatureStore()
            now = datetime.now(timezone.utc)

            deltas: list[float] = []
            for uid in user_ids:
                online_feats = await online_store.get_features("user", uid)
                offline_feats = await offline_store.get_at_time("user", uid, now)
                if not online_feats or not offline_feats:
                    continue
                for key in online_feats:
                    if key in offline_feats:
                        try:
                            ov = float(online_feats[key])
                            fv = float(offline_feats.get("features", {}).get(key, ov))
                            deltas.append(abs(ov - fv))
                        except (TypeError, ValueError):
                            pass

            if not deltas:
                return 0.0
            mae = float(np.mean(deltas))
            logger.info("check_online_offline_consistency: sample=%d mae=%.4f", len(user_ids), mae)
            return mae
        except Exception as exc:
            logger.warning("check_online_offline_consistency failed: %s", exc)
            return 0.0


# Module-level singleton
drift_monitor = DriftMonitor()
