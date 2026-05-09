import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Calculator,
  CheckCircle2,
  CreditCard,
  IndianRupee,
  Plus,
  RefreshCcw,
  TrendingDown,
} from "lucide-react";
import { apiUtils, getEmiReport, scanEmi } from "../../services/api";
import { ErrorCard } from "../common/ErrorCard";

const DANGER_STYLES = {
  SAFE: {
    badge: "bg-emerald-500/20 text-emerald-400",
    healthBg:
      "from-emerald-500/10 via-exiqo-dark/50 to-emerald-500/5 border-emerald-500/30",
    healthIcon: "from-emerald-500 to-emerald-600",
    title: "EMI load is healthy",
  },
  WARNING: {
    badge: "bg-amber-500/20 text-amber-400",
    healthBg:
      "from-amber-500/10 via-exiqo-dark/50 to-amber-500/5 border-amber-500/30",
    healthIcon: "from-amber-500 to-orange-600",
    title: "EMI load needs attention",
  },
  DANGER: {
    badge: "bg-orange-500/20 text-orange-400",
    healthBg:
      "from-orange-500/10 via-exiqo-dark/50 to-orange-500/5 border-orange-500/30",
    healthIcon: "from-orange-500 to-red-600",
    title: "EMI load is high",
  },
  CRITICAL: {
    badge: "bg-rose-500/20 text-rose-400",
    healthBg: "from-rose-500/15 via-exiqo-dark/50 to-rose-500/10 border-rose-500/40",
    healthIcon: "from-rose-500 to-red-700",
    title: "Critical EMI pressure",
  },
};

const levelShort = {
  SAFE: "Within safe range",
  WARNING: "Approaching RBI limit",
  DANGER: "Over RBI safe limit",
  CRITICAL: "EMI trap risk",
};

