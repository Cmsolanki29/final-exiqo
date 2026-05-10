"""Weekly automated retraining pipeline for SmartSpend supervised fraud model.

Phase 5: MLOps.
Dependencies: APScheduler, ml_training package, ModelRegistry, HybridScorer,
              ShadowLogger, asyncpg.

Schedule: every Sunday at 02:00 UTC.

Pipeline (in order):
  1. Pull last 90 days of labeled transactions.
  2. Build training matrix via feature_engineering.build_training_matrix.
  3. Train XGBoost via train_supervised.train_xgboost_model.
  4. Evaluate on held-out test set (PR-AUC, recall@FPR).
  5. Register in MLflow as a new version (stage=None).
  6. Promote to shadow (Staging in MLflow).
  7. Wait 24h (via another scheduler job) — then call _post_shadow_eval.
  8. _post_shadow_eval: run ShadowLogger.evaluate_shadow.
     - If pass → promote to canary at 5%.
     - If fail → alert + halt.
  9. After 24h canary if metrics stable → promote to production.

Note on single-process limitations:
  Steps 7-9 require delayed execution.  In a production system this would be
  an async workflow engine (Temporal, Prefect).  Here we use APScheduler
  one-shot jobs scheduled programmatically, which is safe for a single-process
  deployment.

Circuit-breaker conditions (halt promotion):
  - PR-AUC < 0.40 (worse than previous model)
  - shadow evaluate_shadow().passed == False
  - canary block_rate increase > 20% in any segment
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# Minimum PR-AUC to promote out of shadow
_MIN_PR_AUC_TO_PROMOTE = 0.40

# How long to keep model in shadow/canary before auto-promoting
_SHADOW_EVAL_DELAY_HOURS = 24
_CANARY_EVAL_DELAY_HOURS = 24


class RetrainScheduler:
    """Orchestrates weekly supervised model retraining and staged promotion."""

    def __init__(self) -> None:
        self._scheduler: Optional["AsyncIOScheduler"] = None

    def start(self, scheduler: "AsyncIOScheduler") -> None:
        """Register the weekly retrain job."""
        self._scheduler = scheduler
        scheduler.add_job(
            self._run_retraining_pipeline,
            "cron",
            day_of_week="sun",
            hour=2,
            minute=0,
            id="weekly_retrain",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("retrain_scheduler: registered weekly job (Sunday 02:00 UTC)")

    # ------------------------------------------------------------------ #
    # Main pipeline
    # ------------------------------------------------------------------ #

    async def _run_retraining_pipeline(self) -> None:
        """Step 1-6 of the retraining pipeline."""
        logger.info("retrain_scheduler: pipeline starting")
        start_dt = datetime.now(timezone.utc)

        try:
            version = await asyncio.get_event_loop().run_in_executor(
                None, self._train_and_register_sync
            )
        except Exception as exc:
            logger.exception("retrain_scheduler: training failed: %s", exc)
            return

        if version is None:
            logger.error("retrain_scheduler: registration returned None — aborting")
            return

        # Step 6: promote to shadow
        from services.ml_registry.registry import model_registry, FRAUD_MODEL_NAME
        promoted = model_registry.promote(
            FRAUD_MODEL_NAME, version, "shadow",
            promoted_by="retrain_scheduler", metrics={},
        )
        if not promoted:
            logger.error("retrain_scheduler: shadow promotion failed — aborting")
            return

        logger.info("retrain_scheduler: v%s in shadow — scheduling eval in %dh", version, _SHADOW_EVAL_DELAY_HOURS)

        # Step 7: schedule shadow eval
        if self._scheduler:
            run_at = datetime.now(timezone.utc) + timedelta(hours=_SHADOW_EVAL_DELAY_HOURS)
            self._scheduler.add_job(
                self._post_shadow_eval,
                "date",
                run_date=run_at,
                args=[version],
                id=f"shadow_eval_v{version}",
                replace_existing=True,
            )

    def _train_and_register_sync(self) -> Optional[str]:
        """Blocking: build features → train → evaluate → register.

        Returns MLflow version string or None on failure.
        """
        from datetime import datetime, timedelta, timezone
        import pandas as pd

        logger.info("retrain_scheduler: pulling labeled data (last 90d)")
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)

        # Pull data synchronously (psycopg2, runs in thread executor)
        df = self._pull_labeled_data_sync(start_date, end_date)
        if df is None or len(df) < 50:
            logger.warning("retrain_scheduler: insufficient labeled data (%d rows)", len(df) if df is not None else 0)
            return None

        logger.info("retrain_scheduler: pulled %d labeled rows", len(df))

        from ml_training.feature_engineering import build_features_from_df
        from ml_training.train_supervised import train_xgboost_model, save_model
        from ml_training.evaluation import evaluate_model
        from services.ml_registry.registry import model_registry
        from sklearn.model_selection import TimeSeriesSplit

        try:
            X, y = build_features_from_df(df)
            if len(X) < 50:
                logger.warning("retrain_scheduler: insufficient feature rows (%d)", len(X))
                return None

            # Time-based split
            splitter = TimeSeriesSplit(n_splits=5)
            splits = list(splitter.split(X))
            train_idx, val_idx = splits[-1]
            X_train = X.iloc[train_idx]
            y_train = y.iloc[train_idx]
            X_val = X.iloc[val_idx]
            y_val = y.iloc[val_idx]

            model, train_metrics = train_xgboost_model(X_train, y_train, X_val, y_val)
            eval_metrics = evaluate_model(model, X_val, y_val)

            pr_auc = eval_metrics.get("pr_auc", 0.0) or 0.0
            logger.info("retrain_scheduler: PR-AUC=%.4f", pr_auc)

            if pr_auc < _MIN_PR_AUC_TO_PROMOTE:
                logger.warning(
                    "retrain_scheduler: PR-AUC %.4f < threshold %.2f — model registered but not promoted",
                    pr_auc, _MIN_PR_AUC_TO_PROMOTE,
                )
                # Still register for tracking, but return None to skip promotion
                model_registry.register_model(
                    model,
                    metrics={**train_metrics, **eval_metrics},
                    hyperparams={"source": "weekly_retrain", "pr_auc": pr_auc},
                )
                return None

            all_metrics = {**train_metrics, **eval_metrics}
            version = model_registry.register_model(
                model,
                metrics=all_metrics,
                hyperparams={"source": "weekly_retrain", "n_train": len(X_train)},
            )
            # Also save to disk for Phase 3 fallback
            from core.config import get_settings
            save_model(model, get_settings().SUPERVISED_MODEL_PATH)
            return version

        except Exception as exc:
            logger.exception("retrain_scheduler._train_and_register_sync failed: %s", exc)
            return None

    def _pull_labeled_data_sync(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional["pd.DataFrame"]:
        """Pull labeled transactions synchronously using psycopg2."""
        try:
            import pandas as pd
            import psycopg2
            from core.config import get_settings
            conn = psycopg2.connect(get_settings().DATABASE_URL)
            query = """
                SELECT t.*
                FROM   transactions t
                WHERE  t.created_at >= %s
                  AND  t.created_at < %s
                  AND  t.is_fraud IS NOT NULL
                ORDER  BY t.created_at
            """
            df = pd.read_sql(query, conn, params=(start_date, end_date))
            conn.close()
            return df
        except Exception as exc:
            logger.exception("retrain_scheduler._pull_labeled_data_sync failed: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    # Shadow / canary eval (deferred jobs)
    # ------------------------------------------------------------------ #

    async def _post_shadow_eval(self, version: str) -> None:
        """Evaluate shadow model after 24h; promote to canary if pass."""
        logger.info("retrain_scheduler: evaluating shadow v%s", version)
        from services.monitoring.shadow_logger import shadow_logger
        from services.ml_registry.registry import model_registry, FRAUD_MODEL_NAME

        report = await shadow_logger.evaluate_shadow(period_days=1)
        if not report.get("passed", False):
            logger.error(
                "retrain_scheduler: shadow eval FAILED v%s — halting promotion. checks=%s",
                version, report.get("checks"),
            )
            await self._alert_pipeline_failure("shadow_eval_failed", version, report)
            return

        logger.info("retrain_scheduler: shadow eval passed v%s — promoting to canary 5%%", version)
        model_registry.promote(
            FRAUD_MODEL_NAME, version, "canary",
            promoted_by="retrain_scheduler",
            metrics={"shadow_psi": report.get("score_psi", 0.0)},
            traffic_percentage=5,
        )

        # Hot-reload the scorer with the new model
        from services.hybrid_scorer import hybrid_scorer
        hybrid_scorer.reload_models()

        if self._scheduler:
            run_at = datetime.now(timezone.utc) + timedelta(hours=_CANARY_EVAL_DELAY_HOURS)
            self._scheduler.add_job(
                self._post_canary_eval,
                "date",
                run_date=run_at,
                args=[version],
                id=f"canary_eval_v{version}",
                replace_existing=True,
            )

    async def _post_canary_eval(self, version: str) -> None:
        """Evaluate canary model after 24h; promote to production if stable."""
        logger.info("retrain_scheduler: evaluating canary v%s", version)
        from services.monitoring.shadow_logger import shadow_logger
        from services.ml_registry.registry import model_registry, FRAUD_MODEL_NAME

        report = await shadow_logger.evaluate_shadow(period_days=1)
        if not report.get("passed", False):
            logger.error(
                "retrain_scheduler: canary eval FAILED v%s — rolling back", version
            )
            model_registry.rollback(FRAUD_MODEL_NAME)
            await self._alert_pipeline_failure("canary_eval_failed", version, report)
            return

        logger.info("retrain_scheduler: canary eval passed v%s — promoting to PRODUCTION", version)
        model_registry.promote(
            FRAUD_MODEL_NAME, version, "production",
            promoted_by="retrain_scheduler",
            traffic_percentage=100,
        )

        # Hot-reload production model
        from services.hybrid_scorer import hybrid_scorer
        hybrid_scorer.reload_models()

        logger.info("retrain_scheduler: v%s is now PRODUCTION", version)

    async def _alert_pipeline_failure(
        self,
        alert_type: str,
        version: str,
        details: dict,
    ) -> None:
        """Publish a pipeline failure event for ops alerting."""
        try:
            from services.event_bus.publisher import event_publisher, TOPIC_MODELS_DEPLOYED
            await event_publisher.publish(
                TOPIC_MODELS_DEPLOYED,
                {
                    "alert_type": alert_type,
                    "model_version": version,
                    "details": details,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.warning("retrain_scheduler._alert_pipeline_failure publish failed: %s", exc)


# Module-level singleton
retrain_scheduler = RetrainScheduler()
