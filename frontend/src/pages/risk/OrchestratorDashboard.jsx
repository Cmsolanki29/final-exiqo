/**
 * OrchestratorDashboard — Phase 12 Multi-Model Orchestrator UI.
 *
 * Renders:
 *   1. Top stat row     — total spend vs daily cap, remaining, P9/P12 call counts
 *   2. By-model chart   — Recharts BarChart from /costs/today.by_model
 *   3. Tier routing     — visual scale of tier0..tier3 thresholds + a live preview
 *
 * Backend endpoints used:
 *   GET /api/risk/orchestrator/costs/today      (admin)
 *   GET /api/risk/orchestrator/route/preview    (admin, params: risk_score)
 *   GET /api/risk/orchestrator/health           (public — used for thresholds fallback)
 *
 * Auto-refreshes every 60s.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  GitMerge,
  RefreshCw,
  DollarSign,
  Wallet,
  Bot,
  Scale,
  AlertTriangle,
  TrendingUp,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  CartesianGrid,
} from "recharts";
import {
  getCostsToday,
  previewOrchestrationRoute,
  getOrchestratorHealth,
} from "../../services/riskApi";
import { SkeletonCard } from "../../components/common/SkeletonCard";
import { useToast } from "../../components/common/Toast";

const REFRESH_MS = 60_000;

function modelColor(name) {
  const m = (name || "").toLowerCase();
  if (m.includes("3.3-70b")) return "#a855f7"; // purple
  if (m.includes("3.1-70b")) return "#14b8a6"; // teal
  return "#ec4899"; // pink
}

function fmtUsd(n) {
  if (n == null || !Number.isFinite(Number(n))) return "$0.0000";
  return `$${Number(n).toFixed(4)}`;
}

// ── Top stat card ──────────────────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, sublabel, color = "#a78bfa" }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-sm"
    >
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-gray-600 font-semibold">
        {Icon && <Icon size={11} style={{ color }} />}
        {label}
      </div>
      <p className="text-2xl font-bold text-white mt-1.5">{value ?? "—"}</p>
      {sublabel && <p className="text-[11px] text-gray-600 mt-0.5">{sublabel}</p>}
    </motion.div>
  );
}

// ── Budget bar ─────────────────────────────────────────────────────────────
function BudgetBar({ spent, cap }) {
  const pct = cap > 0 ? Math.min(100, Math.max(0, (spent / cap) * 100)) : 0;
  const over80 = pct > 80;
  const color = over80 ? "#ef4444" : pct > 50 ? "#f59e0b" : "#22c55e";
  return (
    <div className="mt-3">
      <div className="flex items-center justify-between text-[11px] text-gray-500 mb-1">
        <span>{fmtUsd(spent)} spent</span>
        <span>{fmtUsd(cap)} cap</span>
      </div>
      <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6 }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
      {over80 && (
        <p className="text-[11px] text-red-300 mt-1 inline-flex items-center gap-1">
          <AlertTriangle size={11} /> Over 80% of daily cap
        </p>
      )}
    </div>
  );
}

// ── Local tier logic (client-side, instant) ────────────────────────────────
const ALL_MODELS = [
  { id: "xgboost",    label: "XGBoost",          color: "#22c55e" },
  { id: "anomaly",    label: "Anomaly Detection", color: "#eab308" },
  { id: "gnn",        label: "GNN",               color: "#0ea5e9" },
  { id: "llm",        label: "LLM Investigator",  color: "#a855f7" },
  { id: "dnn",        label: "DNN",               color: "#14b8a6" },
];

function getTier(score) {
  if (score < 30) return { tier: 0, label: "Tier 0 — XGBoost only",                costInr: "₹0.00",   costUsd: 0.000, active: ["xgboost"] };
  if (score < 55) return { tier: 1, label: "Tier 1 — XGBoost + Anomaly",           costInr: "₹0.001",  costUsd: 0.001, active: ["xgboost", "anomaly"] };
  if (score < 75) return { tier: 2, label: "Tier 2 — XGBoost + GNN",               costInr: "₹0.003",  costUsd: 0.003, active: ["xgboost", "anomaly", "gnn"] };
  if (score < 90) return { tier: 3, label: "Tier 3 — XGBoost + GNN + LLM",         costInr: "₹0.02",   costUsd: 0.020, active: ["xgboost", "anomaly", "gnn", "llm"] };
  return           { tier: 4, label: "Tier 4 — Full Stack",                         costInr: "₹0.05",   costUsd: 0.050, active: ["xgboost", "anomaly", "gnn", "llm", "dnn"] };
}

const FULL_COST_USD = 0.050;

function ModelChip({ model, active }) {
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-all duration-300"
      style={
        active
          ? { background: `${model.color}20`, borderColor: `${model.color}60`, color: model.color, opacity: 1 }
          : { background: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.25)", opacity: 0.7 }
      }
    >
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0 transition-all duration-300"
        style={{ background: active ? model.color : "rgba(255,255,255,0.15)" }}
      />
      {model.label}
    </div>
  );
}

function LiveTierDisplay({ score }) {
  const info = getTier(score);
  const savings = Math.max(0, FULL_COST_USD - info.costUsd);

  return (
    <div className="mt-4 space-y-3">
      {/* Tier label */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold text-white">
          {info.label}
        </span>
        <span className="text-[10px] bg-white/[0.06] border border-white/10 px-2 py-0.5 rounded-full text-gray-400">
          Tier {info.tier}
        </span>
      </div>

      {/* Model chips */}
      <div className="flex flex-wrap gap-2">
        {ALL_MODELS.map((m) => (
          <ModelChip key={m.id} model={m} active={info.active.includes(m.id)} />
        ))}
      </div>

      {/* Cost callout */}
      <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 text-[12px] leading-relaxed text-gray-400">
        At this risk level,{" "}
        <span className="text-white font-semibold">{info.active.length}</span> model
        {info.active.length !== 1 ? "s" : ""} activate.
        Estimated cost:{" "}
        <span className="text-emerald-300 font-semibold">
          {info.costInr}
        </span>{" "}
        per transaction.{" "}
        {savings > 0 && (
          <>
            Cost optimisation saves{" "}
            <span className="text-purple-300 font-semibold">
              ₹{savings.toFixed(3)}
            </span>{" "}
            vs running all 5 models on every transaction.
          </>
        )}
      </div>
    </div>
  );
}

