import { motion, useReducedMotion } from "framer-motion";

/**
 * Full SmartSpend logo (shield + wordmark) — transparent PNG, nothing cropped.
 * Glow pulse on `.auth-shield-glow-frame` only (box-shadow), not on the image pixels.
 */
export function AnimatedShield() {
  const reduce = useReducedMotion();
  const base = process.env.PUBLIC_URL ?? "";
  const src = `${base}/logo-without-bg.png`;

  return (
    <div className="relative mx-auto flex w-full justify-center px-2 max-w-[min(300px,92vw)] md:max-w-[min(320px,42vw)]">
      {/* Radial spotlight — behind shield only */}
      <div
        className="pointer-events-none absolute left-1/2 top-[42%] z-0 h-[min(440px,88vw)] w-[min(440px,88vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_50%_42%,rgba(139,92,246,0.36)_0%,rgba(236,72,153,0.14)_40%,rgba(6,182,212,0.09)_56%,transparent_72%)] blur-[96px] animate-auth-glow-pulse"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[46%] z-0 h-[min(260px,58vw)] w-[min(260px,58vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-fuchsia-500/16 blur-[76px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[36%] z-0 h-[min(200px,48vw)] w-[min(200px,48vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-400/12 blur-[64px]"
        aria-hidden
      />

      <motion.div
        className="relative z-[2] w-full max-w-[min(280px,90vw)] md:max-w-[min(320px,40vw)]"
        animate={reduce ? undefined : { y: [0, -10, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      >
        <motion.div
          animate={reduce ? undefined : { rotate: [-2, 2, -2] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        >
          <motion.div
            animate={reduce ? undefined : { scale: [1, 1.02, 1] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
            className="relative flex flex-col items-center"
          >
            <div className="auth-shield-glow-frame relative mx-auto w-full">
              <div className="relative z-[1] mx-auto w-full">
                <img
                  src={src}
                  alt="SmartSpend logo"
                  width={1024}
                  height={1024}
                  decoding="async"
                  loading="eager"
                  draggable={false}
                  className="pointer-events-none relative z-[1] mx-auto block h-auto w-full max-w-full object-contain object-center"
                  style={{ imageRendering: "auto" }}
                />
              </div>
            </div>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  );
}
