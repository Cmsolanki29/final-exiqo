import React from "react";
import { motion } from "framer-motion";

const STATUS_STYLES = {
  live: {
    ping: "bg-emerald-400",
    dot: "bg-emerald-400",
    chip: "border-emerald-500/40 bg-emerald-500/15 text-emerald-200",
  },
  limited: {
    ping: "bg-amber-400/70",
    dot: "bg-amber-400",
    chip: "border-amber-500/40 bg-amber-500/15 text-amber-100",
  },
  shadow: {
    ping: "bg-sky-400/70",
    dot: "bg-sky-400",
    chip: "border-sky-500/40 bg-sky-500/15 text-sky-100",
  },
  training: {
    ping: "bg-amber-400/50",
    dot: "bg-amber-400",
    chip: "border-amber-500/35 bg-amber-500/10 text-amber-100",
  },
  inactive: {
    ping: "bg-slate-500/40",
    dot: "bg-slate-500",
    chip: "border-white/10 bg-white/[0.06] text-slate-400",
  },
};

export function PhaseCard({ phase, Icon, index }) {
  const Ico = Icon;
  const st = STATUS_STYLES.live;
  const label = "Active";
  const showPing = true;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.045, type: "spring", stiffness: 380, damping: 28 }}
      whileHover={{ y: -5, transition: { duration: 0.15 } }}
      className="group snap-start rounded-2xl border border-white/[0.08] bg-white/[0.04] p-4 shadow-[0_12px_40px_-28px_rgba(0,0,0,0.85)] transition-[box-shadow,border-color] duration-300 hover:border-violet-400/40 hover:shadow-[0_0_36px_-12px_rgba(124,58,237,0.5)]"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/20 text-xs font-bold tabular-nums text-violet-200 ring-1 ring-violet-400/30">
          {phase.n}
        </span>
        <span className="relative flex h-2 w-2">
          {showPing ? (
            <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${st.ping} opacity-50`} />
          ) : null}
          <span className={`relative inline-flex h-2 w-2 rounded-full ${st.dot}`} />
        </span>
      </div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-violet-200/90">
        <Ico className="h-4 w-4 shrink-0" aria-hidden />
        <span className="text-sm font-semibold leading-tight tracking-tight text-white">{phase.name}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide ${st.chip}`}>{label}</span>
      </div>
      <p className="text-[11px] leading-snug text-white/70">{phase.blurb}</p>
      <p className="mt-2 max-h-0 overflow-hidden text-[10px] leading-snug text-white/55 transition-all duration-300 group-hover:max-h-24">
        {phase.hoverDetail || `Phase ${phase.n} — ${phase.name}.`}
      </p>
    </motion.div>
  );
}