// ── Tier routing strip ─────────────────────────────────────────────────────
function TierStrip({ thresholds, previewScore, previewTier }) {
  const t = thresholds || {};
  const stops = [
    { name: "Tier 0", max: t.tier0_max ?? 30, color: "#22c55e", desc: "Auto-allow" },
    { name: "Tier 1", max: t.tier1_max ?? 60, color: "#eab308", desc: "Auto-allow + log" },
    { name: "Tier 2", max: t.tier2_max ?? 75, color: "#f59e0b", desc: "Flag for review" },
    { name: "Tier 3", max: t.tier3_max ?? 85, color: "#ef4444", desc: "Investigate (LLM)" },
    { name: "Tier 4", max: 100,                color: "#7f1d1d", desc: "Block" },
  ];
  let last = 0;
  const segments = stops.map((s) => {
    const from = last;
    last = s.max;
    return { ...s, from, to: s.max, width: ((s.max - from) / 100) * 100 };
  });

  return (
    <div className="mt-3">
      {/* Bar */}
      <div className="relative h-6 w-full rounded-lg overflow-hidden flex">
        {segments.map((s) => (
          <div
            key={s.name}
            title={`${s.name} · ${s.from}-${s.to} · ${s.desc}`}
            style={{ width: `${s.width}%`, background: `${s.color}33`, borderRight: "1px solid rgba(255,255,255,0.05)" }}
            className="relative flex items-center justify-center text-[10px] font-semibold"
          >
            <span style={{ color: s.color }}>{s.name}</span>
          </div>
        ))}
        {Number.isFinite(previewScore) && (
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.7)]"
            style={{ left: `${Math.min(100, Math.max(0, previewScore))}%` }}
          />
        )}
      </div>

      {/* Scale */}
      <div className="flex justify-between text-[10px] text-gray-600 mt-1 px-0.5">
        {[0, 25, 50, 75, 100].map((v) => (
          <span key={v}>{v}</span>
        ))}
      </div>

      {/* Preview row */}
      {Number.isFinite(previewScore) && (
        <p className="text-[11px] text-gray-400 mt-2">
          Score{" "}
          <span className="text-white font-semibold">{previewScore}</span> →{" "}
          <span className="text-purple-300 font-semibold">{previewTier || "—"}</span>
        </p>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
const OrchestratorDashboard = () => {
  const { showToast } = useToast();
  const [costs, setCosts] = useState(null);
  const [health, setHealth] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewScore, setPreviewScore] = useState(50);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastError, setLastError] = useState(null);

  // Keep latest previewScore in a ref so fetchAll doesn't need it
  // in its deps — prevents the polling interval from being torn down
  // and re-created every time the slider moves.
  const previewScoreRef = useRef(previewScore);
  useEffect(() => {
    previewScoreRef.current = previewScore;
  }, [previewScore]);

  // Separate lightweight fetch just for the route-preview call; fires
  // with a short debounce while the slider is being dragged.
  const debounceRef = useRef(null);
  const fetchPreview = useCallback((score) => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const p = await previewOrchestrationRoute({ risk_score: score });
        setPreview(p);
      } catch {
        // non-critical — ignore
      }
    }, 200);
  }, []);

  const fetchAll = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    setLastError(null);
    const [c, h, p] = await Promise.allSettled([
      getCostsToday(),
      getOrchestratorHealth(),
      previewOrchestrationRoute({ risk_score: previewScoreRef.current }),
    ]);
    if (c.status === "fulfilled") setCosts(c.value);
    else setLastError(c.reason?.message || "costs unavailable");
    if (h.status === "fulfilled") setHealth(h.value);
    if (p.status === "fulfilled") setPreview(p.value);
    setLoading(false);
    setRefreshing(false);
  }, []); // no previewScore dep — uses ref instead

  useEffect(() => {
    fetchAll(false);
    const id = setInterval(() => fetchAll(false), REFRESH_MS);
    return () => clearInterval(id);
  }, [fetchAll]);

  const chartData = useMemo(() => {
    const rows = costs?.by_model || [];
    return rows.map((r) => ({
      model: r.model || "unknown",
      cost: Number(r.cost_usd || 0),
      requests: Number(r.requests || 0),
    }));
  }, [costs]);

  const totalSpend = Number(costs?.total_cost_usd || 0);
  const cap = Number(costs?.daily_cap_usd || 0);
  const remaining = Number(costs?.remaining_usd || Math.max(cap - totalSpend, 0));

  const handleRefresh = () => {
    fetchAll(true);
    showToast("Refreshing orchestrator metrics…", "info");
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between gap-4 flex-wrap"
      >
        <div>
          <div className="flex items-center gap-2">
            <GitMerge size={20} className="text-pink-400" />
            <h2 className="text-2xl font-bold text-white">Orchestrator</h2>
            <span className="text-[10px] font-bold bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded uppercase tracking-wider">
              Phase 12 · 2026
            </span>
          </div>
          <p className="text-gray-400 text-sm mt-1">
            Daily LLM spend, tier routing thresholds, and judge-call breakdown.
          </p>
        </div>

        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-white/10 bg-white/[0.03] text-gray-300 hover:bg-white/[0.07] transition disabled:opacity-50"
        >
          <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </motion.div>

      {/* Stat row */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonCard key={i} lines={2} height={92} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-sm">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-gray-600 font-semibold">
              <DollarSign size={11} className="text-emerald-300" /> Today spend
            </div>
            <p className="text-2xl font-bold text-white mt-1.5">{fmtUsd(totalSpend)}</p>
            <BudgetBar spent={totalSpend} cap={cap} />
          </div>
          <StatCard
            icon={Wallet}
            label="Remaining"
            value={fmtUsd(remaining)}
            sublabel={`of ${fmtUsd(cap)} daily cap`}
            color="#22c55e"
          />
          <StatCard
            icon={Bot}
            label="Phase 9 invocations"
            value={costs?.phase_9_investigations ?? 0}
            sublabel="LLM investigations today"
            color="#a855f7"
          />
          <StatCard
            icon={Scale}
            label="Phase 12 judge calls"
            value={costs?.phase_12_judge_calls ?? 0}
            sublabel="LLM-as-judge invocations"
            color="#ec4899"
          />
        </div>
      )}

      {/* By-model chart */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp size={16} className="text-purple-300" />
            <h3 className="text-sm font-semibold text-white">Spend by model · today</h3>
          </div>
          {costs?.note && (
            <span className="text-[10px] text-amber-300 inline-flex items-center gap-1">
              <AlertTriangle size={10} /> {costs.note}
            </span>
          )}
        </div>

        {chartData.length === 0 ? (
          <div className="py-10 text-center text-sm text-gray-600">
            No LLM calls recorded today. Trigger an investigation or judge replay to see data here.
          </div>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 16, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="model" tick={{ fontSize: 11, fill: "rgba(255,255,255,0.5)" }} />
                <YAxis tick={{ fontSize: 11, fill: "rgba(255,255,255,0.5)" }} tickFormatter={(v) => `$${v.toFixed(3)}`} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(15,15,30,0.95)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 8,
                    fontSize: 12,
                    color: "white",
                  }}
                  formatter={(v, name) => (name === "cost" ? fmtUsd(v) : v)}
                />
                <Bar dataKey="cost" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={`c${i}`} fill={modelColor(entry.model)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </motion.div>

      {/* Tier routing */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm"
      >
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Scale size={16} className="text-pink-300" />
            <h3 className="text-sm font-semibold text-white">Tier routing thresholds</h3>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-[11px] text-gray-500 uppercase tracking-wider">
              Preview score
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={previewScore}
              onChange={(e) => {
              const v = Number(e.target.value);
              setPreviewScore(v);
              fetchPreview(v);
            }}
              className="accent-purple-500"
            />
            <span className="text-sm text-white font-mono w-8 text-right">{previewScore}</span>
          </div>
        </div>

        <TierStrip
          thresholds={health?.thresholds}
          previewScore={previewScore}
          previewTier={preview?.tier_label || preview?.tier_name || preview?.tier}
        />

        <LiveTierDisplay score={previewScore} />

        {lastError && (
          <p className="text-[11px] text-amber-300 mt-3 inline-flex items-center gap-1">
            <AlertTriangle size={11} /> {lastError}
          </p>
        )}
      </motion.div>
    </div>
  );
};

export default OrchestratorDashboard;
