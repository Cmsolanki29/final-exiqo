/**
 * ShapExplanationBars — horizontal bar chart for SHAP feature contributions.
 * Phase 7 explainability. Gracefully handles loading / error / missing data.
 *
 * Props:
 *   features  [{name, shap_value, feature_value, normalizedValue, width, positive}]
 *   loading   {bool}
 *   error     {Error|null}
 *   maxBars   {number} default 5
 */

import React from "react";
import { motion } from "framer-motion";
import { topFeatures, humanizeFeatureName } from "../../utils/risk/shapHelpers";
import { RiskStatePlaceholder } from "./RiskStatePlaceholder";

function Bar({ feature, index }) {
  const color = feature.positive ? "#ef4444" : "#10b981";
  const label = humanizeFeatureName(feature.name);
  const valLabel =
    feature.feature_value != null ? String(feature.feature_value).slice(0, 8) : "";

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      className="flex items-center gap-2 text-xs"
    >
      {/* Feature name */}
      <span
        className="w-32 shrink-0 truncate text-gray-600 text-right"
        title={label}
      >
        {label}
      </span>

      {/* Bar track */}
      <div className="relative flex-1 h-4 rounded-sm overflow-hidden bg-gray-100">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${feature.width}%` }}
          transition={{ duration: 0.5, delay: index * 0.06, ease: "easeOut" }}
          className="absolute inset-y-0 left-0 rounded-sm"
          style={{ backgroundColor: color, opacity: 0.8 }}
        />
      </div>

      {/* Feature value */}
      <span className="w-14 shrink-0 text-gray-400 text-right">{valLabel}</span>

      {/* SHAP value */}
      <span
        className="w-14 shrink-0 font-mono font-medium text-right"
        style={{ color }}
      >
        {feature.positive ? "+" : ""}{feature.shap_value?.toFixed(3) ?? "—"}
      </span>
    </motion.div>
  );
}

export function ShapExplanationBars({ features = [], loading = false, error = null, maxBars = 5 }) {
  if (loading || error || !features.length) {
    return (
      <RiskStatePlaceholder
        loading={loading}
        error={error}
        empty={!loading && !error && !features.length}
        message="No SHAP data available"
      />
    );
  }

  const top = topFeatures(features, maxBars);

  return (
    <div className="space-y-2">
      {/* Legend */}
      <div className="flex gap-4 text-[10px] text-gray-400 mb-1">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-2 rounded-sm bg-red-400 opacity-80" />
          Increases risk
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-2 rounded-sm bg-green-500 opacity-80" />
          Reduces risk
        </span>
      </div>

      {/* Header row */}
      <div className="flex items-center gap-2 text-[10px] text-gray-400 uppercase tracking-wide">
        <span className="w-32 text-right shrink-0">Feature</span>
        <span className="flex-1">Impact</span>
        <span className="w-14 text-right shrink-0">Value</span>
        <span className="w-14 text-right shrink-0">SHAP</span>
      </div>

      {top.map((f, i) => (
        <Bar key={f.name} feature={f} index={i} />
      ))}
    </div>
  );
}
