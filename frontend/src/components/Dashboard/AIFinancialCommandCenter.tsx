import React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Activity, ChevronRight } from "lucide-react";
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

type CardVariant = "critical" | "migration" | "optimization" | "neutral";

function urgencyToVariant(urgency: CommandCard["urgency"]): CardVariant {
  if (urgency === "critical") return "critical";
  if (urgency === "warning" || urgency === "opportunity") return "migration";
  if (urgency === "safe") return "optimization";
  return "neutral";
}

const variantStyles: Record<
  CardVariant,
  { border: string; shadow: string; badgeBg: string; badgeColor: string }
> = {
  critical: {
    border: "1px solid rgba(239, 68, 68, 0.35)",
    shadow: "0 0 20px rgba(239, 68, 68, 0.08)",
    badgeBg: "rgba(239, 68, 68, 0.18)",
    badgeColor: "rgb(252, 165, 165)",
  },
  migration: {
    border: "1px solid rgba(234, 179, 8, 0.35)",
    shadow: "0 0 20px rgba(234, 179, 8, 0.08)",
    badgeBg: "rgba(234, 179, 8, 0.18)",
    badgeColor: "rgb(253, 224, 71)",
  },
  optimization: {
    border: "1px solid rgba(34, 197, 94, 0.35)",
    shadow: "0 0 20px rgba(34, 197, 94, 0.08)",
    badgeBg: "rgba(34, 197, 94, 0.18)",
    badgeColor: "rgb(134, 239, 172)",
  },
  neutral: {
    border: "1px solid rgba(255, 255, 255, 0.12)",
    shadow: "none",
    badgeBg: "rgba(255, 255, 255, 0.1)",
    badgeColor: "rgba(255, 255, 255, 0.75)",
  },
};

export default function AIFinancialCommandCenter({ signalCount, cards, loading, aiActive }: Props) {
  const reduce = useReducedMotion();

  return (
    <section
      className="relative mb-6 font-sans"
      style={{ background: "#0d0f14" }}
      aria-labelledby="ai-command-center-heading"
    >
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="relative flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between"
      >
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className="min-w-0 flex-1"
        >
          <h2
            id="ai-command-center-heading"
            className="text-2xl font-semibold tracking-tight text-white sm:text-[1.75rem]"
          >
            AI financial command center
          </h2>
          <p className="mt-1.5 max-w-xl text-sm font-normal" style={{ color: "rgba(255,255,255,0.50)" }}>
            Pro signals from subscriptions, spend, and health — prioritized for action.
          </p>
        </motion.div>

        <motion.div
          initial={reduce ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="flex shrink-0 items-center gap-2 self-start rounded-full px-4 py-2"
          style={{
            background: "rgba(255,255,255,0.07)",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <span className="relative flex h-2 w-2">
            {aiActive ? (
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full"
                style={{ background: "rgba(52, 211, 153, 0.5)" }}
              />
            ) : null}
            <span
              className="relative inline-flex h-2 w-2 rounded-full"
              style={{ background: aiActive ? "rgb(52, 211, 153)" : "rgba(255,255,255,0.35)" }}
            />
          </span>
          <span className="text-sm font-semibold text-white">
            {aiActive ? "AI active" : "Standby"}
          </span>
          <span className="text-sm font-normal" style={{ color: "rgba(255,255,255,0.45)" }}>
            ·
          </span>
          <span className="text-sm font-semibold tabular-nums text-white">{signalCount}</span>
          <Activity
            className="h-4 w-4"
            strokeWidth={1.75}
            style={{ color: "rgba(255,255,255,0.55)" }}
            aria-hidden
          />
        </motion.div>
      </motion.div>

      {loading ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} lines={4} height={148} />
          ))}
        </div>
      ) : cards.length === 0 ? (
        <p
          className="mt-6 rounded-xl px-5 py-6 text-center text-sm font-normal"
          style={{
            background: "rgba(255,255,255,0.07)",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "rgba(255,255,255,0.50)",
          }}
        >
          No prioritized alerts right now. Keep spending steady — we will surface waste, upgrades, and wins here.
        </p>
      ) : (
        <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {cards.map((c, idx) => {
            const variant = urgencyToVariant(c.urgency);
            const vs = variantStyles[variant];
            return (
              <motion.button
                key={c.id}
                type="button"
                onClick={c.onCta}
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: reduce ? 0 : 0.05 * idx, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                className="group w-full text-left transition-opacity duration-200 hover:opacity-95"
                style={{
                  background: "rgba(255,255,255,0.07)",
                  border: vs.border,
                  boxShadow: vs.shadow,
                  borderRadius: "12px",
                  padding: "20px",
                }}
              >
                <span
                  className="inline-block text-[11px] font-semibold uppercase tracking-wide"
                  style={{
                    background: vs.badgeBg,
                    color: vs.badgeColor,
                    padding: "4px 10px",
                    borderRadius: "20px",
                  }}
                >
                  {c.badge}
                </span>
                <h3 className="mt-3 text-base font-semibold leading-snug text-white">{c.title}</h3>
                <p className="mt-2 text-sm font-normal leading-relaxed" style={{ color: "rgba(255,255,255,0.50)" }}>
                  {c.body}
                </p>
                <div className="mt-4 flex items-end justify-between gap-3">
                  <div>
                    {c.metricLabel ? (
                      <p
                        className="text-[11px] font-semibold uppercase tracking-wide"
                        style={{ color: "rgba(255,255,255,0.45)" }}
                      >
                        {c.metricLabel}
                      </p>
                    ) : null}
                    {c.metricValue ? (
                      <p className="mt-0.5 text-xl font-semibold tabular-nums text-white">{c.metricValue}</p>
                    ) : null}
                  </div>
                  <span
                    className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold text-white transition group-hover:bg-white/[0.12]"
                    style={{
                      border: "1px solid rgba(255,255,255,0.15)",
                      background: "rgba(255,255,255,0.06)",
                    }}
                  >
                    {c.ctaLabel}
                    <ChevronRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" strokeWidth={1.75} aria-hidden />
                  </span>
                </div>
              </motion.button>
            );
          })}
        </div>
      )}
    </section>
  );
}
