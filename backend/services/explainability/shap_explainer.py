"""SHAP TreeExplainer wrapper for the XGBoost supervised fraud model.

Phase 7: SHAP Explainability.
Dependencies: shap>=0.44, xgboost>=2.0, numpy.
Performance budget:
  - First call: ~50–100ms (JIT compilation of tree structure).
  - Subsequent calls: ~5–20ms for a 500-estimator XGBoost on 28 features.
  - This is acceptable for the hot-path (adds ≤20ms to total scoring latency).
  - The admin explain endpoint has no latency budget constraint.

Why TreeExplainer?
  - Model-specific: uses the exact tree structure, not sampling approximations.
  - Additivity guarantee: sum(SHAP values) + base_value = model raw output.
    This is critical for "why was this transaction blocked?" interpretability.
  - Fast: O(depth × n_trees) per prediction, much faster than KernelExplainer.

SHAP output semantics:
  - base_value: average model output (in log-odds for XGBoost binary classifier).
  - shap_value[i] > 0: feature i INCREASES fraud probability.
  - shap_value[i] < 0: feature i DECREASES fraud probability.
  - sum(shap_values) + base_value ≈ model.predict(X, output_margin=True)[0].

Backward compatibility note:
  If SHAP is unavailable (model=None or library error), explain() returns
  {"available": False} and the scoring path continues unaffected.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class SHAPExplainer:
    """Wraps shap.TreeExplainer for the XGBoost supervised fraud model.

    Lifecycle:
      1. SHAPExplainer(model=hybrid_scorer._sup_model)  — created at startup.
      2. explain(feature_vector)  — called per-transaction on the hot path.
      3. reload(new_model)  — called after retraining / model promotion.

    Attributes:
        _explainer: The underlying shap.TreeExplainer, or None if unavailable.
        _model:     The XGBoost model this explainer was built for.
    """

    def __init__(self, model: Optional[Any] = None) -> None:
        """Initialize the explainer, optionally pre-loading a model.

        Args:
            model: An XGBoost classifier (xgb.XGBClassifier). If None, the
                   explainer is in a degraded state and explain() returns
                   {"available": False} until reload() is called.
        """
        self._explainer: Any | None = None
        self._model: Any | None = model
        if model is not None:
            self._build_explainer(model)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def explain(
        self,
        feature_vector: np.ndarray,
        feature_names: Optional[list[str]] = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Compute SHAP attributions for a single feature vector.

        Returns the top-k drivers with human-readable text, plus summary stats.
        If the explainer is unavailable, returns {"available": False}.

        Args:
            feature_vector: 1-D numpy array of shape (n_features,), in the same
                            order as SUPERVISED_FEATURE_COLUMNS.
            feature_names:  Optional list of names for each feature.  Defaults
                            to SUPERVISED_FEATURE_COLUMNS from feature_engineering.
            top_k:          Number of top SHAP drivers to return (default 5).

        Returns:
            Dict with:
              available (bool)          — False if explainer not ready.
              base_value (float)        — average model output (log-odds).
              top_drivers (list[dict])  — sorted by |shap_value| descending.
              feature_count (int)       — total features in the vector.
              total_shap_sum (float)    — sum of all SHAP values.
              latency_ms (float)        — time taken by this call.
        """
        if self._explainer is None:
            return {"available": False, "reason": "no_model"}

        t0 = time.perf_counter()
        try:
            X = feature_vector.reshape(1, -1)
            shap_values = self._explainer.shap_values(X)

            # Normalise output across different SHAP / XGBoost version styles:
            #   shap >= 0.44 with XGBoost binary: returns ndarray (1, n_features)
            #   older / multi-class: returns list [neg_class_arr, pos_class_arr]
            if isinstance(shap_values, list):
                sv = np.asarray(shap_values[1][0], dtype=float)
            else:
                sv = np.asarray(shap_values[0], dtype=float)

            base_value = self._explainer.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = float(np.asarray(base_value).flat[-1])
            else:
                base_value = float(base_value)

            # Resolve feature names
            if feature_names is None:
                try:
                    from ml_training.feature_engineering import SUPERVISED_FEATURE_COLUMNS
                    feature_names = SUPERVISED_FEATURE_COLUMNS
                except ImportError:
                    feature_names = [f"feature_{i}" for i in range(len(sv))]

            # Build top_k drivers sorted by |shap_value|
            n = len(sv)
            indices = np.argsort(np.abs(sv))[::-1][:top_k]
            top_drivers = self._build_drivers(
                sv, feature_vector, feature_names, indices
            )

            latency_ms = (time.perf_counter() - t0) * 1000
            logger.debug(
                "shap.explain top_driver=%s shap=%.3f latency_ms=%.1f",
                top_drivers[0]["feature"] if top_drivers else "n/a",
                top_drivers[0]["shap_value"] if top_drivers else 0.0,
                latency_ms,
            )

            return {
                "available":     True,
                "base_value":    base_value,
                "top_drivers":   top_drivers,
                "feature_count": n,
                "total_shap_sum": float(np.sum(sv)),
                "latency_ms":    latency_ms,
            }

        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning(
                "shap.explain_failed latency_ms=%.1f error=%s", latency_ms, exc
            )
            return {"available": False, "reason": str(exc), "latency_ms": latency_ms}

    def explain_full(
        self,
        feature_vector: np.ndarray,
        feature_names: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Like explain() but returns ALL feature SHAP values (for admin endpoint).

        Args:
            feature_vector: 1-D numpy array (n_features,).
            feature_names:  Optional list of names.

        Returns:
            Dict with available, base_value, all_features (list, sorted by |shap|),
            latency_ms.
        """
        if self._explainer is None:
            return {"available": False, "reason": "no_model"}

        t0 = time.perf_counter()
        try:
            X = feature_vector.reshape(1, -1)
            shap_values = self._explainer.shap_values(X)

            if isinstance(shap_values, list):
                sv = np.asarray(shap_values[1][0], dtype=float)
            else:
                sv = np.asarray(shap_values[0], dtype=float)

            base_value = self._explainer.expected_value
            if isinstance(base_value, (list, np.ndarray)):
                base_value = float(np.asarray(base_value).flat[-1])
            else:
                base_value = float(base_value)

            if feature_names is None:
                try:
                    from ml_training.feature_engineering import SUPERVISED_FEATURE_COLUMNS
                    feature_names = SUPERVISED_FEATURE_COLUMNS
                except ImportError:
                    feature_names = [f"feature_{i}" for i in range(len(sv))]

            all_indices = np.argsort(np.abs(sv))[::-1]
            all_features = self._build_drivers(
                sv, feature_vector, feature_names, all_indices
            )

            return {
                "available":     True,
                "base_value":    base_value,
                "all_features":  all_features,
                "feature_count": len(sv),
                "total_shap_sum": float(np.sum(sv)),
                "latency_ms":    (time.perf_counter() - t0) * 1000,
            }
        except Exception as exc:
            return {
                "available": False,
                "reason":    str(exc),
                "latency_ms": (time.perf_counter() - t0) * 1000,
            }

    def reload(self, model: Any) -> None:
        """Hot-reload the explainer with a new model (called after retraining).

        Args:
            model: New XGBoost classifier to rebuild the TreeExplainer for.
        """
        self._build_explainer(model)
        logger.info("shap_explainer.reloaded model=%s", type(model).__name__)

    @property
    def available(self) -> bool:
        """True if the explainer is ready to produce explanations."""
        return self._explainer is not None

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _build_explainer(self, model: Any) -> None:
        """Build (or rebuild) the shap.TreeExplainer from an XGBoost model.

        Fails silently so that scoring is never blocked by an explainer issue.
        """
        try:
            import shap
            self._explainer = shap.TreeExplainer(model)
            self._model = model
            logger.info(
                "shap_explainer.built model_type=%s n_estimators=%s",
                type(model).__name__,
                getattr(model, "n_estimators", "?"),
            )
        except Exception as exc:
            logger.warning("shap_explainer._build_explainer failed: %s", exc)
            self._explainer = None

    def _build_drivers(
        self,
        sv: np.ndarray,
        feature_vector: np.ndarray,
        feature_names: list[str],
        indices: np.ndarray,
    ) -> list[dict[str, Any]]:
        """Build a list of driver dicts for the given indices, sorted by |shap|."""
        from services.explainability.humanizer import humanize

        drivers = []
        for i in indices:
            if i >= len(feature_names):
                feat_name = f"feature_{i}"
            else:
                feat_name = feature_names[i]

            feat_val = float(feature_vector[i]) if i < len(feature_vector) else 0.0
            sv_val = float(sv[i])
            direction = "increases_risk" if sv_val > 0 else "decreases_risk"

            drivers.append({
                "feature":        feat_name,
                "value":          feat_val,
                "shap_value":     sv_val,
                "direction":      direction,
                "human_readable": humanize(feat_name, feat_val, sv_val),
            })
        return drivers


# Module-level singleton — created without a model; HybridScorer injects it
shap_explainer = SHAPExplainer()
