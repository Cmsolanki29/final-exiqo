import React, { ReactNode } from "react";

export type PageHeaderProps = {
  eyebrow?: string;
  title: string;
  /** Medium-weight line between title and subtitle (e.g. alert summary on dashboard). */
  lead?: string;
  subtitle?: string;
  rightSlot?: ReactNode;
  /** Accent hex colour for gradient title and eyebrow. */
  accentHex: string;
  /** Eyebrow line uses uppercase tracking by default (page labels). Set false for natural sentences. */
  eyebrowUppercase?: boolean;
  /** Dashboard home uses a larger hero title; feature pages use default. */
  titleScale?: "default" | "hero";
};

/**
 * Universal premium page header.
 * Left: identity bar pill → eyebrow → gradient title → subtitle.
 * Right: HeroKpiTile slot.
 * Spec: clamp(1.75rem, 3.5vw, 2.5rem) title, font-heading font-semibold.
 */
export function PageHeader({
  eyebrow,
  title,
  lead,
  subtitle,
  rightSlot,
  accentHex,
  eyebrowUppercase = true,
  titleScale = "default",
}: PageHeaderProps) {
  const titleSize =
    titleScale === "hero"
      ? "clamp(2rem, 4.5vw, 3.25rem)"
      : "clamp(1.75rem, 3.5vw, 2.5rem)";
  return (
    <div className="mb-8 flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
      {/* Left: identity bar + text */}
      <div className="min-w-0 flex-1">
        {/* 4 px gradient identity bar above the title */}
        <div
          className="mb-4 h-1 w-12 rounded-full"
          style={{ background: `linear-gradient(90deg, #7C3AED, ${accentHex})` }}
          aria-hidden
        />

        {eyebrow ? (
          <p
            className={[
              "mb-2 text-[11px] font-semibold tracking-[0.18em]",
              eyebrowUppercase ? "uppercase" : "",
            ].join(" ")}
            style={{ color: `${accentHex}cc` }}
          >
            {eyebrow}
          </p>
        ) : null}

        <h1
          className="font-heading font-semibold leading-tight tracking-tight text-white"
          style={{
            fontSize: titleSize,
            background: `linear-gradient(135deg, #ffffff 40%, ${accentHex})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          {title}
        </h1>

        {lead ? (
          <p className="mt-3 max-w-2xl text-[17px] font-medium leading-snug text-white/85">{lead}</p>
        ) : null}

        {subtitle ? (
          <p
            className={[
              "max-w-xl text-[15px] leading-relaxed text-white/65",
              lead ? "mt-2" : "mt-3",
            ].join(" ")}
          >
            {subtitle}
          </p>
        ) : null}
      </div>

      {/* Right: hero KPI tile slot */}
      {rightSlot && (
        <div className="shrink-0 lg:ml-6">{rightSlot}</div>
      )}
    </div>
  );
}

export default PageHeader;
