import React from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Check,
  CircleDashed,
  Cloud,
  Compass,
  PiggyBank,
  Plane,
  TrendingUp,
  Wallet,
  Hotel,
} from "lucide-react";

const ICONS = {
  get_user_financial_context: Wallet,
  get_weather_for_destination: Cloud,
  search_flights: Plane,
  search_hotels: Hotel,
  explore_places: Compass,
  budget_optimizer: PiggyBank,
  project_future_savings: TrendingUp,
};

const SECTIONS = [
  {
    key: "internal",
    label: "SmartSpend Engine",
    match: (s) => s.source === "internal",
    headerClass: "text-violet-400/90",
    runningBorder: "border-violet-400/40 bg-violet-500/10",
    doneBorder: "border-emerald-500/30 bg-emerald-500/10",
    runningIcon: "text-violet-300",
  },
  {
    key: "travel",
    label: "Live Intelligence",
    match: (s) => s.source !== "internal",
    headerClass: "text-cyan-400/90",
    runningBorder: "border-cyan-400/40 bg-cyan-500/10",
    doneBorder: "border-emerald-500/30 bg-emerald-500/10",
    runningIcon: "text-cyan-300",
  },
];

/**
 * @param {{steps: Array<{id:string,tool:string,friendly:string,status:"running"|"done",summary?:string,source?:string}>}} props
 */
export default function ToolCallTimeline({ steps }) {
  if (!Array.isArray(steps) || steps.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
      className="mb-3 space-y-2"
    >
      {SECTIONS.map((section) => {
        const sectionSteps = steps.filter(section.match);
        if (sectionSteps.length === 0) return null;

        return (
          <motion.div
            key={section.key}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3"
          >
            <p
              className={`mb-2 px-1 text-[10px] font-bold uppercase tracking-[0.18em] ${section.headerClass}`}
            >
              {section.label}
            </p>
            <ul className="space-y-1.5">
              <AnimatePresence initial={false}>
                {sectionSteps.map((step) => {
                  const Icon = ICONS[step.tool] || CircleDashed;
                  const isRunning = step.status === "running";
                  return (
                    <motion.li
                      key={step.id}
                      initial={{ opacity: 0, x: -6 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                      className="flex items-center gap-3 px-1 py-1"
                    >
                      <span
                        className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg border ${
                          isRunning ? section.runningBorder : section.doneBorder
                        }`}
                      >
                        {isRunning ? (
                          <Icon
                            className={`h-3.5 w-3.5 animate-pulse ${section.runningIcon}`}
                            aria-hidden
                          />
                        ) : (
                          <Check className="h-3.5 w-3.5 text-emerald-300" aria-hidden />
                        )}
                      </span>

                      <motion.div layout className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-white">
                          {step.friendly || step.tool}
                          {isRunning ? (
                            <span className="ml-1 inline-flex gap-0.5 align-middle">
                              <Dot delay={0} />
                              <Dot delay={0.15} />
                              <Dot delay={0.3} />
                            </span>
                          ) : null}
                        </p>
                        {!isRunning && step.summary ? (
                          <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="truncate text-[11px] text-gray-400"
                          >
                            {step.summary}
                          </motion.p>
                        ) : null}
                      </motion.div>
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ul>
          </motion.div>
        );
      })}
    </motion.div>
  );
}

function Dot({ delay }) {
  return (
    <span
      className="inline-block h-1 w-1 rounded-full bg-current opacity-80"
      style={{ animation: `tp-dot-blink 1.1s ${delay}s infinite ease-in-out` }}
    />
  );
}
