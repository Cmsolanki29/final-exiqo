/**
 * KPICard — A single dashboard KPI built on PremiumCard.
 *
 *  • Solid surface (inherits PremiumCard) → no bleed-through.
 *  • Variant-coloured icon container + trend pill.
 *  • Animated count-up for the headline number.
 *  • Refined inline sparkline drawn left-to-right on mount.
 */
import React, { useId, useMemo } from "react";
import { TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import PremiumCard, { type PremiumCardVariant } from "./PremiumCard";

type KPIVariant = Extract<PremiumCardVariant, "purple" | "emerald" | "rose" | "cyan" | "amber">;

const ICON_TINT: Record<KPIVariant, { bg: string; border: string; icon: string }> = {
  purple:  { bg: "bg-purple-500/10",  border: "border-purple-500/20",  icon: "text-purple-300" },
  emerald: { bg: "bg-emerald-500/10", border: "border-emerald-500/20", icon: "text-emerald-300" },
  rose:    { bg: "bg-rose-500/10",    border: "border-rose-500/20",    icon: "text-rose-300" },
  cyan:    { bg: "bg-cyan-500/10",    border: "border-cyan-500/20",    icon: "text-cyan-300" },
  amber:   { bg: "bg-amber-500/10",   border: "border-amber-500/20",   icon: "text-amber-300" },
};

const TREND_TINT: Record<KPIVariant, { bg: string; text: string; border: string }> = {
  purple:  { bg: "bg-purple-500/10",  text: "text-purple-300",  border: "border-purple-500/20" },
  emerald: { bg: "bg-emerald-500/10", text: "text-emerald-300", border: "border-emerald-500/20" },
  rose:    { bg: "bg-rose-500/10",    text: "text-rose-300",    border: "border-rose-500/20" },
  cyan:    { bg: "bg-cyan-500/10",    text: "text-cyan-300",    border: "border-cyan-500/20" },
  amber:   { bg: "bg-amber-500/10",   text: "text-amber-300",   border: "border-amber-500/20" },
};

// Accent colour used for the inner radial-gradient glow (same technique as HeroKpiTile).
const GLOW_HEX: Record<KPIVariant, string> = {
  purple:  "rgba(139,92,246,1)",
  emerald: "rgba(16,185,129,1)",
  rose:    "rgba(244,63,94,1)",
  cyan:    "rgba(6,182,212,1)",
  amber:   "rgba(245,158,11,1)",
};

const SPARK_COLOR: Record<KPIVariant, string> = {
  purple:  "#a78bfa",
  emerald: "#34d399",
  rose:    "#fb7185",
  cyan:    "#22d3ee",
  amber:   "#fbbf24",
};

// ─── Refined sparkline (drawn left-to-right on mount via dasharray) ───────────
function Sparkline({
  values,
  color,
  height = 36,
}: {
  values: number[];
  color: string;
  height?: number;
}) {
  const id = useId().replace(/:/g, "");

  const { points, length, area } = useMemo(() => {
    if (!values || values.length < 2) {
      return { points: "", length: 0, area: "" };
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    // 0..100 horizontally, 4..96 vertically (so the line never touches edges)
    const pts = values.map((v, i) => {
      const x = (i / (values.length - 1)) * 100;
      const y = 96 - ((v - min) / span) * 92;
      return [x, y] as const;
    });
    const polyline = pts.map(([x, y]) => `${x},${y}`).join(" ");
    const path = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
    const fillArea = `${path} L100,100 L0,100 Z`;
    return { points: polyline, length: pts.length * 25, area: fillArea };
  }, [values]);

  if (!points) return <div style={{ height }} aria-hidden />;

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ height }}
      className="w-full overflow-visible"
      aria-hidden
    >
      <defs>
        <linearGradient id={`g-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.30" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#g-${id})`} />
      <polyline
        fill="none"
        stroke={color}
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
        vectorEffect="non-scaling-stroke"
        style={{
          strokeDasharray: length,
          strokeDashoffset: length,
          animation: "kpi-spark-draw 900ms ease-out forwards",
        }}
      />
      <style>{`@keyframes kpi-spark-draw { to { stroke-dashoffset: 0; } }`}</style>
    </svg>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────────
export type KPICardProps = {
  variant: KPIVariant;
  label: string;
  value: number;
  /** Used by the count-up to format the running value. */
  formatValue: (n: number) => string;
  subtitle?: string;
  icon: LucideIcon;
  trendPct?: number | null;
  sparkline?: number[];
  delay?: number;
};

export default function KPICard({
  variant,
  label,
  value,
  formatValue,
  subtitle,
  icon: Icon,
  trendPct,
  sparkline = [],
  delay = 0,
}: KPICardProps) {
  // Render the real formatted value directly. The previous count-up animation
  // could race with React's effect cleanup and leave the displayed value at 0
  // even after the data had loaded — losing the entire purpose of the card.
  // Sparkline still draws in left-to-right via SVG dasharray below.
  const display = formatValue(Number.isFinite(value) ? value : 0);

  const tint  = ICON_TINT[variant];
  const trend = TREND_TINT[variant];
  const showTrend = trendPct != null && Number.isFinite(trendPct);
  const trendUp   = (trendPct ?? 0) >= 0;

  return (
    <PremiumCard variant={variant} topAccent delay={delay}>
      {/* Permanent inner accent glow — same radial-gradient technique as HeroKpiTile */}
      <div
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-[0.12]"
        style={{ background: `radial-gradient(ellipse at bottom right, ${GLOW_HEX[variant]} 0%, transparent 65%)` }}
        aria-hidden
      />

      {/* Top row — icon + trend pill */}
      <div className="flex items-start justify-between gap-3">
        <div
          className={[
            "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border",
            tint.bg,
            tint.border,
          ].join(" ")}
        >
          <Icon size={20} className={tint.icon} aria-hidden />
        </div>

        {showTrend && (
          <span
            className={[
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
              "text-[11px] font-semibold tabular-nums",
              trend.bg, trend.text, trend.border,
            ].join(" ")}
          >
            {trendUp
              ? <TrendingUp size={11} aria-hidden />
              : <TrendingDown size={11} aria-hidden />}
            {trendUp ? "+" : ""}{(trendPct as number).toFixed(1)}%
          </span>
        )}
      </div>

      {/* Label + big number + subtitle */}
      <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">
        {label}
      </p>
      <p className="mt-1.5 text-4xl font-bold tracking-tight text-white tabular-nums">
        {display}
      </p>
      {subtitle && (
        <p className="mt-1 text-xs text-gray-500">{subtitle}</p>
      )}

      {/* Sparkline footer */}
      {sparkline.length >= 2 && (
        <div className="mt-4 -mx-1">
          <Sparkline values={sparkline} color={SPARK_COLOR[variant]} />
        </div>
      )}
    </PremiumCard>
  );
}
