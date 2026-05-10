"""ScoreResult schema — the unified output of every scoring path.

Phase 1: Real-time event-driven scoring.
Phase 7 additions: explanation_detail (structured SHAP output); feature_vector
                   (stored for admin explain endpoint).
Dependencies: pydantic v2.

Why a dedicated schema?
  The ML layer, decision engine, SHAP explainer, and API layer all pass
  results around.  A typed Pydantic model enforces the contract at every
  boundary without defensive dict[str, Any] casts.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ScoreResult(BaseModel):
    """Output of a single scoring call (unsupervised and/or supervised layers).

    risk_score         — final blended 0-100 score (100 = most suspicious).
    risk_level         — bucketed label derived from risk_score + thresholds.
    unsup_score        — raw output of the EnsembleAnomalyDetector (0.0-1.0).
    sup_score          — XGBoost probability (0.0-1.0); None until Phase 3.
    signals            — dict of named sub-signals (amount_zscore, velocity…).
    explanation        — flat human-readable string from top 3 SHAP drivers
                         (Phase 7) or rule-based reason (Phases 1–6).
    explanation_detail — structured SHAP output dict (Phase 7); None until
                         supervised model + SHAP explainer are available.
                         Schema: {available, base_value, top_drivers, …}
    feature_vector_ref — opaque list of (feature_name, value) pairs for
                         the admin explain endpoint.  Not serialised in API
                         responses (excluded=True); stored in-memory only.
    detector_version   — monotonic version string for model tracking.
    latency_ms         — wall-clock time from feature assembly to score (ms).
    """

    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    unsup_score: float = Field(
        ge=0.0, le=1.0, description="Normalised unsupervised ensemble score"
    )
    sup_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Supervised model probability (None until Phase 3)",
    )

    signals: dict[str, Any] = Field(
        default_factory=dict,
        description="Named sub-signals: amount_zscore, velocity, burst_flag, etc.",
    )
    explanation: str = Field(
        default="",
        description="Flat human-readable top reasons (top-3 SHAP drivers in Phase 7)",
    )
    # Phase 7: structured SHAP attribution dict
    explanation_detail: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Phase 7: structured SHAP output.  "
            "None when supervised model or SHAP explainer not available.  "
            "Schema: {available, base_value, top_drivers: [{feature, value, "
            "shap_value, direction, human_readable}], feature_count, total_shap_sum}"
        ),
    )

    detector_version: str
    latency_ms: float = Field(ge=0.0)

    @classmethod
    def cold_start(cls, detector_version: str, latency_ms: float = 0.0) -> "ScoreResult":
        """Return a safe fallback score when no model is trained for the user.

        50 = MEDIUM is intentional: we do not want to BLOCK a user with no history
        (false positive) nor silently ALLOW without any signal (false negative).
        The downstream decision engine can apply a 'new user' override if needed.
        """
        return cls(
            risk_score=50,
            risk_level="MEDIUM",
            unsup_score=0.5,
            sup_score=None,
            signals={"reason": "no_model", "note": "User has insufficient transaction history"},
            explanation="Insufficient transaction history to score — default medium risk assigned.",
            detector_version=detector_version,
            latency_ms=latency_ms,
        )
