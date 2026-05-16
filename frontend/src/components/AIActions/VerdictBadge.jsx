import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle } from "lucide-react";

const VERDICT_META = {
  GREEN: {
    label: "Affordable · Go for it",
    Icon: CheckCircle2,
    className:
      "border-emerald-500/40 bg-emerald-500/10 text-emerald-200 shadow-[0_0_30px_rgba(16,185,129,0.18)]",
    accent: "from-emerald-400/30 to-emerald-500/10",
  },
  YELLOW: {
    label: "Borderline · Choose a path",
    Icon: AlertTriangle,
    className:
      "border-amber-500/40 bg-amber-500/10 text-amber-200 shadow-[0_0_30px_rgba(245,158,11,0.18)]",
    accent: "from-amber-400/30 to-amber-500/10",
  },
  RED: {
    label: "Not viable yet · Try alternatives",
    Icon: XCircle,
    className:
      "border-rose-500/40 bg-rose-500/10 text-rose-200 shadow-[0_0_30px_rgba(244,63,94,0.18)]",
    accent: "from-rose-400/30 to-rose-500/10",
  },
};

export default function VerdictBadge({ verdict }) {
  const key = (verdict || "").toUpperCase();
  const meta = VERDICT_META[key] || {
    label: "Plan in progress",
    Icon: HelpCircle,
    className: "border-white/15 bg-white/[0.04] text-white/80",
    accent: "from-white/10 to-white/[0.02]",
  };
  const { Icon } = meta;

  return (
    <div className="relative inline-flex">
      <div
        className={`pointer-events-none absolute inset-0 -z-10 rounded-full bg-gradient-to-r ${meta.accent} blur-md`}
        aria-hidden
      />
      <span
        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold uppercase tracking-[0.14em] ${meta.className}`}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden />
        {meta.label}
      </span>
    </div>
  );
}
