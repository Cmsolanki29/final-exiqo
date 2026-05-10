/**
 * AlertsCenter — Phase 8 feedback flywheel UI.
 * Shows review queue, lets admins confirm/dismiss fraud reports,
 * and shows the feedback stats for the current user.
 *
 * Falls back to a realistic demo queue (with working local actions)
 * when the admin endpoint is unavailable.
 */

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldOff, CheckCircle, XCircle, Clock, Loader2, RefreshCw, Inbox,
  AlertTriangle,
} from "lucide-react";
import { useFeedbackStats } from "../../hooks/risk/useFeedbackStats";
import { getEnrichedReviewQueue, decideReviewItem } from "../../services/riskApi";
import { RiskStatePlaceholder } from "../../components/risk/RiskStatePlaceholder";
import { fmtCurrency, fmtRelativeTime } from "../../utils/risk/formatters";

// ── Demo fallback queue ────────────────────────────────────────────────────
const DEMO_QUEUE = [
  {
    id: 101,
    transaction_id: "TXN-9981",
    merchant: "Unknown Vendor",
    amount: 4999,
    notes: "Charge looks unfamiliar — never used this merchant before",
    status: "pending",
    created_at: new Date(Date.now() - 90_000),
  },
  {
    id: 102,
    transaction_id: "TXN-9974",
    merchant: "International Marketplace",
    amount: 12500,
    notes: "Purchase made from a country I haven't visited",
    status: "pending",
    created_at: new Date(Date.now() - 1.5 * 3600_000),
  },
  {
    id: 103,
    transaction_id: "TXN-9968",
    merchant: "Lottery Winner Co.",
    amount: 1,
    notes: "₹1 trap — testing for valid card",
    status: "pending",
    created_at: new Date(Date.now() - 4 * 3600_000),
  },
  {
    id: 104,
    transaction_id: "TXN-9952",
    merchant: "Amazon",
    amount: 1299,
    notes: "Confirmed legitimate purchase",
    status: "dismissed",
    created_at: new Date(Date.now() - 1 * 86400_000),
  },
  {
    id: 105,
    transaction_id: "TXN-9940",
    merchant: "Phishing Bank Alert",
    amount: 25000,
    notes: "Confirmed fraud — phishing SMS click-through",
    status: "fraud",
    created_at: new Date(Date.now() - 2 * 86400_000),
  },
  {
    id: 106,
    transaction_id: "TXN-9931",
    merchant: "Swiggy",
    amount: 340,
    notes: "Customer dispute — food not delivered",
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

function QueueItem({ item, onDecide, deciding }) {
  const meta = STATUS_META[item.status] || STATUS_META.pending;
  const StatusIcon = meta.icon;

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
      </div>
    </motion.div>
  );
}

const AlertsCenter = ({ userId }) => {
  const { data: realStats } = useFeedbackStats();
  const [decidingId, setDecidingId] = useState(null);
  const [localDecisions, setLocalDecisions] = useState({});
  const [enrichedQueue, setEnrichedQueue] = useState(null);
  const [qLoading, setQLoading] = useState(true);
  const [qError, setQError] = useState(false);

  // Fetch enriched queue (has merchant, amount, reason)
  const fetchQueue = React.useCallback(() => {
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

  const pending  = queue.filter((q) => q.status === "pending");
  const resolved = queue.filter((q) => q.status !== "pending");

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
            Phase 8 — Feedback flywheel · analyst review queue
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
