import { motion, useReducedMotion } from "framer-motion";

export type RocketTrailProps = {
  /** Trigger the launch animation (false = idle on pad). */
  launch?: boolean;
  /** Sized to its container by default; pass explicit width if needed. */
  width?: number | string;
  height?: number | string;
  /** Color theme for the trail (cyan→magenta default). */
  trailFrom?: string;
  trailTo?: string;
  className?: string;
  /** Optional curve override (default is a curving up-right path). */
  pathD?: string;
};

const BRAND_EASE = [0.22, 1, 0.36, 1] as const;

/**
 * Animated SVG rocket that launches along a curving cyan→magenta trail.
 * Used by the splash and by intro story slide 3.
 *
 * The rocket is animated via SVG `motionPath`-style pathLength tweening
 * by translating along an SVG path manually (Framer Motion compatible).
 */
export function RocketTrail({
  launch = true,
  width = "100%",
  height = "100%",
  trailFrom = "#22D3EE",
  trailTo = "#EC4899",
  className,
  pathD = "M 28 200 C 60 140, 80 120, 130 80 S 220 30, 280 18",
}: RocketTrailProps) {
  const reduce = useReducedMotion();

  return (
    <div className={`relative ${className ?? ""}`} style={{ width, height }} aria-hidden>
      <svg viewBox="0 0 320 220" className="h-full w-full">
        <defs>
          <linearGradient id="rtTrail" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={trailFrom} stopOpacity="0" />
            <stop offset="35%" stopColor={trailFrom} stopOpacity="0.9" />
            <stop offset="100%" stopColor={trailTo} stopOpacity="0.95" />
          </linearGradient>
          <linearGradient id="rtBody" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#F5F3FF" />
            <stop offset="100%" stopColor="#A855F7" />
          </linearGradient>
          <linearGradient id="rtFlame" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#FBBF24" />
            <stop offset="100%" stopColor="#EC4899" />
          </linearGradient>
        </defs>

        {/* Trail */}
        <motion.path
          d={pathD}
          fill="none"
          stroke="url(#rtTrail)"
          strokeWidth={3.2}
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{
            pathLength: launch ? (reduce ? 1 : 1) : 0,
            opacity: launch ? 0.95 : 0,
          }}
          transition={{ duration: reduce ? 0.2 : 1.1, ease: BRAND_EASE }}
        />

        {/* Sparkles along trail */}
        {launch && !reduce
          ? [0.2, 0.4, 0.6, 0.8].map((t, i) => (
              <motion.circle
                key={t}
                r={2}
                fill="#F5F3FF"
                initial={{ opacity: 0, cx: 28, cy: 200 }}
                animate={{ opacity: [0, 1, 0] }}
                transition={{ duration: 0.9, ease: BRAND_EASE, delay: 0.3 + i * 0.12 }}
                style={{ offsetPath: `path("${pathD}")`, offsetDistance: `${t * 100}%` } as React.CSSProperties}
              />
            ))
          : null}

        {/* Rocket — line-art body, animated along the path */}
        <motion.g
          initial={{ offsetDistance: "0%", opacity: 0 }}
          animate={{
            offsetDistance: launch ? "100%" : "0%",
            opacity: launch ? 1 : 0,
          }}
          transition={{ duration: reduce ? 0.3 : 1.2, ease: BRAND_EASE, delay: 0.05 }}
          style={{
            offsetPath: `path("${pathD}")`,
            offsetRotate: "auto",
            transformOrigin: "center",
          } as React.CSSProperties}
        >
          {/* Translate so anchor sits at rocket tip */}
          <g transform="translate(-9 -9)">
            <path
              d="M 0 9 L 7 0 L 14 0 C 18 4, 18 14, 14 18 L 7 18 Z"
              fill="url(#rtBody)"
              stroke="#F5F3FF"
              strokeWidth={0.8}
            />
            <circle cx={11} cy={6} r={1.6} fill="#22D3EE" stroke="#F5F3FF" strokeWidth={0.4} />
            <path d="M 0 9 L -3 12 L 0 14 Z" fill="#7C3AED" />
            <path d="M 14 18 L 16 22 L 12 22 Z" fill="url(#rtFlame)" />
          </g>
        </motion.g>
      </svg>
    </div>
  );
}

export default RocketTrail;
