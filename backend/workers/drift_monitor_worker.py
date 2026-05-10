"""Hourly drift monitoring APScheduler worker for SmartSpend.

Phase 5: MLOps.
Dependencies: APScheduler (AsyncIOScheduler), DriftMonitor, Prometheus metrics,
              EventPublisher (to alert on high PSI).

Schedule: runs every 60 minutes.

Responsibilities:
  1. Call DriftMonitor.check_feature_drift() for every numeric feature.
  2. Write results to drift_reports table.
  3. Update Prometheus model_drift_psi gauges.
  4. Publish MODELS_DEPLOYED event (as alert) for features with PSI > 0.25.
  5. Check prediction drift (score distribution).

Why hourly?
  Fraud patterns can change rapidly (coordinated attack bursts, new malware,
  card data dumps).  Hourly drift detection catches these before they degrade
  model precision significantly, giving the on-call team time to promote a
  retrained model.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


class DriftMonitorWorker:
    """Wraps DriftMonitor with APScheduler job registration and DB persistence."""

    def start(self, scheduler: "AsyncIOScheduler") -> None:
        """Register the hourly drift check job with an already-started scheduler."""
        scheduler.add_job(
            self._run_drift_check,
            "interval",
            minutes=60,
            id="drift_monitor",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("drift_monitor_worker: registered hourly job")

    async def _run_drift_check(self) -> None:
        """Execute one full drift monitoring cycle."""
        logger.info("drift_monitor_worker: starting hourly check")
        from services.monitoring.drift import drift_monitor
        from services.monitoring.metrics import model_drift_psi, model_drift_kl

        # 1. Feature drift
        try:
            feature_psi: dict[str, float] = await drift_monitor.check_feature_drift()
        except Exception as exc:
            logger.exception("drift_monitor.check_feature_drift failed: %s", exc)
            feature_psi = {}

        # 2. Update Prometheus + persist to drift_reports
        for feature_name, psi_val in feature_psi.items():
            model_drift_psi.labels(feature_name=feature_name).set(psi_val)
            await self._persist_drift_report(feature_name, psi_val, 0.0, psi_val > 0.25)

        # 3. Alert on high PSI
        high_drift_features = [f for f, p in feature_psi.items() if p > 0.25]
        if high_drift_features:
            await self._publish_drift_alert(high_drift_features, feature_psi)

        # 4. Prediction drift
        try:
            pred_psi = await drift_monitor.check_prediction_drift()
            model_drift_psi.labels(feature_name="_prediction_score").set(pred_psi)
            if pred_psi > 0.25:
                logger.warning("drift_monitor: prediction score drift PSI=%.4f", pred_psi)
                await self._persist_drift_report("_prediction_score", pred_psi, 0.0, True)
                await self._publish_drift_alert(["_prediction_score"], {"_prediction_score": pred_psi})
        except Exception as exc:
            logger.warning("drift_monitor.check_prediction_drift failed: %s", exc)

        logger.info(
            "drift_monitor_worker: done features_checked=%d high_drift=%d",
            len(feature_psi), len(high_drift_features),
        )

    async def _persist_drift_report(
        self,
        feature_name: str,
        psi_value: float,
        kl_divergence: float,
        alert_triggered: bool,
    ) -> None:
        """Write one row to drift_reports."""
        from core.db import get_pool
        pool = get_pool()
        if pool is None:
            return
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO drift_reports
                        (feature_name, psi_value, kl_divergence, alert_triggered)
                    VALUES ($1, $2, $3, $4)
                    """,
                    feature_name, psi_value, kl_divergence, alert_triggered,
                )
        except Exception as exc:
            logger.warning("drift_worker._persist_drift_report failed: %s", exc)

    async def _publish_drift_alert(
        self,
        features: list[str],
        psi_map: dict[str, float],
    ) -> None:
        """Publish a drift alert event to the event bus."""
        try:
            from services.event_bus.publisher import event_publisher, TOPIC_MODELS_DEPLOYED
            payload = {
                "alert_type": "feature_drift",
                "features": features,
                "psi_values": psi_map,
                "triggered_at": datetime.now(timezone.utc).isoformat(),
            }
            await event_publisher.publish(TOPIC_MODELS_DEPLOYED, payload)
            logger.warning("drift_monitor: published drift alert for %d features", len(features))
        except Exception as exc:
            logger.warning("drift_worker._publish_drift_alert failed: %s", exc)


# Module-level singleton
drift_monitor_worker = DriftMonitorWorker()
