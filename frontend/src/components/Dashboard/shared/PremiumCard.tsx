/**
 * PremiumCard — Universal dashboard surface.
 *
 * Design principles:
 *  • Solid gradient background (NOT transparent) — content never bleeds through.
 *  • Signature shadow-glow that shifts colour with the variant prop.
 *  • Subtle hover lift (-0.5 translate + shadow expansion).
 *  • Optional 1-px gradient top accent for emphasis cards.
 *
 * Use this as the SINGLE card primitive across the dashboard. One look, everywhere.
 */
import React, { forwardRef } from "react";
import { motion, type HTMLMotionProps, useReducedMotion } from "framer-motion";

export type PremiumCardVariant = "purple" | "emerald" | "rose" | "cyan" | "amber" | "neutral";

type PremiumCardProps = Omit<HTMLMotionProps<"div">, "ref"> & {
  variant?: PremiumCardVariant;
  /** Adds a gradient hairline at the top of the card. */
  topAccent?: boolean;
  /** Reduce internal padding (used for dense cards like AI insights). */
  padding?: "default" | "compact";
  /** Disable hover lift (e.g. for non-interactive blocks). */
  interactive?: boolean;
  delay?: number;
  className?: string;
  children: React.ReactNode;
};

// Shadow-glow per variant — this is what makes the dashboard feel premium.
// Format: rest shadow + hover shadow.
// purple / rose / emerald use the same 60px-blur permanent glow as the
// "ANALYSED THIS MONTH" HeroKpiTile on the Transactions page (just color-swapped).
const SHADOW: Record<PremiumCardVariant, { rest: string; hover: string; accent: string }> = {
  purple:  {
    rest:  "shadow-[0_0_60px_-10px_rgba(139,92,246,0.40)]",
    hover: "hover:shadow-[0_0_70px_-10px_rgba(139,92,246,0.55)]",
    accent: "via-purple-400/40",
  },
  emerald: {
    rest:  "shadow-[0_0_60px_-10px_rgba(16,185,129,0.40)]",
    hover: "hover:shadow-[0_0_70px_-10px_rgba(16,185,129,0.55)]",
    accent: "via-emerald-400/40",
  },
  rose:    {
    rest:  "shadow-[0_0_60px_-10px_rgba(244,63,94,0.40)]",
    hover: "hover:shadow-[0_0_70px_-10px_rgba(244,63,94,0.55)]",
    accent: "via-rose-400/40",
  },
  cyan:    {
    rest:  "shadow-[0_8px_32px_-8px_rgba(6,182,212,0.20)]",
    hover: "hover:shadow-[0_14px_44px_-8px_rgba(6,182,212,0.35)]",
    accent: "via-cyan-400/40",
  },
  amber:   {
    rest:  "shadow-[0_8px_32px_-8px_rgba(245,158,11,0.20)]",
    hover: "hover:shadow-[0_14px_44px_-8px_rgba(245,158,11,0.32)]",
    accent: "via-amber-400/40",
  },
  neutral: {
    rest:  "shadow-[0_8px_32px_-12px_rgba(15,10,31,0.65)]",
    hover: "hover:shadow-[0_14px_44px_-12px_rgba(139,92,246,0.25)]",
    accent: "via-white/30",
  },
};

const PremiumCard = forwardRef<HTMLDivElement, PremiumCardProps>(function PremiumCard(
  {
    variant = "neutral",
    topAccent = false,
    padding = "default",
    interactive = true,
    delay = 0,
    className = "",
    children,
    ...rest
  },
  ref
) {
  const reduce = useReducedMotion();
  const s = SHADOW[variant];

  return (
    <motion.div
      ref={ref}
      initial={reduce ? { opacity: 1 } : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0.15 : 0.4, ease: [0.22, 1, 0.36, 1], delay: reduce ? 0 : delay }}
      className={[
        "group/card relative overflow-hidden rounded-2xl transition-all duration-300",
        // SOLID gradient background — never transparent.
        "bg-gradient-to-br from-[#15102A] to-[#0F0A1F]",
        "border border-white/[0.06]",
        padding === "compact" ? "p-5" : "p-6",
        s.rest,
        interactive ? `hover:border-white/[0.12] ${s.hover} hover:-translate-y-0.5` : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {topAccent && (
        <span
          aria-hidden
          className={`pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent ${s.accent} to-transparent`}
        />
      )}
      {children}
    </motion.div>
  );
});

export default PremiumCard;
