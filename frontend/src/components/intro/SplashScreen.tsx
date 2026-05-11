import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { AuroraBackground } from "./AuroraBackground";
import { RocketTrail } from "./RocketTrail";
import { ShieldMark } from "./ShieldMark";

const BRAND_EASE = [0.22, 1, 0.36, 1] as const;
const BRAND = "SmartSpend";
const TAGLINE = "Your money, intelligently shielded.";

export type SplashScreenProps = {
  /** Called once the splash finishes (after the 2.6s morph). */
  onComplete: () => void;
  /** Allows skipping via keyboard / click anywhere. */
  onSkip?: () => void;
  /** Shared layoutId for the morph into /intro navbar logo. */
  shieldLayoutId?: string;
};

/**
 * Cinematic 2.6s boot sequence (Stripe x Apple Vision Pro vibe):
 *  - 0.0s  Black field, 6px white dot pulses at center.
 *  - 0.3s  Dot bursts into 60 brand particles → form shield outline.
 *  - 0.8s  Shield fills with gradient, gloss sweeps L→R.
 *  - 1.2s  Rocket launches behind the shield with cyan→magenta trail.
 *  - 1.6s  4 bar-chart bars rise (80ms stagger), arrow exits the shield.
 *  - 2.0s  "SmartSpend" reveals letter by letter with a gradient mask.
 *  - 2.3s  Tagline fades in.
 *  - 2.6s  Composition scales to 0.25 + translates to top-left
 *          (morphs into the /intro navbar logo via shared layoutId).
 *
 * Honors prefers-reduced-motion (drops particle burst + rocket, keeps fades).
 */
