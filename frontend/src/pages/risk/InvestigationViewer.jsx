/**
 * InvestigationViewer — Phase 9 LLM Investigation Agent UI.
 *
 * Lists recent review-queue transactions, lets an admin view the most-recent
 * investigation per transaction, manually trigger a fresh investigation, and
 * read the agent's reasoning + recommended action.
 *
 * Backend endpoints used (via riskApi.js):
 *   GET  /api/risk/investigations/{txn_id}        getInvestigation()
 *   POST /api/risk/investigations/{txn_id}/run    triggerInvestigation()
 *   GET  /api/risk/review-queue                   getEnrichedReviewQueue()
 *
 * Graceful behaviour:
 *   - When the review queue is empty/unreachable we fall back to a small set
 *     of demo transactions so the page never looks broken in dev.
 *   - 404 from getInvestigation is treated as "no investigation yet" and
 *     surfaces a primary CTA to run one.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  ChevronDown,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Play,
  RefreshCw,
  Clock,
  DollarSign,
  Sparkles,
} from "lucide-react";
import {
  getEnrichedReviewQueue,
  getInvestigation,
  triggerInvestigation,
} from "../../services/riskApi";
import { SkeletonCard } from "../../components/common/SkeletonCard";
import { useToast } from "../../components/common/Toast";
import { fmtCurrency, fmtRelativeTime } from "../../utils/risk/formatters";

// ── Demo fallback so dev experience is never empty ────────────────────────
const DEMO_QUEUE = [
  { id: 9981, transaction_id: 9981, merchant: "Unknown Vendor",        amount: 4999,  risk_score: 82, created_at: new Date(Date.now() -  90_000) },
  { id: 9974, transaction_id: 9974, merchant: "Intl Marketplace",      amount: 12500, risk_score: 71, created_at: new Date(Date.now() - 5_400_000) },
  { id: 9968, transaction_id: 9968, merchant: "Lottery Winner Co.",    amount: 1,     risk_score: 58, created_at: new Date(Date.now() - 14_400_000) },
  { id: 9952, transaction_id: 9952, merchant: "Amazon",                amount: 1299,  risk_score: 22, created_at: new Date(Date.now() - 86_400_000) },
];

// ── Visual helpers ─────────────────────────────────────────────────────────
function riskColor(score) {
  if (score == null) return { fg: "#94a3b8", bg: "rgba(148,163,184,0.15)", label: "Unknown" };
  if (score < 40)    return { fg: "#22c55e", bg: "rgba(34,197,94,0.15)",   label: "Low" };
  if (score < 70)    return { fg: "#f59e0b", bg: "rgba(245,158,11,0.15)",  label: "Medium" };
  return                 { fg: "#ef4444", bg: "rgba(239,68,68,0.15)",   label: "High" };
}

const ACTION_META = {
  ALLOW:        { icon: CheckCircle2,  fg: "#22c55e", bg: "rgba(34,197,94,0.12)",  border: "rgba(34,197,94,0.30)" },
  FLAG:         { icon: AlertTriangle, fg: "#f59e0b", bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.30)" },
  INVESTIGATE:  { icon: Sparkles,      fg: "#a855f7", bg: "rgba(168,85,247,0.12)", border: "rgba(168,85,247,0.30)" },
  BLOCK:        { icon: XCircle,       fg: "#ef4444", bg: "rgba(239,68,68,0.12)",  border: "rgba(239,68,68,0.30)" },
};

function ActionPill({ action }) {
  const key = (action || "").toUpperCase();
  const meta = ACTION_META[key] || ACTION_META.FLAG;
  const Icon = meta.icon;
  return (
    <span
      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border"
      style={{ color: meta.fg, background: meta.bg, borderColor: meta.border }}
    >
      <Icon size={12} />
      {key || "FLAG"}
    </span>
  );
}

function RiskScoreBadge({ score }) {
  const c = riskColor(score);
  return (
    <span
      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold"
      style={{ color: c.fg, background: c.bg }}
      title={`${c.label} risk`}
    >
      {Number.isFinite(score) ? Math.round(score) : "—"}
    </span>
  );
}

// ── Investigation detail card ──────────────────────────────────────────────
function InvestigationCard({ txn, investigation, busy, onRun, error }) {
  const [reasonExpanded, setReasonExpanded] = useState(true);
  const has = !!investigation;
  const action = investigation?.recommended_action;
  const reasoning =
    investigation?.reasoning ||
    investigation?.agent_reasoning ||
    investigation?.summary ||
    "";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm p-5"
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
              Transaction
            </span>
            <span className="font-mono text-sm text-white">#{txn.transaction_id ?? txn.id}</span>
            <RiskScoreBadge score={txn.risk_score} />
          </div>
          <h3 className="text-base font-semibold text-white mt-1 truncate">
            {txn.merchant || "Unknown merchant"}
          </h3>
          <p className="text-sm text-gray-400">
            {fmtCurrency(txn.amount)}
            {txn.created_at && (
              <span className="text-gray-600"> · {fmtRelativeTime(txn.created_at)}</span>
            )}
          </p>
        </div>

        <button
          type="button"
          onClick={() => onRun(txn)}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-purple-500/30 bg-purple-500/10 text-purple-200 hover:bg-purple-500/20 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          {busy ? "Investigating…" : has ? "Re-run Investigation" : "Run Investigation"}
        </button>
      </div>

      {/* Body */}
      {error && !has ? (
        <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-200">
          <div className="flex items-center gap-2 font-semibold mb-1">
            <AlertTriangle size={14} />
            No investigation yet
          </div>
          <p className="text-amber-200/70 text-xs">
            Click <span className="font-semibold">Run Investigation</span> to ask the LLM agent
            to analyse this transaction. The agent will use velocity, merchant history, and
            network signals to recommend an action.
          </p>
        </div>
      ) : has ? (
        <div className="mt-4 space-y-4">
          {/* Recommended action */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                Recommended action
              </p>
              <div className="mt-1">
                <ActionPill action={action} />
              </div>
            </div>
            {Number.isFinite(investigation.cost_usd) && (
              <div className="text-right">
                <p className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                  Cost
                </p>
                <p className="inline-flex items-center gap-1 text-sm text-white">
                  <DollarSign size={12} className="text-exiqo-glow/40" />
                  {Number(investigation.cost_usd).toFixed(4)}
                </p>
              </div>
            )}
          </div>

          {/* Reasoning (collapsible) */}
          {reasoning && (
            <div className="rounded-xl border border-white/10 bg-black/20">
              <button
                type="button"
                onClick={() => setReasonExpanded((v) => !v)}
                className="w-full flex items-center justify-between gap-2 px-4 py-2.5 text-left"
              >
                <span className="text-xs uppercase tracking-wider text-gray-400 font-semibold">
                  Agent reasoning
                </span>
                <motion.span animate={{ rotate: reasonExpanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
                  <ChevronDown size={14} className="text-exiqo-glow/40" />
                </motion.span>
              </button>
              <AnimatePresence initial={false}>
                {reasonExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="px-4 pb-4 pt-1 text-sm text-gray-300 whitespace-pre-wrap leading-relaxed font-mono">
                      {reasoning}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          {/* Meta footer */}
          <div className="flex items-center gap-4 flex-wrap text-[11px] text-gray-500">
            {investigation.model_used && (
              <span className="inline-flex items-center gap-1">
                <Bot size={11} /> {investigation.model_used}
              </span>
            )}
            {investigation.triggered_by && (
              <span className="inline-flex items-center gap-1">
                <Sparkles size={11} /> triggered by {investigation.triggered_by}
              </span>
            )}
            {investigation.completed_at && (
              <span className="inline-flex items-center gap-1">
                <Clock size={11} /> {fmtRelativeTime(investigation.completed_at)}
              </span>
            )}
            {Number.isFinite(investigation.tool_rounds) && (
              <span>tool rounds: {investigation.tool_rounds}</span>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-4">
          <SkeletonCard lines={3} height={80} />
        </div>
      )}
    </motion.div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
const InvestigationViewer = ({ userId }) => {
  const { showToast } = useToast();

  const [queue, setQueue] = useState([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState(false);

  // map<txn_id, { loading, data, error }>
  const [invMap, setInvMap] = useState({});
  // map<txn_id, true> for the run button
  const [busyMap, setBusyMap] = useState({});

  const loadQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError(false);
    try {
      const rows = await getEnrichedReviewQueue("pending", 20);
      const items = Array.isArray(rows) ? rows : rows?.items ?? [];
      if (items.length === 0) throw new Error("empty");
      setQueue(items);
    } catch {
      setQueue(DEMO_QUEUE);
      setQueueError(true);
    } finally {
      setQueueLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  // Auto-fetch the most-recent investigation for every txn in parallel.
  // We use Promise.allSettled so a single 404 never blocks the rest.
  useEffect(() => {
    if (!queue.length) return;
    let cancelled = false;

    const ids = queue
      .map((t) => t.transaction_id ?? t.id)
      .filter((id) => !!id);

    // Optimistically set every unseen id to "loading".
    setInvMap((m) => {
      const patch = {};
      for (const id of ids) {
        if (!m[id]) patch[id] = { loading: true, data: null, error: null };
      }
      return Object.keys(patch).length ? { ...m, ...patch } : m;
    });

    Promise.allSettled(ids.map((id) => getInvestigation(id))).then((results) => {
      if (cancelled) return;
      setInvMap((m) => {
        const next = { ...m };
        ids.forEach((id, i) => {
          const r = results[i];
          if (r.status === "fulfilled") {
            next[id] = { loading: false, data: r.value, error: null };
          } else {
            const status = r.reason?.response?.status;
            next[id] = {
              loading: false,
              data: null,
              error: status === 404 ? "not_found" : r.reason?.message || "error",
            };
          }
        });
        return next;
      });
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queue]);

  const handleRun = useCallback(
    async (txn) => {
      const id = txn.transaction_id ?? txn.id;
      if (!id) return;
      setBusyMap((m) => ({ ...m, [id]: true }));
      try {
        const data = await triggerInvestigation(id, userId ?? null, "manual");
        setInvMap((m) => ({ ...m, [id]: { loading: false, data, error: null } }));
        showToast(`Investigation complete · ${data?.recommended_action || "OK"}`, "success");
      } catch (err) {
        const msg = err?.response?.data?.detail || err?.message || "Investigation failed";
        showToast(msg, "error");
        setInvMap((m) => ({
          ...m,
          [id]: { loading: false, data: m[id]?.data ?? null, error: msg },
        }));
      } finally {
        setBusyMap((m) => ({ ...m, [id]: false }));
      }
    },
    [userId, showToast]
  );

  const totalInvestigations = useMemo(
    () => Object.values(invMap).filter((s) => !!s.data).length,
    [invMap]
  );

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between gap-4 flex-wrap"
      >
        <div>
          <div className="flex items-center gap-2">
            <Bot size={20} className="text-purple-400" />
            <h2 className="text-2xl font-bold text-white">Investigations</h2>
            <span className="text-[10px] font-bold bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded uppercase tracking-wider">
              Phase 9 · 2026
            </span>
          </div>
          <p className="text-gray-400 text-sm mt-1">
            LLM agent reads each high-risk transaction, runs tool calls, and recommends an action.
          </p>
        </div>

        <button
          type="button"
          onClick={loadQueue}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-white/10 bg-white/[0.03] text-gray-300 hover:bg-white/[0.07] transition"
        >
          <RefreshCw size={12} />
          Refresh queue
        </button>
      </motion.div>

      {/* Stat strip */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
            In review queue
          </p>
          <p className="text-2xl font-bold text-white mt-1">{queue.length}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
            Investigations loaded
          </p>
          <p className="text-2xl font-bold text-purple-300 mt-1">{totalInvestigations}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
            Data source
          </p>
          <p className="text-sm font-semibold mt-1.5">
            {queueError ? (
              <span className="text-amber-300">Demo fallback</span>
            ) : (
              <span className="text-emerald-300">Live backend</span>
            )}
          </p>
        </div>
      </div>

      {/* List */}
      {queueLoading ? (
        <div className="space-y-3">
          <SkeletonCard lines={3} height={120} />
          <SkeletonCard lines={3} height={120} />
        </div>
      ) : queue.length === 0 ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 text-center text-gray-400">
          Review queue is empty. New high-risk transactions will appear here automatically.
        </div>
      ) : (
        <div className="space-y-3">
          {queue.map((txn) => {
            const id = txn.transaction_id ?? txn.id;
            const state = invMap[id] || { loading: true, data: null, error: null };
            return (
              <InvestigationCard
                key={id}
                txn={txn}
                investigation={state.data}
                busy={!!busyMap[id]}
                onRun={handleRun}
                error={state.error}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export default InvestigationViewer;
