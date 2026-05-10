/**
 * RiskLiveTicker — compact horizontal strip showing the last N flagged events.
 * Scrolls through events with a marquee-style animation.
 * Gracefully hides if no events / risk engine offline.
 */

import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Eye, ShieldOff, Activity } from "lucide-react";
import { riskTheme } from "../../utils/risk/riskTheme";
import { fmtCurrency, fmtRelativeTime } from "../../utils/risk/formatters";

/* Demo events shown when the live feed endpoint doesn't exist yet. */
const DEMO_EVENTS = [
  { id: 1, merchant: "Amazon", amount: 12500, action: "challenge", ts: Date.now() - 90_000 },
  { id: 2, merchant: "Unknown Vendor", amount: 4999,  action: "block",     ts: Date.now() - 200_000 },
  { id: 3, merchant: "Swiggy",    amount: 340,   action: "allow",     ts: Date.now() - 310_000 },
  { id: 4, merchant: "Paytm",     amount: 2100,  action: "review",    ts: Date.now() - 420_000 },
];

function ActionIcon({ action }) {
  const { iconName } = riskTheme(action);
  const props = { size: 12, className: "shrink-0" };
  if (iconName === "AlertTriangle") return <AlertTriangle {...props} />;
  if (iconName === "Eye")           return <Eye {...props} />;
  if (iconName === "ShieldOff")     return <ShieldOff {...props} />;
  return <Activity {...props} />;
}

export function RiskLiveTicker({ events: propEvents = null }) {
  const events = propEvents ?? DEMO_EVENTS;
  const [idx, setIdx] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!events.length) return;
    timerRef.current = setInterval(() => {
      setIdx((i) => (i + 1) % events.length);
    }, 4000);
    return () => clearInterval(timerRef.current);
  }, [events.length]);

  if (!events.length) return null;

  const ev      = events[idx];
  const theme   = riskTheme(ev.action);
  const isAlert = ev.action !== "allow";

  return (
    <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/95 border border-gray-100 shadow-sm text-xs overflow-hidden w-full max-w-md">
      {/* Pulsing indicator */}
      <span className="relative flex h-2 w-2 shrink-0">
        {isAlert && (
          <span
            className="absolute inline-flex h-full w-full rounded-full animate-ping opacity-70"
            style={{ backgroundColor: theme.color }}
          />
        )}
        <span
          className="relative inline-flex rounded-full h-2 w-2"
          style={{ backgroundColor: theme.color }}
        />
      </span>

      <span className="text-gray-400 shrink-0">Live:</span>

      <AnimatePresence mode="wait">
        <motion.div
          key={ev.id}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.25 }}
          className="flex items-center gap-1 min-w-0"
        >
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full font-medium text-[11px]"
            style={{ background: theme.bg, color: theme.color }}
          >
            <ActionIcon action={ev.action} />
            {theme.label}
          </span>
          <span className="text-gray-600 truncate">{ev.merchant}</span>
          <span className="text-gray-400 shrink-0">{fmtCurrency(ev.amount)}</span>
          <span className="text-gray-300 shrink-0">{fmtRelativeTime(ev.ts)}</span>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
