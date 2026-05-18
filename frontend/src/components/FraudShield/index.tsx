import React, { useMemo, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Activity, ArrowRight, ChevronRight, RefreshCw } from "lucide-react";
import AlertCards from "./AlertCards";
import MetricCards from "./MetricCards";
import TypologyPanel from "./TypologyPanel";
import TransactionTable from "./TransactionTable";
import { ALERT_CARDS, FLAGGED_TRANSACTIONS, METRICS, TYPOLOGIES } from "./mockData";

const ACCENT = "#F43F5E";
const PAGE_BG = "#0f1117";

type Props = {
  onNavigate?: (tab: string) => void;
};

function formatSyncedAt(d: Date) {
  return d.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZoneName: "short",
  });
}

export default function FraudShieldVigil({ onNavigate }: Props) {
  const reduce = useReducedMotion();
  const tableRef = useRef<HTMLElement>(null);
  const syncedAt = useMemo(() => formatSyncedAt(new Date()), []);
  const alertCount = ALERT_CARDS.length;

  const scrollToTable = () => {
    tableRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="w-full rounded-2xl p-1 font-sans" style={{ background: PAGE_BG }}>
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between"
      >
        <div className="min-w-0 flex-1">
          <motion.div
            className="mb-4 h-1 w-12 rounded-full"
            style={{ background: `linear-gradient(90deg, #7c3aed, ${ACCENT})` }}
            aria-hidden
          />
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: `${ACCENT}cc` }}>
            Risk awareness · FraudShield Vigil
          </p>
          <h1
            className="font-heading text-[clamp(1.75rem,3.5vw,2.5rem)] font-semibold leading-tight tracking-tight"
            style={{
              background: `linear-gradient(135deg, #ffffff 40%, ${ACCENT})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            FraudShield Vigil
          </h1>
          <p className="mt-2 max-w-xl text-[15px] leading-relaxed" style={{ color: "#8b8fa8" }}>
            Real-time mule detection & transaction risk monitoring
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-stretch gap-3 sm:items-end">
          <p className="flex items-center gap-2 text-xs" style={{ color: "#8b8fa8" }}>
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
            Last synced {syncedAt}
          </p>
          <div
            className="flex items-center gap-2 self-start rounded-full px-4 py-2 sm:self-end"
            style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.1)" }}
          >
            <span className="relative flex h-2 w-2">
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full"
                style={{ background: "rgba(52, 211, 153, 0.5)" }}
              />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            <span className="text-sm font-semibold text-white">AI active</span>
            <span className="text-sm" style={{ color: "rgba(255,255,255,0.45)" }}>
              ·
            </span>
            <span className="text-sm font-semibold tabular-nums text-white">{alertCount} alerts</span>
            <Activity className="h-4 w-4" style={{ color: "rgba(255,255,255,0.55)" }} aria-hidden />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={scrollToTable}
              className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-transparent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.06]"
            >
              Review Alerts
              <ArrowRight className="h-4 w-4" aria-hidden />
            </button>
            <button
              type="button"
              onClick={() => onNavigate?.("transactions")}
              className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-[0_0_24px_rgba(124,58,237,0.35)] transition hover:opacity-95"
              style={{ background: "linear-gradient(135deg, #7c3aed, #a855f7)" }}
            >
              Transactions
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      </motion.div>

      <div className="mt-8">
        <AlertCards cards={ALERT_CARDS} onCta={scrollToTable} />
      </div>

      <motion.div className="mt-6">
        <MetricCards metrics={METRICS} />
      </motion.div>

      <TypologyPanel typologies={TYPOLOGIES} />

      <TransactionTable ref={tableRef} rows={FLAGGED_TRANSACTIONS} />
    </div>
  );
}
