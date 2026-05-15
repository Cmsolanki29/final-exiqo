/**
 * LiveInsightsFeed — vertical list of AI insight cards.
 *
 * Each row is an <AIInsightCard /> built on PremiumCard so the whole dashboard
 * uses one consistent surface treatment.
 */
import React from "react";
import {
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import PremiumCard, { type PremiumCardVariant } from "./shared/PremiumCard";
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

// Severity → PremiumCard variant + icon + tint
const SEVERITY_MAP: Record<
  FeedItem["severity"],
  { variant: PremiumCardVariant; icon: LucideIcon; iconBg: string; iconBorder: string; iconColor: string; badgeBg: string; badgeText: string; badgeBorder: string }
> = {
  critical: {
    variant:    "rose",
    icon:       ShieldAlert,
    iconBg:     "bg-rose-500/10",
    iconBorder: "border-rose-500/20",
    iconColor:  "text-rose-300",
    badgeBg:    "bg-rose-500/10",
    badgeText:  "text-rose-300",
    badgeBorder:"border-rose-500/20",
  },
  warning: {
    variant:    "amber",
    icon:       AlertTriangle,
    iconBg:     "bg-amber-500/10",
    iconBorder: "border-amber-500/20",
    iconColor:  "text-amber-300",
    badgeBg:    "bg-amber-500/10",
    badgeText:  "text-amber-300",
    badgeBorder:"border-amber-500/20",
  },
  info: {
    variant:    "cyan",
    icon:       Sparkles,
    iconBg:     "bg-cyan-500/10",
    iconBorder: "border-cyan-500/20",
    iconColor:  "text-cyan-300",
    badgeBg:    "bg-cyan-500/10",
    badgeText:  "text-cyan-300",
    badgeBorder:"border-cyan-500/20",
  },
  positive: {
    variant:    "emerald",
    icon:       TrendingUp,
    iconBg:     "bg-emerald-500/10",
    iconBorder: "border-emerald-500/20",
    iconColor:  "text-emerald-300",
    badgeBg:    "bg-emerald-500/10",
    badgeText:  "text-emerald-300",
    badgeBorder:"border-emerald-500/20",
  },
};

// ─── Single insight row ───────────────────────────────────────────────────────
function AIInsightCard({ item, delay }: { item: FeedItem; delay: number }) {
  const m = SEVERITY_MAP[item.severity];
  const Icon = m.icon;

  return (
    <PremiumCard variant={m.variant} padding="compact" delay={delay}>
      <div className="flex items-start gap-4">
        {/* Severity icon container */}
        <div
          className={[
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border",
            m.iconBg,
            m.iconBorder,
          ].join(" ")}
        >
          <Icon size={20} className={m.iconColor} aria-hidden />
        </div>

        {/* Body */}
        <div className="min-w-0 flex-1">
          {/* Top meta row */}
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={[
                "rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                m.badgeBg,
                m.badgeText,
                m.badgeBorder,
              ].join(" ")}
            >
              {item.badge}
            </span>
            <span className="text-xs text-gray-500">{item.timeLabel}</span>
          </div>

          {/* Title + body */}
          <h3 className="mt-2 text-base font-semibold leading-tight text-white">
            {item.title}
          </h3>
          <p className="mt-1 text-sm leading-relaxed text-gray-400">
            {item.body}
          </p>

          {/* Actions */}
          {item.actions.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {item.actions.map((a) => (
                <button
                  key={a.label}
                  type="button"
                  onClick={a.onClick}
                  className={[
                    "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors duration-150",
                    a.variant === "ghost"
                      ? "border border-white/10 bg-white/[0.03] text-gray-300 hover:bg-white/[0.06] hover:text-white"
                      : "border border-purple-500/30 bg-purple-500/15 text-purple-200 hover:bg-purple-500/25",
                  ].join(" ")}
                >
                  {a.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right amount block */}
        {item.rightValue && (
          <div className="shrink-0 text-right">
            {item.rightLabel && (
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                {item.rightLabel}
              </p>
            )}
            <p className="mt-1 text-xl font-bold tabular-nums text-white">
              {item.rightValue}
            </p>
          </div>
        )}
      </div>
    </PremiumCard>
  );
}

// ─── List ─────────────────────────────────────────────────────────────────────
export default function LiveInsightsFeed({ items, loading, onViewAll }: Props) {
  return (
    <section>
      {/* Header */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Live AI insights</h2>
          <p className="mt-1 text-sm text-gray-400">
            Subscription intelligence + anomaly watch — newest first.
          </p>
        </div>
        <button
          type="button"
          onClick={onViewAll}
          className="inline-flex items-center gap-1.5 self-start rounded-lg border border-white/10 bg-white/[0.03] px-3.5 py-2 text-sm font-medium text-gray-300 transition-colors duration-150 hover:border-purple-500/30 hover:bg-purple-500/10 hover:text-white"
        >
          View all insights
          <ArrowRight size={14} aria-hidden />
        </button>
      </div>

      {/* Body */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} lines={3} height={100} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <PremiumCard variant="neutral" interactive={false}>
          <p className="text-center text-sm text-gray-400">
            No feed items yet. Open Subscriptions to run analysis, or check
            Insights for deeper reports.
          </p>
        </PremiumCard>
      ) : (
        <div className="space-y-3">
          {items.map((it, idx) => (
            <AIInsightCard key={it.id} item={it} delay={Math.min(idx, 4) * 0.05} />
          ))}
        </div>
      )}
    </section>
  );
}
