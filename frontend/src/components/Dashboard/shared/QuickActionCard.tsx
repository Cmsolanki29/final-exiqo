/**
 * QuickActionCard — Compact navigation card for the 4-up Guardian rail.
 *
 *  • Built on PremiumCard for a single consistent look.
 *  • PRIMARY title is NEVER truncated — the layout adapts instead.
 *  • Optional badge (count of pending items) sits in the top-right corner.
 *  • Whole card is a button so the entire surface is clickable.
 */
import React from "react";
import { ArrowRight, type LucideIcon } from "lucide-react";
import PremiumCard, { type PremiumCardVariant } from "./PremiumCard";

type QAVariant = Extract<PremiumCardVariant, "purple" | "emerald" | "rose" | "cyan" | "amber">;

const ICON_TINT: Record<QAVariant, { bg: string; border: string; icon: string }> = {
  purple:  { bg: "bg-purple-500/10",  border: "border-purple-500/20",  icon: "text-purple-300" },
  emerald: { bg: "bg-emerald-500/10", border: "border-emerald-500/20", icon: "text-emerald-300" },
  rose:    { bg: "bg-rose-500/10",    border: "border-rose-500/20",    icon: "text-rose-300" },
  cyan:    { bg: "bg-cyan-500/10",    border: "border-cyan-500/20",    icon: "text-cyan-300" },
  amber:   { bg: "bg-amber-500/10",   border: "border-amber-500/20",   icon: "text-amber-300" },
};

const LINK_COLOR: Record<QAVariant, string> = {
  purple:  "text-purple-300",
  emerald: "text-emerald-300",
  rose:    "text-rose-300",
  cyan:    "text-cyan-300",
  amber:   "text-amber-300",
};

const BADGE_TINT: Record<QAVariant, string> = {
  purple:  "bg-purple-500/15 text-purple-200 border-purple-500/30",
  emerald: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
  rose:    "bg-rose-500/15 text-rose-200 border-rose-500/30",
  cyan:    "bg-cyan-500/15 text-cyan-200 border-cyan-500/30",
  amber:   "bg-amber-500/15 text-amber-200 border-amber-500/30",
};

export type QuickActionCardProps = {
  variant: QAVariant;
  icon: LucideIcon;
  /** PRIMARY title — never truncated. */
  title: string;
  /** One-line status string under the title. */
  status: string;
  /** Optional numeric badge (e.g. pending alerts). */
  badge?: number;
  ctaLabel?: string;
  onClick: () => void;
  delay?: number;
};

export default function QuickActionCard({
  variant,
  icon: Icon,
  title,
  status,
  badge,
  ctaLabel = "Open",
  onClick,
  delay = 0,
}: QuickActionCardProps) {
  const tint = ICON_TINT[variant];

  return (
    <PremiumCard
      variant={variant}
      padding="compact"
      delay={delay}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className="cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-purple-400/50"
    >
      {/* Top row — icon + optional badge */}
      <div className="flex items-start justify-between">
        <div
          className={[
            "flex h-12 w-12 items-center justify-center rounded-xl border",
            tint.bg,
            tint.border,
          ].join(" ")}
        >
          <Icon size={22} className={tint.icon} aria-hidden />
        </div>
        {typeof badge === "number" && badge > 0 && (
          <span
            className={[
              "inline-flex min-w-[1.5rem] items-center justify-center rounded-full border",
              "px-2 py-0.5 text-[11px] font-bold tabular-nums",
              BADGE_TINT[variant],
            ].join(" ")}
          >
            {badge}
          </span>
        )}
      </div>

      {/* Title — full text, never truncated */}
      <h3 className="mt-4 text-base font-semibold leading-tight text-white">
        {title}
      </h3>

      {/* Status line */}
      <p className="mt-1 text-xs leading-snug text-gray-400">
        {status}
      </p>

      {/* CTA */}
      <span
        className={[
          "mt-4 inline-flex items-center gap-1 text-xs font-medium",
          LINK_COLOR[variant],
          "transition-transform duration-200 group-hover/card:translate-x-0.5",
        ].join(" ")}
      >
        {ctaLabel}
        <ArrowRight size={12} aria-hidden />
      </span>
    </PremiumCard>
  );
}
