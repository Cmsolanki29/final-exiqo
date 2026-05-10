/**
 * shapHelpers — utilities for rendering SHAP explanation payloads.
 *
 * Backend shape (from /api/transactions/:id/explain):
 * {
 *   features: [{ name, shap_value, feature_value }],
 *   base_value: float,
 *   predicted_risk_score: float,
 *   risk_action: "allow" | "review" | "challenge" | "block",
 *   natural_language: string
 * }
 */

export function sortFeaturesByImpact(features = []) {
  return [...features].sort(
    (a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value)
  );
}

export function normalizeShap(features = []) {
  const max = Math.max(...features.map((f) => Math.abs(f.shap_value)), 1);
  return features.map((f) => ({
    ...f,
    normalizedValue: f.shap_value / max,
    width: Math.abs(f.shap_value / max) * 100,
    positive: f.shap_value > 0,
  }));
}

export function topFeatures(features = [], n = 5) {
  return normalizeShap(sortFeaturesByImpact(features).slice(0, n));
}

export function humanizeFeatureName(raw = "") {
  return raw
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
