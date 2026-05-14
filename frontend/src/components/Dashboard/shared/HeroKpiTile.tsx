import React from "react";
import { GlassCard } from "../../intro/GlassCard";
import { DeltaChip } from "./DeltaChip";

export type HeroKpiTileProps = {
  label: string;
  /** Formatted string (inr / count / pct) already formatted by caller. */
  value: string;
  caption?: string;
  /** When true, show a skeleton bar instead of the caption line. */
  captionLoading?: boolean;
  delta?: number | null;
  /** Accent hex colour — used for the value gradient. Must match FEATURE_ACCENTS. */
  accentHex: string;
  loading?: boolean;
};

export function HeroKpiTile({
  label,
  value,
  caption,
  captionLoading,
  delta,
  accentHex,
  loading,
}: HeroKpiTileProps) {
  return (
    <GlassCard
      elevation="raised"
      className="min-w-[200px] shrink-0 border-white/[0.1] sm:min-w-[220px]"
      style={{ padding: "1.25rem 1.5rem" } as React.CSSProperties}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/55">{label}</p>
      <div className="mt-2 flex flex-wrap items-baseline gap-2">
        {loading ? (
          <span className="h-10 w-32 animate-pulse rounded-lg bg-white/[0.08]" />
        ) : (
          <span
            className="text-3xl font-semibold tabular-nums md:text-4xl"
            style={{
              background: `linear-gradient(135deg, #ffffff 30%, ${accentHex})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            {value}
          </span>
        )}
        {!loading && delta != null && <DeltaChip delta={delta} />}
      </div>
      {captionLoading ? (
        <span className="mt-2 block h-3 w-44 max-w-full animate-pulse rounded bg-white/[0.08]" aria-hidden />
      ) : caption ? (
        <p className="mt-1 text-xs leading-snug text-white/50">{caption}</p>
      ) : null}
      {/* Subtle accent glow behind the tile */}
      <div
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-10"
        style={{ background: `radial-gradient(ellipse at bottom right, ${accentHex} 0%, transparent 65%)` }}
        aria-hidden
      />
    </GlassCard>
  );
}

export default HeroKpiTile;
