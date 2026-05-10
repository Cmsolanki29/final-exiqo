"""ShapContextTool — surface the existing Phase 7 SHAP explanation for a
transaction as input to the LLM agent.

If the SHAP explainer / supervised model isn't loaded, we still return the
stored ``anomaly_reason``, ``risk_score``, and ``risk_level`` so the agent
has *some* model context to reason over.
"""

from __future__ import annotations

import logging
from typing import Any

from core.db import get_pool
from services.phase_9_agent.tools.base_tool import BaseTool, ToolOutput

logger = logging.getLogger(__name__)


class ShapContextTool(BaseTool):
    name = "get_model_context"
    description = (
        "Fetch the existing fraud-model context for the transaction: the "
        "stored risk_score, risk_level, anomaly_reason, plus (when "
        "available) the top SHAP feature drivers explaining why the model "
        "scored the way it did.  Use this to ground your reasoning in what "
        "the ML pipeline already concluded."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer"},
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 15},
            },
            "required": ["transaction_id"],
        }

    async def execute(self, input_data: dict[str, Any]) -> ToolOutput:
        try:
            txn_id = int(input_data.get("transaction_id"))
        except (TypeError, ValueError):
            return ToolOutput(success=False, error="transaction_id must be an integer")
        top_k = max(1, min(int(input_data.get("top_k", 5) or 5), 15))

        # ---- Always fetch the stored model context ---- #
        try:
            pool = get_pool()
        except RuntimeError as exc:
            return ToolOutput(success=False, error=f"db_unavailable: {exc}")

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, user_id, amount, merchant, category,
                           hour_of_day, day_of_week, risk_score, risk_level,
                           anomaly_flag, anomaly_reason, is_fraud
                    FROM transactions
                    WHERE id = $1
                    """,
                    txn_id,
                )
        except Exception as exc:  # noqa: BLE001
            return ToolOutput(success=False, error=f"query_failed: {exc}")

        if row is None:
            return ToolOutput(success=False, error=f"transaction {txn_id} not found")

        stored_context = {
            "risk_score": int(row["risk_score"]) if row["risk_score"] is not None else None,
            "risk_level": row["risk_level"],
            "anomaly_flag": bool(row["anomaly_flag"]) if row["anomaly_flag"] is not None else None,
            "anomaly_reason": row["anomaly_reason"],
        }

        # ---- Try to enrich with live SHAP attributions ---- #
        shap_block: dict[str, Any] = {"available": False, "reason": "not_attempted"}
        try:
            from services.explainability.shap_explainer import shap_explainer
            from services.feature_store.feature_assembly import FeatureAssembler
            from ml_training.feature_engineering import (
                SUPERVISED_FEATURE_COLUMNS,
                assembled_to_feature_vector,
            )
            import numpy as np

            if shap_explainer.available:
                assembler = FeatureAssembler()
                txn_dict = dict(row)
                txn_feats = assembler._compute_txn_features(txn_dict, {})
                assembled: dict[str, Any] = {f"txn_{k}": v for k, v in txn_feats.items()}
                assembled["amt_ratio_30d"] = txn_feats.get("amount_vs_user_avg_30d", 1.0)
                assembled["merchant_changed"] = txn_feats.get("is_new_merchant", 0.0)
                feat_vec = assembled_to_feature_vector(assembled)
                if not isinstance(feat_vec, np.ndarray):
                    feat_vec = np.asarray(feat_vec, dtype=float)
                shap_block = shap_explainer.explain(
                    feat_vec, SUPERVISED_FEATURE_COLUMNS, top_k=top_k
                )
            else:
                shap_block = {"available": False, "reason": "shap_explainer_not_ready"}
        except Exception as exc:  # noqa: BLE001
            logger.debug("shap_context_tool SHAP enrichment skipped: %s", exc)
            shap_block = {"available": False, "reason": f"shap_error: {exc}"}

        return ToolOutput(
            success=True,
            data={
                "transaction_id": txn_id,
                "stored_context": stored_context,
                "shap": shap_block,
            },
        )
