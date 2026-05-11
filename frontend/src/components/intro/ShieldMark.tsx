import { motion, useReducedMotion } from "framer-motion";

export type ShieldMarkProps = {
  /** Drives the staged choreography: outline → fill → bars → arrow. */
  stage?: "idle" | "outline" | "fill" | "bars" | "complete";
  /** Pixel size (square). */
  size?: number;
  /** Apply a heartbeat pulse. Used on intro story slide 2. */
  heartbeat?: boolean;
  className?: string;
  /** Forward layoutId for AnimatePresence morph from splash → navbar logo. */
  layoutId?: string;
};

const BRAND_EASE = [0.22, 1, 0.36, 1] as const;

/**
 * Animatable SVG twin of `/public/smartspend-shield-logo.png`.
 * Staged choreography matches the splash timeline:
 *   stage="outline" → shield border draws via pathLength
 *   stage="fill"    → brand gradient fills + glossy sweep
 *   stage="bars"    → 4 bar-chart bars rise (staggered)
 *   stage="complete"→ rising arrow exits the shield
 */
export function ShieldMark({
  stage = "complete",
  size = 220,
  heartbeat = false,
  className,
  layoutId,
}: ShieldMarkProps) {
  const reduce = useReducedMotion();

  const showOutline = stage !== "idle";
  const showFill = stage === "fill" || stage === "bars" || stage === "complete";
  const showBars = stage === "bars" || stage === "complete";
  const showArrow = stage === "complete";

  // Shield path — soft rounded shield with subtle taper.
  const shieldPath =
    "M64 8 C 96 16, 112 14, 124 22 L 124 66 C 124 95, 102 116, 64 124 C 26 116, 4 95, 4 66 L 4 22 C 16 14, 32 16, 64 8 Z";

  return (
    <motion.div
      layoutId={layoutId}
      className={`relative ${className ?? ""}`}
      style={{ width: size, height: size }}
      animate={
        heartbeat && !reduce
          ? { scale: [1, 1.045, 1, 1.025, 1] }
          : undefined
      }
      transition={{ duration: 1.6, repeat: heartbeat ? Infinity : 0, ease: "easeInOut" }}
    >
      {/* Soft halo */}
      <div
        className="pointer-events-none absolute inset-0 rounded-full"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(124,58,237,0.45) 0%, rgba(236,72,153,0.20) 35%, rgba(34,211,238,0.10) 55%, transparent 72%)",
          filter: "blur(28px)",
          opacity: showFill ? 1 : 0,
          transition: `opacity 700ms cubic-bezier(${BRAND_EASE.join(",")})`,
        }}
        aria-hidden
      />

      <svg
        viewBox="0 0 128 128"
        className="relative h-full w-full"
        aria-label="SmartSpend shield"
        role="img"
      >
        <defs>
          <linearGradient id="ssShieldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#7C3AED" />
            <stop offset="40%" stopColor="#A855F7" />
            <stop offset="75%" stopColor="#EC4899" />
            <stop offset="100%" stopColor="#22D3EE" />
          </linearGradient>
          <linearGradient id="ssShieldStroke" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#A855F7" />
            <stop offset="100%" stopColor="#22D3EE" />
          </linearGradient>
          <linearGradient id="ssGloss" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(255,255,255,0)" />
            <stop offset="50%" stopColor="rgba(255,255,255,0.45)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </linearGradient>
          <clipPath id="ssShieldClip">
            <path d={shieldPath} />
          </clipPath>
        </defs>

        {/* Outline draw */}
        <motion.path
          d={shieldPath}
          fill="none"
          stroke="url(#ssShieldStroke)"
          strokeWidth={2.4}
          strokeLinejoin="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{
            pathLength: showOutline ? 1 : 0,
            opacity: showOutline ? 1 : 0,
          }}
          transition={{ duration: reduce ? 0.2 : 0.6, ease: BRAND_EASE }}
        />

        {/* Gradient fill + gloss sweep */}
        <g clipPath="url(#ssShieldClip)">
          <motion.path
            d={shieldPath}
            fill="url(#ssShieldGrad)"
            initial={{ opacity: 0 }}
            animate={{ opacity: showFill ? 1 : 0 }}
            transition={{ duration: reduce ? 0.2 : 0.5, ease: BRAND_EASE }}
          />
          {/* Gloss highlight that sweeps L → R when fill becomes visible */}
          <motion.rect
            x={-60}
            y={0}
            width={48}
            height={128}
            fill="url(#ssGloss)"
            initial={{ x: -60, opacity: 0 }}
            animate={{ x: showFill ? 140 : -60, opacity: showFill ? 1 : 0 }}
            transition={{ duration: reduce ? 0.2 : 0.9, ease: BRAND_EASE, delay: showFill ? 0.15 : 0 }}
            style={{ mixBlendMode: "overlay" }}
          />
          {/* Subtle inner darken at the bottom for depth */}
          <rect x={0} y={70} width={128} height={58} fill="rgba(7,4,24,0.28)" />
        </g>

        {/* Bar chart inside shield (4 bars, rising) */}
        <g>
          {[
            { x: 30, h: 22, c: "#F5F3FF" },
            { x: 48, h: 36, c: "#F5F3FF" },
            { x: 66, h: 28, c: "#F5F3FF" },
            { x: 84, h: 48, c: "#F5F3FF" },
          ].map((b, i) => (
            <motion.rect
              key={b.x}
              x={b.x}
              width={10}
              rx={2}
              fill={b.c}
              initial={{ y: 92, height: 0, opacity: 0 }}
              animate={{
                y: showBars ? 92 - b.h : 92,
                height: showBars ? b.h : 0,
                opacity: showBars ? 0.95 : 0,
              }}
              transition={{
                duration: reduce ? 0.2 : 0.5,
                ease: BRAND_EASE,
                delay: showBars ? i * 0.08 : 0,
              }}
              style={{ transformBox: "fill-box" }}
            />
          ))}
        </g>

        {/* Rising arrow that exits the shield */}
        <motion.g
          initial={{ opacity: 0, y: 6 }}
          animate={{
            opacity: showArrow ? 1 : 0,
            y: showArrow ? -8 : 6,
          }}
          transition={{ duration: reduce ? 0.2 : 0.6, ease: BRAND_EASE, delay: showArrow ? 0.05 : 0 }}
        >
          <motion.path
            d="M 30 86 L 56 60 L 70 70 L 96 36"
            fill="none"
            stroke="#F5F3FF"
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: showArrow ? 1 : 0 }}
            transition={{ duration: reduce ? 0.2 : 0.55, ease: BRAND_EASE }}
          />
          <motion.path
            d="M 88 32 L 100 32 L 100 44"
            fill="none"
            stroke="#F5F3FF"
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: showArrow ? 1 : 0 }}
            transition={{ duration: reduce ? 0.2 : 0.4, ease: BRAND_EASE, delay: showArrow ? 0.35 : 0 }}
          />
        </motion.g>
      </svg>
    </motion.div>
  );
}

export default ShieldMark;
