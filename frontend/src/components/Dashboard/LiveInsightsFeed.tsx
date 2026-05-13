import React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, ChevronRight } from "lucide-react";
import { GlassCard } from "../intro/GlassCard";
import { SkeletonCard } from "../common/SkeletonCard";

export type FeedAction = { label: string; variant?: "primary" | "ghost"; onClick: () => void };

export type FeedItem = {
  id: string;
  severity: "critical" | "warning" | "info" | "positive";
  badge: string;
  timeLabel: string;
  title: string;
  body: string;
  rightLabel?: string;
  rightValue?: string;
  actions: FeedAction[];
};

type Props = {
  items: FeedItem[];
  loading: boolean;
  onViewAll: () => void;
};

const sevRing: Record<FeedItem["severity"], string> = {
  critical: "border-rose-500/25 hover:border-rose-400/40",
  warning: "border-amber-500/25 hover:border-amber-400/35",
  info: "border-cyan-500/20 hover:border-cyan-400/35",
  positive: "border-emerald-500/25 hover:border-emerald-400/35",
};

const sevBadge: Record<FeedItem["severity"], string> = {
  critical: "bg-rose-500/15 text-rose-100 ring-1 ring-rose-500/25",
  warning: "bg-amber-500/15 text-amber-50 ring-1 ring-amber-500/25",
  info: "bg-cyan-500/12 text-cyan-50 ring-1 ring-cyan-500/20",
  positive: "bg-emerald-500/12 text-emerald-50 ring-1 ring-emerald-500/20",
};

export default function LiveInsightsFeed({ items, loading, onViewAll }: Props) {
  const reduce = useReducedMotion();

  return (
    <section className="mt-8">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="font-heading text-xl font-bold text-white sm:text-2xl">Live AI insights</h2>
          <p className="mt-1 text-sm text-white/55">Subscription intelligence + anomaly watch — newest first.</p>
        </div>
        <button
          type="button"
          onClick={onViewAll}
          className="inline-flex min-h-[48px] items-center justify-center gap-1.5 self-start rounded-xl border border-violet-400/35 bg-violet-500/15 px-4 py-2.5 text-sm font-semibold text-violet-100 transition hover:bg-violet-500/25 md:min-h-0"
        >
          View all insights
          <ArrowRight className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} lines={3} height={100} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <GlassCard surface="panel" padding="md" className="border-white/10 text-center text-sm text-white/55">
          No feed items yet. Open Subscriptions to run analysis, or check Insights for deeper reports.
        </GlassCard>
      ) : (
        <div className="space-y-3">
          {items.map((it, idx) => (
            <motion.div
              key={it.id}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: reduce ? 0 : 0.04 * idx }}
            >
              <GlassCard
                surface="panel"
                padding="md"
                className={`border transition-colors ${sevRing[it.severity]}`}
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex min-w-0 flex-1 gap-4">
                    <div className="hidden h-12 w-12 shrink-0 rounded-xl border border-white/10 bg-white/[0.05] sm:grid sm:place-items-center">
                      <ChevronRight className="h-5 w-5 text-white/35" aria-hidden />
                    </div>
                    <div className="min-w-0">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${sevBadge[it.severity]}`}>
                          {it.badge}
                        </span>
                        <span className="text-[11px] text-white/40">{it.timeLabel}</span>
                      </div>
                      <h3 className="text-base font-semibold text-white">{it.title}</h3>
                      <p className="mt-1 text-sm leading-relaxed text-white/60">{it.body}</p>
                      {it.actions.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {it.actions.map((a) => (
                            <button
                              key={a.label}
                              type="button"
                              onClick={a.onClick}
                              className={
                                a.variant === "ghost"
                                  ? "rounded-lg border border-white/12 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-white/80 transition hover:bg-white/[0.08]"
                                  : "rounded-lg border border-white/15 bg-gradient-to-r from-violet-500/25 to-fuchsia-500/20 px-3 py-1.5 text-xs font-semibold text-white transition hover:from-violet-500/35 hover:to-fuchsia-500/25"
                              }
                            >
                              {a.label}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                  {it.rightValue ? (
                    <div className="shrink-0 text-right lg:pl-4">
                      {it.rightLabel ? (
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-white/45">{it.rightLabel}</p>
                      ) : null}
                      <p className="text-lg font-bold tabular-nums text-white">{it.rightValue}</p>
                    </div>
                  ) : null}
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </div>
      )}
    </section>
  );
}
