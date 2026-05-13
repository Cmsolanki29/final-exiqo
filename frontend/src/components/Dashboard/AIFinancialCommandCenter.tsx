import React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Activity, ChevronRight, Sparkles } from "lucide-react";
import { GlassCard } from "../intro/GlassCard";
import { SkeletonCard } from "../common/SkeletonCard";

export type CommandCard = {
  id: string;
  urgency: "critical" | "warning" | "opportunity" | "safe" | "info";
  badge: string;
  title: string;
  body: string;
  metricLabel?: string;
  metricValue?: string;
  ctaLabel: string;
  onCta: () => void;
};

type Props = {
  signalCount: number;
  cards: CommandCard[];
  loading: boolean;
  aiActive: boolean;
};

const urgencyStyles: Record<
  CommandCard["urgency"],
  { ring: string; badge: string; glow: string }
> = {
  critical: {
    ring: "border-rose-500/35 hover:border-rose-400/50",
    badge: "bg-rose-500/20 text-rose-200 ring-1 ring-rose-500/30",
    glow: "bg-rose-500/15",
  },
  warning: {
    ring: "border-amber-500/35 hover:border-amber-400/50",
    badge: "bg-amber-500/20 text-amber-100 ring-1 ring-amber-500/30",
    glow: "bg-amber-500/12",
  },
  opportunity: {
    ring: "border-violet-500/35 hover:border-violet-400/50",
    badge: "bg-violet-500/20 text-violet-100 ring-1 ring-violet-500/30",
    glow: "bg-violet-500/12",
  },
  safe: {
    ring: "border-emerald-500/30 hover:border-emerald-400/45",
    badge: "bg-emerald-500/20 text-emerald-100 ring-1 ring-emerald-500/25",
    glow: "bg-emerald-500/10",
  },
  info: {
    ring: "border-cyan-500/25 hover:border-cyan-400/40",
    badge: "bg-cyan-500/15 text-cyan-50 ring-1 ring-cyan-500/25",
    glow: "bg-cyan-500/10",
  },
};

export default function AIFinancialCommandCenter({ signalCount, cards, loading, aiActive }: Props) {
  const reduce = useReducedMotion();

  return (
    <GlassCard
      surface="panel"
      padding="md"
      className="relative mb-6 overflow-hidden border-purple-500/20 bg-gradient-to-br from-purple-950/40 via-[#0c0a18]/90 to-cyan-950/25 ring-1 ring-white/[0.06]"
    >
      {!reduce ? (
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-purple-500/15 blur-3xl"
          aria-hidden
        />
      ) : null}
      {!reduce ? (
        <div
          className="pointer-events-none absolute -bottom-20 -left-16 h-56 w-56 rounded-full bg-cyan-500/10 blur-3xl"
          aria-hidden
        />
      ) : null}

      <div className="relative z-10 mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-1 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/55">
            <Sparkles className="h-3.5 w-3.5 text-cyan-300" aria-hidden />
            Live layer
          </div>
          <h2 className="mt-2 font-heading text-2xl font-bold tracking-tight text-white sm:text-3xl">
            AI financial command center
          </h2>
          <p className="mt-1 max-w-xl text-sm text-white/60">
            Pro signals from subscriptions, spend, and health — prioritized for action.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 rounded-2xl border border-white/10 bg-black/30 px-4 py-2.5">
          <span className="relative flex h-2.5 w-2.5">
            {aiActive ? (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/60" />
            ) : null}
            <span
              className={`relative inline-flex h-2.5 w-2.5 rounded-full ${aiActive ? "bg-emerald-400" : "bg-white/30"}`}
            />
          </span>
          <div className="text-right">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-white/45">Status</p>
            <p className="text-sm font-semibold text-white">{aiActive ? "AI active" : "Standby"}</p>
          </div>
          <Activity className="h-5 w-5 text-cyan-300/80" aria-hidden />
          <span className="rounded-lg bg-white/[0.06] px-2 py-1 text-xs font-bold tabular-nums text-white/90">
            {signalCount}
          </span>
        </div>
      </div>

      {loading ? (
        <div className="relative z-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} lines={4} height={148} />
          ))}
        </div>
      ) : cards.length === 0 ? (
        <p className="relative z-10 rounded-2xl border border-white/10 bg-black/25 px-4 py-6 text-center text-sm text-white/60">
          No prioritized alerts right now. Keep spending steady — we will surface waste, upgrades, and wins here.
        </p>
      ) : (
        <div className="relative z-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {cards.map((c, idx) => {
            const u = urgencyStyles[c.urgency];
            return (
              <motion.button
                key={c.id}
                type="button"
                onClick={c.onCta}
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: reduce ? 0 : 0.05 * idx, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                className={`group relative overflow-hidden rounded-2xl border bg-black/25 p-5 text-left backdrop-blur-sm transition-all duration-300 hover:bg-white/[0.04] ${u.ring}`}
              >
                {!reduce ? (
                  <div
                    className={`pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full blur-2xl ${u.glow}`}
                    aria-hidden
                  />
                ) : null}
                <div className="relative z-10 flex items-start justify-between gap-2">
                  <span className={`inline-flex max-w-[85%] items-center rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${u.badge}`}>
                    {c.badge}
                  </span>
                </div>
                <h3 className="relative z-10 mt-3 text-base font-bold leading-snug text-white">{c.title}</h3>
                <p className="relative z-10 mt-2 text-sm leading-relaxed text-white/60">{c.body}</p>
                <div className="relative z-10 mt-4 flex items-end justify-between gap-3">
                  <div>
                    {c.metricLabel ? (
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-white/45">{c.metricLabel}</p>
                    ) : null}
                    {c.metricValue ? (
                      <p className="mt-0.5 text-xl font-bold tabular-nums text-white">{c.metricValue}</p>
                    ) : null}
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-xl border border-white/15 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-white/90 transition group-hover:border-white/25 group-hover:bg-white/[0.1]">
                    {c.ctaLabel}
                    <ChevronRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" aria-hidden />
                  </span>
                </div>
              </motion.button>
            );
          })}
        </div>
      )}
    </GlassCard>
  );
}
