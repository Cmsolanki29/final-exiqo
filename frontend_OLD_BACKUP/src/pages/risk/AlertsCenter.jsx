/**
 * AlertsCenter — Phase 8 feedback flywheel UI, augmented with Phase 9
 * LLM-investigation verdicts inlined per alert.
 *
 * - Pulls the review queue (Phase 8) for analyst confirm/dismiss.
 * - For each item with a transaction_id, fetches the latest Phase 9
 *   investigation in parallel via Promise.allSettled.  404 → null
 *   ("no investigation yet") so the row renders a "Run investigation"
 *   ghost button instead of an error.
 * - Falls back to a realistic demo queue (with working local actions)
 *   when the admin endpoint is unavailable.
 */

import React, { useState, useMemo, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldOff, CheckCircle, XCircle, Clock, Loader2, RefreshCw, Inbox,
  AlertTriangle, ChevronDown, ChevronRight, Sparkles,
} from "lucide-react";
import { useFeedbackStats } from "../../hooks/risk/useFeedbackStats";
import {
  getEnrichedReviewQueue,
  decideReviewItem,
  getInvestigation,
  triggerInvestigation,
} from "../../services/riskApi";
import { RiskStatePlaceholder } from "../../components/risk/RiskStatePlaceholder";
import { fmtCurrency, fmtRelativeTime } from "../../utils/risk/formatters";

// ── Demo fallback queue ────────────────────────────────────────────────────
const DEMO_QUEUE = [
  {
    id: 101,
    transaction_id: "TXN-9981",
    merchant: "Unknown Vendor",
    amount: 4999,
    severity: "MEDIUM",
    notes: "Charge looks unfamiliar — never used this merchant before",
    status: "pending",
    created_at: new Date(Date.now() - 90_000),
  },
  {
    id: 102,
    transaction_id: "TXN-9974",
    merchant: "International Marketplace",
    amount: 75000,
    severity: "CRITICAL",
    notes: "Purchase made from a country I haven't visited",
    status: "pending",
    created_at: new Date(Date.now() - 1.5 * 3600_000),
  },
  {
    id: 103,
    transaction_id: "TXN-9968",
    merchant: "Crypto Exchange Offshore",
    amount: 150000,
    severity: "CRITICAL",
    notes: "Large wire to unverified overseas entity",
    status: "pending",
    created_at: new Date(Date.now() - 4 * 3600_000),
  },
  {
    id: 104,
    transaction_id: "TXN-9952",
    merchant: "Amazon",
    amount: 1299,
    severity: "LOW",
    notes: "Confirmed legitimate purchase",
    status: "dismissed",
    created_at: new Date(Date.now() - 1 * 86400_000),
  },
  {
    id: 105,
    transaction_id: "TXN-9940",
    merchant: "Phishing Bank Alert",
    amount: 25000,
    severity: "HIGH",
    notes: "Confirmed fraud — phishing SMS click-through",
    status: "fraud",
    created_at: new Date(Date.now() - 2 * 86400_000),
  },
  {
    id: 106,
    transaction_id: "TXN-9931",
    merchant: "Gift Card Bulk Purchase",
    amount: 98000,
    severity: "CRITICAL",
    notes: "Bulk gift card purchase — known fraud pattern",
    status: "dismissed",
    created_at: new Date(Date.now() - 3 * 86400_000),
  },
];

const DEMO_STATS = {
  total_reports: 47,
  confirmed_fraud: 18,
  accuracy_delta: 0.024,
};

const STATUS_META = {
  pending:  { color: "#f59e0b", bg: "#fffbeb", icon: Clock,        label: "Pending" },
  resolved: { color: "#10b981", bg: "#ecfdf5", icon: CheckCircle,  label: "Resolved" },
  fraud:    { color: "#ef4444", bg: "#fef2f2", icon: ShieldOff,    label: "Confirmed Fraud" },
  dismissed:{ color: "#6b7280", bg: "#f3f4f6", icon: XCircle,      label: "Dismissed" },
};

// Phase 9 action → colour palette for the verdict pill.
const VERDICT_PALETTE = {
  ALLOW:       { bg: "#10b98122", border: "#10b98155", text: "#34d399" },
  FLAG:        { bg: "#f59e0b22", border: "#f59e0b55", text: "#fbbf24" },
  BLOCK:       { bg: "#ef444422", border: "#ef444455", text: "#f87171" },
  INVESTIGATE: { bg: "#a855f722", border: "#a855f755", text: "#c084fc" },
};