export function SplashScreen({
  onComplete,
  onSkip,
  shieldLayoutId = "ssShieldMark",
}: SplashScreenProps) {
  const reduce = useReducedMotion();

  // 0..1 wallclock progress through the splash (capped at 1).
  const [t, setT] = useState(0);
  // Drives the AnimatePresence exit (morph to top-left).
  const [exiting, setExiting] = useState(false);

  // Particle ring used for the burst → shield-outline formation.
  const particles = useMemo(() => {
    const N = 60;
    const ring = 95; // radius around center the particles converge to
    return Array.from({ length: N }, (_, i) => {
      const angle = (i / N) * Math.PI * 2;
      // Pseudo-random offset for a chaotic burst.
      const seed = Math.sin(i * 14.31) * 1000;
      const r = seed - Math.floor(seed);
      return {
        id: i,
        // Scattered start position
        startX: (r - 0.5) * 380,
        startY: ((Math.cos(i * 7.7) * 1000) % 1) * 320 - 160,
        // Final ring position
        endX: Math.cos(angle) * ring,
        endY: Math.sin(angle) * ring,
        size: 2 + (i % 3),
        hue: i % 3,
      };
    });
  }, []);

  useEffect(() => {
    let raf = 0;
    let start: number | null = null;
    const total = reduce ? 1500 : 2600;
    const tick = (now: number) => {
      if (start === null) start = now;
      const p = Math.min(1, (now - start) / total);
      setT(p);
      if (p < 1) raf = requestAnimationFrame(tick);
      else {
        // Begin the morph exit
        setExiting(true);
        // Allow morph + AnimatePresence exit to play before unmounting
        window.setTimeout(onComplete, reduce ? 200 : 700);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [onComplete, reduce]);

  // Wallclock seconds for stage gating.
  const sec = t * (reduce ? 1.5 : 2.6);

  const showDot = sec < 0.5;
  const showParticles = sec >= 0.3 && sec < 1.2;
  const stage =
    sec < 0.3
      ? "idle"
      : sec < 0.8
      ? "outline"
      : sec < 1.6
      ? "fill"
      : sec < 2.0
      ? "bars"
      : "complete";
  const launchRocket = sec >= 1.2;
  const showWord = sec >= 2.0;
  const showTagline = sec >= 2.3;

  // Letters with progressive reveal
  const letters = BRAND.split("");

  const particleColor = (h: number) =>
    h === 0 ? "#7C3AED" : h === 1 ? "#EC4899" : "#22D3EE";

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center overflow-hidden bg-[#070418] font-sans text-ss-ink"
      role="dialog"
      aria-label="SmartSpend loading"
      onClick={onSkip}
    >
      <AuroraBackground starCount={70} />

      {/* Skip — top-right (subtle) */}
      {onSkip ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onSkip();
          }}
          className="absolute right-5 top-5 z-30 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70 backdrop-blur-md transition hover:border-white/20 hover:bg-white/[0.08] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
        >
          Skip
        </button>
      ) : null}

      {/* The morphing composition */}
      <AnimatePresence>
        {!exiting ? (
          <motion.div
            key="splash-stage"
            className="relative z-10 flex flex-col items-center justify-center"
            initial={{ scale: 1, x: 0, y: 0, opacity: 1 }}
            exit={
              reduce
                ? { opacity: 0, transition: { duration: 0.25 } }
                : {
                    scale: 0.25,
                    x: "-42vw",
                    y: "-42vh",
                    opacity: 0.6,
                    transition: { duration: 0.7, ease: BRAND_EASE },
                  }
            }
          >
            {/* Stage 1: pulsing dot — visible only at the very start */}
            <AnimatePresence>
              {showDot ? (
                <motion.div
                  key="dot"
                  className="absolute h-[6px] w-[6px] rounded-full bg-white shadow-[0_0_24px_rgba(245,243,255,0.8)]"
                  initial={{ scale: 0.4, opacity: 0 }}
                  animate={{ scale: [0.4, 1.4, 1], opacity: 1 }}
                  exit={{ scale: 4, opacity: 0 }}
                  transition={{ duration: 0.5, ease: BRAND_EASE }}
                />
              ) : null}
            </AnimatePresence>

            {/* Stage 2: 60 particles bursting → forming shield outline */}
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              {!reduce &&
                particles.map((p) => (
                  <motion.span
                    key={p.id}
                    className="absolute rounded-full"
                    style={{
                      width: p.size,
                      height: p.size,
                      background: particleColor(p.hue),
                      boxShadow: `0 0 8px ${particleColor(p.hue)}`,
                    }}
                    initial={{ x: 0, y: 0, opacity: 0, scale: 0.4 }}
                    animate={
                      showParticles
                        ? {
                            x: [0, p.startX, p.endX, p.endX],
                            y: [0, p.startY, p.endY, p.endY],
                            opacity: [0, 1, 0.95, 0],
                            scale: [0.4, 1, 0.85, 0.4],
                          }
                        : { opacity: 0 }
                    }
                    transition={{
                      duration: 0.95,
                      ease: BRAND_EASE,
                      times: [0, 0.35, 0.85, 1],
                    }}
                  />
                ))}
            </div>

            {/* Stage 3-5: animated shield with rocket launching from behind */}
            <div className="relative flex h-[260px] w-[260px] items-center justify-center">
              {/* Rocket BEHIND the shield (appears at t >= 1.2s) */}
              <div className="pointer-events-none absolute inset-0 -z-[1] flex items-center justify-center">
                <div className="absolute h-[260px] w-[320px] -translate-x-2 -translate-y-2">
                  <RocketTrail launch={launchRocket} />
                </div>
              </div>

              <ShieldMark
                stage={stage as "idle" | "outline" | "fill" | "bars" | "complete"}
                size={220}
                layoutId={shieldLayoutId}
              />
            </div>

            {/* Brand wordmark — letter by letter with gradient mask */}
            <div className="mt-8 h-[64px] overflow-hidden">
              <div className="flex items-baseline gap-[2px] font-heading text-[clamp(2.2rem,6vw,3.4rem)] font-semibold tracking-tight">
                {letters.map((ch, i) => (
                  <motion.span
                    key={`${ch}-${i}`}
                    className="bg-ss-brand bg-[length:200%_200%] bg-clip-text text-transparent"
                    initial={{ opacity: 0, y: 24, filter: "blur(8px)" }}
                    animate={
                      showWord
                        ? { opacity: 1, y: 0, filter: "blur(0px)" }
                        : { opacity: 0, y: 24, filter: "blur(8px)" }
                    }
                    transition={{
                      duration: 0.55,
                      ease: BRAND_EASE,
                      delay: showWord ? i * 0.045 : 0,
                    }}
                    style={{ backgroundPosition: "0% 50%" }}
                  >
                    {ch}
                  </motion.span>
                ))}
              </div>
            </div>

            {/* Tagline */}
            <motion.p
              className="mt-3 text-[13px] font-medium tracking-[0.18em] text-ss-mute md:text-sm"
              initial={{ opacity: 0, y: 8 }}
              animate={showTagline ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
              transition={{ duration: 0.55, ease: BRAND_EASE }}
            >
              {TAGLINE}
            </motion.p>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {/* Hint text — accessible cue for "tap anywhere / skip" */}
      <p className="absolute bottom-6 left-1/2 -translate-x-1/2 text-[10px] font-medium uppercase tracking-[0.22em] text-white/35">
        Tap anywhere to skip
      </p>
    </div>
  );
}

export default SplashScreen;
