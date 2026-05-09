import { motion, useReducedMotion } from "framer-motion";
import { AuthParticleField } from "./AuthParticleField";

/** Left hero: EXIQO stack #070B1A → #111827 → #1E1B4B + mesh, orbs, noise, particles, light veil. */
export function BackgroundEffects() {
  const reduce = useReducedMotion();

  return (
    <>
      <div
        className="absolute inset-0 bg-gradient-to-br from-[#070B1A] via-[#111827] to-[#1E1B4B]"
        aria-hidden
      />
      <div
        className="absolute inset-0 bg-gradient-to-t from-transparent via-[#1e1b4b]/40 to-[#070b1a]/90"
        aria-hidden
      />
      <div
        className="absolute inset-0 bg-[radial-gradient(ellipse_82%_56%_at_50%_34%,rgba(139,92,246,0.22),transparent_62%)]"
        aria-hidden
      />
      <div
        className="absolute -left-28 top-[12%] h-[21rem] w-[21rem] rounded-full bg-violet-600/28 blur-[118px]"
        aria-hidden
      />
      <div
        className="absolute -right-20 bottom-[6%] h-[25rem] w-[25rem] rounded-full bg-fuchsia-500/22 blur-[128px]"
        aria-hidden
      />
      <div
        className="absolute left-[24%] top-[36%] h-72 w-72 -translate-x-1/2 rounded-full bg-cyan-400/12 blur-[96px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 animate-auth-mesh bg-[radial-gradient(at_22%_16%,rgba(139,92,246,0.3)_0%,transparent_50%),radial-gradient(at_84%_70%,rgba(236,72,153,0.18)_0%,transparent_48%),radial-gradient(at_50%_94%,rgba(6,182,212,0.1)_0%,transparent_44%)] opacity-[0.55] mix-blend-screen"
        aria-hidden
      />
      <motion.div
        className="pointer-events-none absolute -left-1/4 top-0 h-full w-[150%] opacity-[0.065]"
        style={{
          background:
            "conic-gradient(from 200deg at 50% 45%, transparent 0deg, rgba(139,92,246,0.45) 48deg, transparent 100deg, rgba(6,182,212,0.3) 190deg, transparent 280deg)",
        }}
        animate={reduce ? undefined : { rotate: [0, 360] }}
        transition={{ duration: 140, repeat: Infinity, ease: "linear" }}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.038]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
        }}
        aria-hidden
      />
      <AuthParticleField />
    </>
  );
}