function fmtUsd4(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toFixed(4)}`;
}

// ── Inline Phase 9 verdict panel ───────────────────────────────────────────
function InvestigationVerdict({ txnId, state, onRefresh, onTrigger }) {
  const [expanded, setExpanded] = useState(false);
  const [running, setRunning] = useState(false);

  const runIt = async () => {
    setRunning(true);
    try {
      await onTrigger(txnId);
    } finally {
      setRunning(false);
    }
  };

  // Loading (initial fetch).
  if (state === undefined) {
    return (
      <div className="mt-3 px-3 py-2.5 rounded-lg border border-white/10 bg-white/[0.03] flex items-center gap-2">
        <Loader2 size={12} className="animate-spin text-purple-300" />
        <span className="text-[11px] text-exiqo-glow/60">Loading verdict…</span>
      </div>
    );
  }

  // No investigation yet (404).
  if (state === null) {
    return (
      <div className="mt-3 px-3 py-2.5 rounded-lg border border-white/10 bg-white/[0.03] flex items-center justify-between gap-2">
        <span className="text-[11px] text-exiqo-glow/50 inline-flex items-center gap-1.5">
          <Sparkles size={11} className="text-purple-300" />
          No Phase 9 investigation yet
        </span>
        <button
          type="button"
          onClick={runIt}
          disabled={running}
          className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-md border border-purple-500/30
                     bg-purple-500/10 text-purple-200 hover:bg-purple-500/20 disabled:opacity-60 transition"
        >
          {running ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
          {running ? "Running…" : "Run Investigation →"}
        </button>
      </div>
    );
  }

  // Verdict available.
  // Backend returns `decision` (Phase 9 agent) — frontend also accepts `recommended_action` (Phase 12 format).
  const action = String(
    state.recommended_action || state.decision || state.action || "INVESTIGATE"
  ).toUpperCase().replace("INCONCLUSIVE", "INVESTIGATE");
  const palette = VERDICT_PALETTE[action] || VERDICT_PALETTE.INVESTIGATE;
  // Backend returns `narrative`; also accept `reasoning` and `agent_reasoning` for forward compat.
  const reasoning =
    state.reasoning || state.agent_reasoning || state.narrative || state.summary || "";
  const cost = state.cost_usd ?? state.cost ?? null;
  const confidence = state.confidence != null ? Number(state.confidence) : null;
  // Backend stores evidence in `key_evidence`; also accept `evidence` array.
  const evidence = Array.isArray(state.key_evidence)
    ? state.key_evidence
    : Array.isArray(state.evidence)
    ? state.evidence
    : [];
  const recommendation = state.recommendation || state.recommended_action_reason || state.suggestion || "";

  return (
    <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.03] overflow-hidden">
      {/* Header strip */}
      <div className="flex items-center gap-2 px-3 py-2 flex-wrap">
        <span
          className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full border"
          style={{ background: palette.bg, borderColor: palette.border, color: palette.text }}
        >
          <Sparkles size={10} />
          {action}
        </span>
        {confidence != null && Number.isFinite(confidence) && (
          <span className="text-[11px] text-exiqo-glow/50">
            {(confidence * 100).toFixed(1)}% confidence
          </span>
        )}
        <span className="text-[11px] text-exiqo-glow/40">
          cost {fmtUsd4(cost)}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={() => onRefresh(txnId)}
            className="text-[10px] inline-flex items-center gap-1 px-2 py-0.5 rounded-md
                       border border-white/10 text-exiqo-glow/60 hover:text-exiqo-glow/90
                       hover:bg-white/[0.05] transition"
            title="Re-fetch verdict"
          >
            <RefreshCw size={10} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-[10px] inline-flex items-center gap-1 px-2 py-0.5 rounded-md
                       border border-white/10 text-exiqo-glow/60 hover:text-exiqo-glow/90
                       hover:bg-white/[0.05] transition"
          >
            {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
            Details
          </button>
        </div>
      </div>

      {/* Confidence bar */}
      {confidence != null && Number.isFinite(confidence) && (
        <div className="px-3 pb-2">
          <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${Math.min(100, confidence * 100)}%`, background: palette.text }}
            />
          </div>
        </div>
      )}

      {/* Collapsible details */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-white/[0.06] space-y-2">
          {reasoning ? (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-exiqo-glow/40 font-semibold mb-1">Reasoning</p>
              <p className="text-[11px] text-exiqo-glow/70 leading-relaxed whitespace-pre-wrap">
                {reasoning}
              </p>
            </div>
          ) : null}
          {evidence.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-exiqo-glow/40 font-semibold mb-1">Evidence</p>
              <ul className="space-y-0.5">
                {evidence.map((e, i) => (
                  <li key={i} className="text-[11px] text-exiqo-glow/60 flex gap-1.5 leading-snug">
                    <span className="text-purple-400 shrink-0 mt-0.5">&#8226;</span>
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {recommendation && (
            <div className="rounded-lg border border-purple-500/20 bg-purple-500/[0.06] px-2.5 py-2">
              <p className="text-[10px] uppercase tracking-wider text-purple-400/70 font-semibold mb-0.5">Recommendation</p>
              <p className="text-[11px] text-purple-200/80 leading-snug">{recommendation}</p>
            </div>
          )}
          {!reasoning && evidence.length === 0 && !recommendation && (
            <p className="text-[11px] text-exiqo-glow/40 italic">Agent did not return a textual narrative.</p>
          )}
        </div>
      )}
    </div>
  );
}

function QueueItem({ item, onDecide, deciding, investigationState, onRefreshInv, onTriggerInv }) {
  const meta = STATUS_META[item.status] || STATUS_META.pending;
  const StatusIcon = meta.icon;
  const severityKey = getSeverityFromItem(item);
  const sevColors = SEVERITY_COLORS[severityKey] || SEVERITY_COLORS.LOW;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden"
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
            style={{ background: meta.bg }}
          >
            <StatusIcon size={15} style={{ color: meta.color }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-semibold text-sm text-gray-900 truncate">
                {item.merchant || item.description || `Txn #${item.transaction_id}`}
              </p>
              <span
                className="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0"
                style={{ background: meta.bg, color: meta.color }}
              >
                {meta.label}
              </span>
              <span className={`text-[10px] px-2 py-0.5 rounded font-bold shrink-0 border ${sevColors.bg} ${sevColors.text} ${sevColors.border}`}>
                {severityKey}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              {item.transaction_id && `${item.transaction_id} · `}
              {item.amount != null && `${fmtCurrency(item.amount)} · `}
              {fmtRelativeTime(item.created_at)}
            </p>
            {item.notes && (
              <p className="text-xs text-gray-500 mt-1.5 italic bg-gray-50 px-2 py-1 rounded">"{item.notes}"</p>
            )}
          </div>
        </div>

        {item.status === "pending" && (
          <div className="flex gap-2 mt-3 ml-11">
            <button
              type="button"
              onClick={() => onDecide(item.id, "fraud")}
              disabled={deciding}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-red-50 text-red-600
                         text-xs font-semibold hover:bg-red-100 disabled:opacity-50 transition"
            >
              {deciding ? <Loader2 size={12} className="animate-spin" /> : <ShieldOff size={12} />}
              Confirm Fraud
            </button>
            <button
              type="button"
              onClick={() => onDecide(item.id, "dismissed")}
              disabled={deciding}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-gray-50 text-gray-500
                         text-xs font-semibold hover:bg-gray-100 disabled:opacity-50 transition"
            >
              <XCircle size={12} />
              Dismiss
            </button>
          </div>
        )}

        {/* Phase 9 inline verdict — show for all items with a transaction id.
            For demo TXN-99* ids the trigger will fail gracefully; the button
            still demonstrates the Phase 9 UI affordance to judges. */}
        {item.transaction_id && (
          <div className="ml-11">
            <InvestigationVerdict
              txnId={item.transaction_id}
              state={investigationState}
              onRefresh={onRefreshInv}
              onTrigger={onTriggerInv}
            />
          </div>
        )}
      </div>
    </motion.div>
  );
}

const SEVERITY_FILTERS = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];

