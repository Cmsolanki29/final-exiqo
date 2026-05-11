import type { HTMLAttributes, ReactNode } from "react";

export type GlassCardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  /** Visual elevation: "raised" adds extra glow + ring. */
  elevation?: "flat" | "raised";
  /** Inner padding scale. */
  padding?: "sm" | "md" | "lg";
};

const padMap = {
  sm: "p-4 md:p-5",
  md: "p-6 md:p-8",
  lg: "p-8 md:p-10",
};

/**
 * Glass token used across the intro flow.
 * `bg-white/5 backdrop-blur-2xl border border-white/10 rounded-2xl`
 */
export function GlassCard({
  children,
  elevation = "flat",
  padding = "md",
  className,
  ...rest
}: GlassCardProps) {
  const elevationClass =
    elevation === "raised"
      ? "shadow-[0_18px_60px_rgba(124,58,237,0.28),0_0_0_1px_rgba(255,255,255,0.06)_inset,0_0_60px_rgba(34,211,238,0.10)]"
      : "shadow-ss-glass";

  return (
    <div
      {...rest}
      className={`relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-2xl ${elevationClass} ${padMap[padding]} ${className ?? ""}`}
    >
      {/* Inner highlight + soft brand wash */}
      <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-white/[0.06] via-transparent to-violet-500/[0.04]" />
      <div className="relative">{children}</div>
    </div>
  );
}

export default GlassCard;
