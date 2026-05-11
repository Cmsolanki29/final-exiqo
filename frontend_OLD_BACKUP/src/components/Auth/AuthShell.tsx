import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { AnimatedShield } from "./AnimatedShield";
import { AuthCard } from "./AuthCard";
import { BackgroundEffects } from "./BackgroundEffects";

export type AuthShellProps = {
  cardTitle: string;
  cardLead: string;
  error: string;
  children: ReactNode;
  footer: ReactNode;
};

function StatPill({ children, delay }: { children: ReactNode; delay: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.span
      initial={reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: reduce ? 0 : delay, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-none inline-flex select-none items-center rounded-full border border-white/[0.1] bg-white/[0.06] px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-200/95 shadow-[0_0_20px_rgba(139,92,246,0.1),inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-md"
    >
      <motion.span
        className="inline-block"
        animate={reduce ? undefined : { y: [0, -3, 0] }}
        transition={{
          duration: 5 + delay * 0.4,
          repeat: Infinity,
          ease: "easeInOut",
          delay: delay * 0.25,
        }}
      >
        {children}
      </motion.span>
    </motion.span>
  );
}

export function AuthShell({ cardTitle, cardLead, error, children, footer }: AuthShellProps) {
  const reduce = useReducedMotion();

  return (
    <div className="relative flex min-h-screen flex-col bg-[#070B1A] font-sans text-slate-100 antialiased md:flex-row">
      {/* Unified ambient layer (both columns) */}
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_100%_70%_at_50%_-15%,rgba(139,92,246,0.1),transparent_52%),radial-gradient(ellipse_55%_45%_at_100%_40%,rgba(236,72,153,0.05),transparent_50%)]"
        aria-hidden
      />
      {/* Soft light spill at the column seam */}
      <div
        className="pointer-events-none absolute inset-y-0 left-1/2 hidden w-px -translate-x-1/2 bg-gradient-to-b from-transparent via-violet-500/20 to-transparent md:block"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-y-0 left-1/2 hidden w-[min(120px,12vw)] -translate-x-1/2 bg-[radial-gradient(ellipse_at_center,rgba(139,92,246,0.09),transparent_70%)] blur-2xl md:block"
        aria-hidden
      />

      {/* LEFT 50% — hero / storytelling */}
      <aside
        className="relative flex min-h-[50vh] w-full shrink-0 flex-col items-center justify-center overflow-hidden px-6 py-14 md:min-h-screen md:w-1/2 md:px-10 md:py-12"
        aria-label="SmartSpend brand"
      >
        <BackgroundEffects />

        <motion.div
          className="relative z-[2] flex w-full max-w-lg flex-col items-center justify-center text-center md:min-h-[min(520px,72vh)]"
          initial={reduce ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={reduce ? { duration: 0 } : { duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <AnimatedShield />

          {/* Wordmark is inside the logo image — avoid duplicate visible title */}
          <h1 className="auth-brand-sr-only">SmartSpend</h1>
          <p className="mt-8 max-w-md text-[15px] font-medium leading-relaxed tracking-wide text-slate-400/95 md:mt-9 md:text-base">
            AI-Powered Financial Intelligence
          </p>

          <motion.div
            className="mt-9 flex flex-wrap items-center justify-center gap-2.5 md:mt-10"
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: reduce ? 0 : 0.2, duration: 0.48 }}
          >
            <StatPill delay={0.32}>+32% Savings</StatPill>
            <StatPill delay={0.48}>AI Insights</StatPill>
            <StatPill delay={0.62}>Smart Analytics</StatPill>
          </motion.div>
        </motion.div>
      </aside>

      {/* RIGHT 50% — calm auth surface */}
      <main
        className="relative flex w-full shrink-0 flex-col items-center justify-center border-t border-white/[0.05] bg-gradient-to-b from-[#0b1224] via-[#0d1528] to-[#080f1c] px-5 py-14 md:w-1/2 md:border-l md:border-t-0 md:border-white/[0.06] md:px-12 md:py-16"
        aria-label="Authentication"
      >
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_90%_50%_at_50%_12%,rgba(139,92,246,0.1),transparent_58%),radial-gradient(ellipse_50%_42%_at_85%_75%,rgba(6,182,212,0.05),transparent_55%)]"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute left-1/2 top-[42%] h-[min(480px,85vh)] w-[min(380px,85vw)] max-w-full -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-600/[0.06] blur-[90px]"
          aria-hidden
        />

        <motion.div
          className="relative z-[1] w-full max-w-[460px]"
          initial={reduce ? false : { opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={reduce ? { duration: 0 } : { duration: 0.52, ease: [0.22, 1, 0.36, 1] }}
        >
          <AuthCard title={cardTitle} lead={cardLead} error={error} footer={footer}>
            {children}
          </AuthCard>
        </motion.div>
      </main>
    </div>
  );
}