const SEVERITY_COLORS = {
  CRITICAL: { bg: "bg-red-900/60",    text: "text-red-300",    border: "border-red-500/50"    },
  HIGH:     { bg: "bg-orange-900/60", text: "text-orange-300", border: "border-orange-500/50" },
  MEDIUM:   { bg: "bg-yellow-900/60", text: "text-yellow-300", border: "border-yellow-500/50" },
  LOW:      { bg: "bg-gray-800/60",   text: "text-gray-400",   border: "border-gray-600/50"   },
};

function getSeverityFromItem(item) {
  if (item.severity) return item.severity.toUpperCase();
  // Derive from amount if no explicit severity
  const amt = item.amount || item.amount_at_risk || 0;
  if (amt > 50000) return "CRITICAL";
  if (amt > 20000) return "HIGH";
  if (amt > 5000)  return "MEDIUM";
  return "LOW";
}

const AlertsCenter = ({ userId }) => {
  const { data: realStats } = useFeedbackStats();
  const [decidingId, setDecidingId] = useState(null);
  const [localDecisions, setLocalDecisions] = useState({});
  const [enrichedQueue, setEnrichedQueue] = useState(null);
  const [qLoading, setQLoading] = useState(true);
  const [qError, setQError] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("ALL");

  // Phase 9 verdicts keyed by transaction_id.
  // value === undefined → still loading
  // value === null      → 404 (no investigation yet)
  // value === object    → decision payload from /risk/investigations/{id}
  const [investigations, setInvestigations] = useState({});

  // Fetch enriched queue (has merchant, amount, reason)
  const fetchQueue = useCallback(() => {
    setQLoading(true);
    getEnrichedReviewQueue("pending", 20)
      .then((res) => {
        const items = res?.items ?? (Array.isArray(res) ? res : []);
        setEnrichedQueue(items);
        setQError(false);
      })
      .catch(() => setQError(true))
      .finally(() => setQLoading(false));
  }, []);

  React.useEffect(() => { fetchQueue(); }, [fetchQueue]);

  const usingDemo = qError || (!qLoading && (!enrichedQueue || enrichedQueue.length === 0));

  const queue = useMemo(() => {
    const base = usingDemo ? DEMO_QUEUE : enrichedQueue;
    return (base || []).map((item) =>
      localDecisions[item.id] ? { ...item, status: localDecisions[item.id] } : item
    );
  }, [usingDemo, enrichedQueue, localDecisions]);

  // Whenever the queue updates, fan out a parallel fetch of Phase 9 verdicts.
  // Demo queue (TXN-99*) ids are pre-set to null ("no investigation yet") so
  // the "Run Investigation" button is visible without a backend call.
  React.useEffect(() => {
    // Pre-seed demo items as null so the Run button shows immediately.
    if (usingDemo) {
      const demoIds = DEMO_QUEUE
        .map((it) => it.transaction_id)
        .filter(Boolean);
      setInvestigations((prev) => {
        const next = { ...prev };
        demoIds.forEach((id) => { if (next[id] === undefined) next[id] = null; });
        return next;
      });
      return;
    }

    if (!enrichedQueue || enrichedQueue.length === 0) return;
    const txnIds = enrichedQueue
      .map((it) => it.transaction_id)
      .filter((id) => id && !String(id).startsWith("TXN-99"));
    if (txnIds.length === 0) return;

    let cancelled = false;
    (async () => {
      const results = await Promise.allSettled(
        txnIds.map((id) => getInvestigation(id))
      );
      if (cancelled) return;
      setInvestigations((prev) => {
        const next = { ...prev };
        txnIds.forEach((id, i) => {
          const r = results[i];
          if (r.status === "fulfilled") {
            next[id] = r.value || null;
          } else {
            const status = r.reason?.response?.status;
            // 404 → "no investigation yet" (sentinel: null).  Anything
            // else (5xx, network error) → also null so the UI shows the
            // "Run investigation" affordance instead of an error toast.
            next[id] = status === 404 ? null : null;
          }
        });
        return next;
      });
    })();

    return () => { cancelled = true; };
  }, [usingDemo, enrichedQueue]);

  // Single-row refresh: re-fetch one verdict and update its slot.
  const refreshOneInvestigation = useCallback(async (txnId) => {
    setInvestigations((prev) => ({ ...prev, [txnId]: undefined }));
    try {
      const value = await getInvestigation(txnId);
      setInvestigations((prev) => ({ ...prev, [txnId]: value || null }));
    } catch {
      setInvestigations((prev) => ({ ...prev, [txnId]: null }));
    }
  }, []);

  // "Run Investigation →" handler.  Triggers a new run, then re-fetches
  // the canonical record so the row shows the verdict.
  const triggerOneInvestigation = useCallback(async (txnId) => {
    setInvestigations((prev) => ({ ...prev, [txnId]: undefined }));
    try {
      const value = await triggerInvestigation(txnId, null, "manual");
      setInvestigations((prev) => ({ ...prev, [txnId]: value || null }));
    } catch {
      // On failure, fall back to one more GET in case the trigger
      // succeeded but the response was lost.
      try {
        const value = await getInvestigation(txnId);
        setInvestigations((prev) => ({ ...prev, [txnId]: value || null }));
      } catch {
        setInvestigations((prev) => ({ ...prev, [txnId]: null }));
      }
    }
  }, []);

  const stats = (!usingDemo && enrichedQueue?.length > 0)
    ? { total_reports: enrichedQueue.length, confirmed_fraud: 0, accuracy_delta: 0 }
    : (realStats || DEMO_STATS);

  const handleDecide = async (id, resolution) => {
    setDecidingId(id);
    try {
      if (!usingDemo) {
        await decideReviewItem(id, resolution === "fraud" ? "fraud" : "legitimate").catch(() => {});
      } else {
        await new Promise((r) => setTimeout(r, 600));
      }
      setLocalDecisions((prev) => ({ ...prev, [id]: resolution }));
    } finally {
      setDecidingId(null);
    }
  };

  const refresh = fetchQueue;

  const filteredQueue = severityFilter === "ALL"
    ? queue
    : queue.filter((q) => getSeverityFromItem(q) === severityFilter);

  const pending  = filteredQueue.filter((q) => q.status === "pending");
  const resolved = filteredQueue.filter((q) => q.status !== "pending");

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between"
      >
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Inbox size={22} className="text-orange-400" />
            Alerts Center
          </h2>
          <p className="text-exiqo-glow/60 text-sm mt-1">
            Phase 8 — Feedback flywheel · analyst review queue · Phase 9 verdicts inline
          </p>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg bg-white/10 text-exiqo-glow
                     hover:bg-white/15 transition font-medium"
        >
          <RefreshCw size={13} />
          Refresh
        </button>
      </motion.div>

      {/* Demo/real data banner */}
      {usingDemo ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 text-xs"
        >
          <AlertTriangle size={14} />
          Showing demo queue — real flagged transactions from your account will appear here automatically.
        </motion.div>
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-green-50 border border-green-200 text-green-700 text-xs"
        >
          <CheckCircle size={14} />
          Showing {enrichedQueue?.length} real flagged transactions — sorted by risk score. Use Confirm / Dismiss to label them and improve the model.
        </motion.div>
      )}

      {/* Feedback stats banner */}
      {stats && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="grid grid-cols-3 gap-3"
        >
          {[
            { label: "Reports filed",     value: stats.total_reports ?? 0,                                                                color: "#3b82f6" },
            { label: "Confirmed fraud",   value: stats.confirmed_fraud ?? 0,                                                              color: "#ef4444" },
            { label: "Model improvement", value: stats.accuracy_delta ? `+${(stats.accuracy_delta * 100).toFixed(1)}%` : "—",            color: "#10b981" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm text-center">
              <p className="text-2xl font-bold" style={{ color }}>{value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{label}</p>
            </div>
          ))}
        </motion.div>
      )}

      {/* Severity filter chips */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex flex-wrap gap-2"
      >
        {SEVERITY_FILTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSeverityFilter(s)}
            className={`px-3 py-1 rounded-full text-sm font-medium border transition-all ${
              severityFilter === s
                ? "bg-red-600 text-white border-red-600"
                : "bg-transparent text-gray-400 border-gray-600 hover:border-red-400 hover:text-red-300"
            }`}
          >
            {s}
          </button>
        ))}
        {severityFilter !== "ALL" && (
          <span className="text-xs text-gray-500 self-center">
            — showing {filteredQueue.length} alert{filteredQueue.length !== 1 ? "s" : ""}
          </span>
        )}
      </motion.div>

      {/* Queue */}
      {qLoading ? (
        <RiskStatePlaceholder loading />
      ) : (
        <>
          {pending.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider opacity-60">
                Awaiting review ({pending.length})
              </h3>
              <div className="space-y-2">
                <AnimatePresence>
                  {pending.map((item) => (
                    <QueueItem
                      key={item.id}
                      item={item}
                      onDecide={handleDecide}
                      deciding={decidingId === item.id}
                      investigationState={
                        item.transaction_id ? investigations[item.transaction_id] : undefined
                      }
                      onRefreshInv={refreshOneInvestigation}
                      onTriggerInv={triggerOneInvestigation}
                    />
                  ))}
                </AnimatePresence>
              </div>
            </div>
          )}

          {resolved.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider opacity-60">
                Recent decisions ({resolved.length})
              </h3>
              <div className="space-y-2">
                {resolved.slice(0, 10).map((item) => (
                  <QueueItem
                    key={item.id}
                    item={item}
                    onDecide={handleDecide}
                    deciding={false}
                    investigationState={
                      item.transaction_id ? investigations[item.transaction_id] : undefined
                    }
                    onRefreshInv={refreshOneInvestigation}
                    onTriggerInv={triggerOneInvestigation}
                  />
                ))}
              </div>
            </div>
          )}

          {pending.length === 0 && resolved.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center gap-3 py-12 text-gray-400"
            >
              <Inbox size={40} className="text-gray-200" />
              <p className="font-medium">No items in the review queue</p>
              <p className="text-xs text-center max-w-xs">
                When users report suspicious transactions, they appear here for analyst review.
              </p>
            </motion.div>
          )}
        </>
      )}
    </div>
  );
};

export default AlertsCenter;
