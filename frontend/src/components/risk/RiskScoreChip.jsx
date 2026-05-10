/**
 * RiskScoreChip — compact badge showing the risk action + score for a transaction.
 * Clicking it opens ShapExplanationModal (Phase 7).
 *
 * Props:
 *   txnId   {string|number}
 *   action  {"allow"|"review"|"challenge"|"block"|null}
 *   score   {number} 0–1 (optional; omit if unavailable)
 *   onClick {() => void} override to handle click externally
 *   size    {"sm"|"md"} default "sm"
 */

import React from "react";
import { motion } from "framer-motion";
import { ShieldCheck, Eye, AlertTriangle, ShieldOff, Shield } from "lucide-react";
import { riskTheme } from "../../utils/risk/riskTheme";
import { fmtRiskScore } from "../../utils/risk/formatters";

function ActionIcon({ name, size = 12 }) {
  const p = { size, className: "shrink-0" };
  if (name === "ShieldCheck")  return <ShieldCheck {...p} />;
  if (name === "Eye")          return <Eye {...p} />;
  if (name === "AlertTriangle")return <AlertTriangle {...p} />;
  if (name === "ShieldOff")    return <ShieldOff {...p} />;
  return <Shield {...p} />;
}

export function RiskScoreChip({ txnId, action, score, onClick, size = "sm" }) {
  if (!action) return null;
  const theme   = riskTheme(action);
  const padding = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";

  return (
    <motion.button
      type="button"
      onClick={onClick}
      title={`Phase 7 SHAP — Transaction ${txnId || ""} · ${theme.label}${score != null ? ` · score ${fmtRiskScore(score)}` : ""}`}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.96 }}
      className={`
        inline-flex items-center gap-1 rounded-full border font-medium
        transition-all cursor-pointer select-none ${padding}
      `}
      style={{
        background: theme.bg,
        color:      theme.color,
        borderColor: theme.border,
      }}
    >
      <ActionIcon name={theme.iconName} size={size === "sm" ? 11 : 13} />
      <span>{theme.label}</span>
      {score != null && (
        <span className="opacity-60 text-[10px]">{fmtRiskScore(score)}</span>
      )}
    </motion.button>
  );
}
