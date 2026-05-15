import React from "react";
import { motion } from "framer-motion";
import { inr } from "../../lib/format";

const STATUS_STYLES = {
  BLOCKED: "bg-rose-500/25 text-rose-100 ring-rose-500/45 shadow-[0_0_16px_-4px_rgba(244,63,94,0.45)]",
  REVIEW: "bg-amber-500/20 text-amber-50 ring-amber-500/40 shadow-[0_0_14px_-4px_rgba(245,158,11,0.35)]",
  APPROVED: "bg-emerald-500/20 text-emerald-50 ring-emerald-500/35",
};

function StatusPulse({ status }) {
  const color =
    status === "BLOCKED" ? "bg-rose-400" : status === "REVIEW" ? "bg-amber-400" : "bg-emerald-400";
  return (
    <span className="relative flex h-2 w-2" aria-hidden>
      <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${color} opacity-55`} />
      <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
    </span>
  );
}

export default function LiveEventRow({ event: e }) {
  const pill = STATUS_STYLES[e.status] || STATUS_STYLES.APPROVED;

  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: -12, filter: "blur(4px)" }}
      animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
      exit={{ opacity: 0, height: 0, marginBottom: 0 }}
      transition={{ type: "spring", stiffness: 460, damping: 34 }}
      whileHover={{ scale: 1.005, transition: { duration: 0.15 } }}
      className="group relative overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-r from-white/[0.04] via-white/[0.02] to-transparent px-4 py-3.5 backdrop-blur-md sm:px-5"
    >
      <div
        className="pointer-events-none absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-violet-500/80 via-cyan-400/50 to-transparent opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        aria-hidden
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] text-[10px] font-bold tabular-nums text-gray-300">
            {e.score}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-white">{e.merchant}</p>
            <p className="mt-0.5 flex items-center gap-2 text-[11px] tabular-nums text-gray-500">
              <time dateTime={e.ts.toISOString()}>
                {e.ts.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </time>
              <span className="text-gray-600">·</span>
              <span className="text-gray-500">micro-score</span>
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3 sm:gap-4">
          <span className="text-sm font-bold tabular-nums tracking-tight text-white">{inr(e.amount)}</span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ring-1 ${pill}`}
          >
            <StatusPulse status={e.status} />
            {e.status}
          </span>
        </div>
      </div>
    </motion.li>
  );
}
