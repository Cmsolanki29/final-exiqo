import React from "react";
import { motion } from "framer-motion";

/** `risk` is 0–1 (higher = riskier). Bands on 0–100: Safe 0–33, Watch 34–66, Risky 67+. */
export function BehaviorRiskGauge({ risk = 0, embedded = true }) {
  const pct = Math.min(100, Math.max(0, Math.round(Number(risk) * 100)));
  const band = pct <= 33 ? "safe" : pct <= 66 ? "watch" : "risky";
  const label = band === "safe" ? "Safe" : band === "watch" ? "Watch" : "Risky";
  const sub =
    band === "safe"
      ? "Patterns match your usual self."
      : band === "watch"
        ? "A few signals differ from baseline — stay alert."
        : "Several anomalies — review before large transfers.";

  const strokeColor = band === "safe" ? "#10b981" : band === "watch" ? "#f59e0b" : "#ef4444";
  const c = 40;
  const r = 32;
  const circ = 2 * Math.PI * r;
  const dashOffset = circ * (1 - pct / 100);

  const cardCls = embedded
    ? "rounded-2xl border border-white/10 bg-white/[0.04] p-6 backdrop-blur-xl"
    : "rounded-2xl border border-gray-100 bg-white p-5 shadow-sm";

  return (
    <div className={cardCls}>
      <h3 className={embedded ? "text-sm font-semibold text-white" : "text-sm font-semibold text-gray-700"}>
        Behavioral risk score
      </h3>
      <p className={embedded ? "mt-0.5 text-xs text-gray-500" : "mt-0.5 text-xs text-gray-400"}>
        Safe · Watch · Risky bands (0–100)
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-6">
        <div className="relative h-28 w-28 shrink-0">
          <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90" aria-hidden>
            <circle cx={c} cy={c} r={r} fill="none" stroke={embedded ? "rgba(255,255,255,0.08)" : "#f3f4f6"} strokeWidth="10" />
            <motion.circle
              cx={c}
              cy={c}
              r={r}
              fill="none"
              stroke={strokeColor}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circ}
              initial={{ strokeDashoffset: circ }}
              animate={{ strokeDashoffset: dashOffset }}
              transition={{ duration: 1.05, ease: [0.22, 1, 0.36, 1] }}
            />
          </svg>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className={embedded ? "text-xl font-bold tabular-nums text-white" : "text-xl font-bold tabular-nums text-gray-900"}>
              {pct}
            </span>
            <span className={embedded ? "text-[9px] text-gray-500" : "text-[9px] text-gray-400"}>/ 100</span>
          </div>
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <span
            className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wide ${
              band === "safe"
                ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-200"
                : band === "watch"
                  ? "border-amber-500/40 bg-amber-500/15 text-amber-100"
                  : "border-rose-500/40 bg-rose-500/15 text-rose-100"
            }`}
          >
            {label}
          </span>
          <p className={embedded ? "text-sm leading-relaxed text-gray-400" : "text-sm text-gray-600"}>{sub}</p>
          <div
            className={`flex flex-wrap gap-3 text-[10px] uppercase tracking-wider ${
              embedded ? "text-gray-500" : "text-gray-400"
            }`}
          >
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-400/80" /> Safe 0–33
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-amber-400/80" /> Watch 34–66
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-rose-400/80" /> Risky 67+
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