const EMITrapDetector = ({ userId }) => {
  const [state, setState] = useState({ loading: true, error: "", data: null });
  const [newEmi, setNewEmi] = useState("");
  const [scanLoading, setScanLoading] = useState(false);

  const load = async () => {
    setState((p) => ({ ...p, loading: true, error: "" }));
    try {
      const data = await getEmiReport(userId);
      setState({ loading: false, error: "", data });
    } catch (err) {
      setState({ loading: false, error: err.message || "Unable to load EMI report", data: null });
    }
  };

  useEffect(() => {
    load();
  }, [userId]);

  const ratio = Number(state.data?.debt_to_income_ratio || 0);
  const dangerLevel = state.data?.danger_level || "SAFE";
  const ds = DANGER_STYLES[dangerLevel] || DANGER_STYLES.SAFE;
  const monthlyIncome = Number(state.data?.monthly_income || 0);
  const totalBurden = Number(state.data?.total_emi_burden || 0);
  const maxNew = Number(state.data?.max_new_emi_allowed || 0);
  const emis = state.data?.emis_detected || [];
  const activeCount = emis.length;

  const emiCheck = useMemo(() => {
    const considering = Number(newEmi || 0);
    const available = Number(state.data?.max_new_emi_allowed || 0);
    if (!considering) return "";
    if (available - considering >= 0) {
      return `Yes — after this EMI you still have ${apiUtils.formatINR(available - considering)} safe buffer.`;
    }
    return `No — this EMI would exceed your safe capacity by ${apiUtils.formatINR(Math.abs(available - considering))}.`;
  }, [newEmi, state.data?.max_new_emi_allowed]);

  const runScan = async () => {
    setScanLoading(true);
    try {
      await scanEmi(userId);
      await load();
    } finally {
      setScanLoading(false);
    }
  };

  const scrollToCalculator = () => {
    document.getElementById("emi-calculator")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (state.loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 animate-pulse rounded-xl bg-exiqo-dark/60" />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-2xl border border-exiqo-purple/20 bg-exiqo-dark/40" />
          ))}
        </div>
        <div className="h-48 animate-pulse rounded-3xl border border-exiqo-purple/20 bg-exiqo-dark/40" />
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="rounded-2xl border border-exiqo-purple/30 bg-exiqo-dark/40 p-6">
        <ErrorCard message={state.error} onRetry={load} />
      </div>
    );
  }

  const ratioLabel =
    ratio < 30 ? "Under 30% safe limit" : ratio < 40 ? "Near or above RBI guideline" : "Above RBI safe limit";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="mb-2 text-3xl font-bold text-white">EMI Trap Detector</h1>
          <p className="text-sm text-exiqo-glow/60">Monitor your debt health and avoid EMI traps</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={runScan}
            disabled={scanLoading}
            className="inline-flex items-center gap-2 rounded-xl border-2 border-exiqo-purple/40 bg-exiqo-dark/60 px-5 py-3 text-sm font-semibold text-white transition hover:border-exiqo-purple/60 hover:bg-exiqo-purple/15 disabled:opacity-50"
          >
            <RefreshCcw className={`h-4 w-4 ${scanLoading ? "animate-spin" : ""}`} />
            {scanLoading ? "Scanning…" : "Rescan"}
          </button>
          <button
            type="button"
            onClick={scrollToCalculator}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-exiqo-purple to-exiqo-pink px-6 py-3 text-sm font-semibold text-white shadow-lg transition hover:shadow-purple-glow"
          >
            <Plus className="h-5 w-5" />
            Plan new EMI
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        <motion.div
          whileHover={{ y: -4 }}
          className="relative overflow-hidden rounded-2xl border-2 border-exiqo-purple/30 bg-gradient-to-br from-exiqo-dark/80 to-exiqo-purple/10 p-6 shadow-xl"
        >
          <div className="mb-4 flex items-start justify-between">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-exiqo-purple to-exiqo-pink shadow-lg">
              <CreditCard className="h-6 w-6 text-white" />
            </div>
            <div className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold ${ds.badge}`}>
              {dangerLevel === "SAFE" ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <AlertCircle className="h-3 w-3" />
              )}
              {levelShort[dangerLevel] || levelShort.SAFE}
            </div>
          </div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-exiqo-glow/60">Total EMI burden</p>
          <h3 className="mb-2 text-4xl font-bold tracking-tight text-white">{apiUtils.formatINR(totalBurden)}</h3>
          <p className="text-sm font-medium text-exiqo-purple">
            {monthlyIncome > 0 ? `${ratio.toFixed(1)}% of income` : "Income not set — ratio N/A"}
          </p>
          <div className="pointer-events-none absolute bottom-0 right-0 h-32 w-32 rounded-tl-full bg-gradient-to-tl from-white/5 to-transparent" />
        </motion.div>

        <motion.div
          whileHover={{ y: -4 }}
          className="relative overflow-hidden rounded-2xl border-2 border-emerald-500/30 bg-gradient-to-br from-exiqo-dark/80 to-emerald-500/10 p-6 shadow-xl"
        >
          <div className="mb-4 flex items-start justify-between">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 shadow-lg">
              <TrendingDown className="h-6 w-6 text-white" />
            </div>
          </div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-exiqo-glow/60">Debt-to-income</p>
          <h3 className="mb-2 text-4xl font-bold tracking-tight text-white">{ratio.toFixed(1)}%</h3>
          <p className="text-sm font-medium text-emerald-400">{ratioLabel}</p>
        </motion.div>

        <motion.div
          whileHover={{ y: -4 }}
          className="relative overflow-hidden rounded-2xl border-2 border-sky-500/30 bg-gradient-to-br from-exiqo-dark/80 to-sky-500/10 p-6 shadow-xl"
        >
          <div className="mb-4 flex items-start justify-between">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-cyan-600 shadow-lg">
              <Calculator className="h-6 w-6 text-white" />
            </div>
          </div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-exiqo-glow/60">Max new EMI</p>
          <h3 className="mb-2 text-4xl font-bold tracking-tight text-white">{apiUtils.formatINR(maxNew)}</h3>
          <p className="text-sm font-medium text-sky-400">Available capacity (30% rule)</p>
        </motion.div>

        <motion.div
          whileHover={{ y: -4 }}
          className="relative overflow-hidden rounded-2xl border-2 border-exiqo-pink/30 bg-gradient-to-br from-exiqo-dark/80 to-exiqo-pink/10 p-6 shadow-xl"
        >
          <div className="mb-4 flex items-start justify-between">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-exiqo-pink to-rose-600 shadow-lg">
              <AlertCircle className="h-6 w-6 text-white" />
            </div>
          </div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-exiqo-glow/60">Active EMIs</p>
          <h3 className="mb-2 text-4xl font-bold tracking-tight text-white">{activeCount}</h3>
          <p className="text-sm font-medium text-exiqo-pink">
            {activeCount === 0 ? "No recurring EMI pattern detected" : "Detected in last 6 months"}
          </p>
        </motion.div>
      </div>

      {/* Health narrative */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className={`rounded-3xl border-2 bg-gradient-to-br p-8 shadow-xl ${ds.healthBg}`}
      >
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
          <div
            className={`flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br shadow-lg ${ds.healthIcon}`}
          >
            {dangerLevel === "SAFE" ? (
              <CheckCircle2 className="h-8 w-8 text-white" />
            ) : (
              <AlertTriangle className="h-8 w-8 text-white" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="mb-3 text-2xl font-bold text-white">{ds.title}</h3>
            <p className="mb-4 text-lg text-exiqo-glow/80">{state.data?.verdict}</p>
            <p className="leading-relaxed text-exiqo-glow/60">{state.data?.ai_advice}</p>
          </div>
        </div>
      </motion.div>

      {/* Calculator */}
      <motion.div
        id="emi-calculator"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="rounded-3xl border-2 border-exiqo-purple/30 bg-gradient-to-br from-exiqo-purple/10 via-exiqo-dark/50 to-exiqo-pink/10 p-8 shadow-xl"
      >
        <h3 className="mb-6 text-2xl font-bold text-white">Can I take one more EMI?</h3>

        <div className="grid gap-8 md:grid-cols-2">
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-semibold text-exiqo-glow/70">
                How much EMI are you considering?
              </label>
              <div className="relative">
                <IndianRupee className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-exiqo-purple" />
                <input
                  type="number"
                  min="0"
                  value={newEmi}
                  onChange={(e) => setNewEmi(e.target.value)}
                  placeholder="Enter EMI amount"
                  className="w-full rounded-xl border-2 border-exiqo-purple/40 bg-exiqo-dark/60 py-4 pl-12 pr-4 text-lg font-semibold text-white placeholder:text-exiqo-glow/40 focus:border-exiqo-purple focus:outline-none focus:ring-2 focus:ring-exiqo-purple"
                />
              </div>
            </div>
            {emiCheck ? (
              <p className="rounded-xl border border-exiqo-purple/25 bg-exiqo-dark/50 p-4 text-sm text-exiqo-glow/90">
                {emiCheck}
              </p>
            ) : null}
            <button
              type="button"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-exiqo-purple to-exiqo-pink py-4 text-sm font-semibold text-white transition hover:shadow-purple-glow"
            >
              Calculate impact
              <ArrowRight className="h-5 w-5" />
            </button>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border-2 border-exiqo-purple/30 bg-exiqo-dark/60 p-6">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-exiqo-glow/70">Total EMI burden</span>
                <span className="text-xl font-bold text-white">{apiUtils.formatINR(totalBurden)}</span>
              </div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-exiqo-glow/70">Max new EMI allowed</span>
                <span className="text-xl font-bold text-white">{apiUtils.formatINR(maxNew)}</span>
              </div>
              <div className="flex items-center justify-between border-t border-exiqo-purple/30 pt-4">
                <span className="flex items-center gap-2 text-sm font-semibold text-exiqo-glow/70">
                  <AlertCircle className="h-4 w-4" />
                  RBI safe limit
                </span>
                <span className="text-lg font-bold text-exiqo-purple">30%</span>
              </div>
            </div>
            <div className="rounded-xl border-2 border-sky-500/30 bg-sky-500/10 p-4">
              <p className="flex items-start gap-2 text-sm font-medium text-sky-300">
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                Keep your debt-to-income ratio below 30% for financial stability.
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* EMI list or empty */}
      {activeCount === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="py-12 text-center sm:py-16"
        >
          <div className="mb-6 inline-flex h-24 w-24 items-center justify-center rounded-3xl bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-xl shadow-emerald-500/20">
            <CheckCircle2 className="h-12 w-12 text-white" />
          </div>
          <h3 className="mb-3 text-2xl font-bold text-white">No EMIs detected</h3>
          <p className="mx-auto max-w-md text-exiqo-glow/60">
            Your finances look clean from recurring EMI signals in recent history.
          </p>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <h3 className="text-xl font-bold text-white">Detected EMIs</h3>
          <div className="grid gap-4 md:grid-cols-2">
            {emis.map((emi) => (
              <article
                key={emi.merchant}
                className="rounded-2xl border-2 border-exiqo-purple/25 bg-exiqo-dark/50 p-5 shadow-lg transition hover:border-exiqo-purple/45"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <h4 className="text-lg font-semibold text-white">
                    {emi.emi_type === "VEHICLE EMI" ? "🚗 " : "💳 "}
                    {emi.merchant}
                  </h4>
                  <span className="whitespace-nowrap rounded-lg bg-exiqo-purple/20 px-2 py-1 text-xs font-bold text-exiqo-glow">
                    {emi.emi_type}
                  </span>
                </div>
                <p className="text-sm text-exiqo-glow/80">
                  {apiUtils.formatINR(emi.amount)}
                  <span className="text-exiqo-glow/50"> / month</span>
                  <span className="text-exiqo-glow/50"> · Due ~{emi.payment_date}th</span>
                </p>
                <p className="mt-2 text-xs text-exiqo-glow/50">
                  {emi.months_detected} months streak · Last {emi.last_detected || "—"}
                </p>
              </article>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default EMITrapDetector;
