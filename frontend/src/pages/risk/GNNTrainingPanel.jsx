/**
 * GNNTrainingPanel — Phase 10 GraphSAGE training trigger + status UI.
 *
 * Backend endpoints used:
 *   GET  /api/risk/gnn/status     (admin)   → trained_at, graph_users, embeddings_stored
 *   POST /api/risk/gnn/train      (admin)   → runs GraphSAGE, persists embeddings
 *   GET  /api/risk/gnn/health     (public)  → feature_flag_enabled + config
 *
 * UX:
 *   1. Status grid (last trained, graph users, embeddings stored, params)
 *   2. Big "Train GNN Now" CTA → confirm dialog → POST /train with spinner
 *   3. Result summary on success (users_in_graph, epochs_run, duration_sec, trained)
 *   4. Phase 10 health row at the bottom
 */

import React, { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Share2,
  RefreshCw,
  Loader2,
  Play,
  Network,
  AlertTriangle,
  Database,
  Settings2,
  CheckCircle2,
  Clock,
} from "lucide-react";
import {
  getGnnStatus,
  getGnnHealth,
  triggerGnnTrain,
} from "../../services/riskApi";
import { SkeletonCard } from "../../components/common/SkeletonCard";
import { useToast } from "../../components/common/Toast";
import { fmtRelativeTime } from "../../utils/risk/formatters";

// ── Confirm dialog (matches DNN page style) ───────────────────────────────
function ConfirmDialog({ open, title, message, onCancel, onConfirm, busy }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full rounded-2xl border border-white/10 bg-exiqo-dark/90 backdrop-blur-md p-6"
      >
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="text-sm text-exiqo-glow/70 mt-2">{message}</p>
        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="px-3 py-1.5 text-sm rounded-lg border border-white/10 text-exiqo-glow/80 hover:bg-white/[0.05] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold disabled:opacity-50"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            {busy ? "Training…" : "Train GNN"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function InfoTile({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-white/5 bg-black/20 p-3">
      <p className="text-[10px] uppercase tracking-wider text-exiqo-glow/40 font-semibold mb-1">
        {label}
      </p>
      <p className="text-sm font-bold text-white">{value ?? "—"}</p>
      {hint && <p className="text-[10px] text-exiqo-glow/40 mt-0.5">{hint}</p>}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
const GNNTrainingPanel = () => {
  const { showToast } = useToast();

  const [status, setStatus] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [training, setTraining] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [s, h] = await Promise.allSettled([getGnnStatus(), getGnnHealth()]);
    if (s.status === "fulfilled") setStatus(s.value);
    else setError(s.reason?.message || "status unavailable");
    if (h.status === "fulfilled") setHealth(h.value);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const handleConfirmTrain = async () => {
    setTraining(true);
    setLastResult(null);
    try {
      const result = await triggerGnnTrain();
      setLastResult(result);
      if (result?.trained === false) {
        const reason = result.reason || "training_skipped";
        showToast(`Training skipped: ${reason}`, "warning");
      } else {
        showToast(
          `GNN trained in ${result?.duration_sec ? Number(result.duration_sec).toFixed(1) + "s" : "—"}`,
          "success"
        );
      }
      setConfirmOpen(false);
      fetchAll();
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || "Training failed";
      showToast(msg, "error");
      setLastResult({ trained: false, reason: msg });
    } finally {
      setTraining(false);
    }
  };

  const trainedAt = status?.trained_at ?? status?.last_trained_at;
  const graphUsers = status?.graph_users ?? status?.users_in_graph;
  const embeddings = status?.embeddings_stored ?? status?.embedding_count;

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
            <Share2 size={20} className="text-sky-400" />
            <h2 className="text-2xl font-bold text-white">GNN Training</h2>
            <span className="text-[10px] font-bold bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded uppercase tracking-wider">
              Phase 10 · 2026
            </span>
          </div>
          <p className="text-exiqo-glow/60 text-sm mt-1">
            GraphSAGE builds a 64-dim embedding per user from transaction relationships.
            Embeddings feed the orchestrator as a context signal.
          </p>
        </div>

        <button
          type="button"
          onClick={fetchAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-white/10 bg-white/[0.03] text-exiqo-glow/80 hover:bg-white/[0.07] transition"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </motion.div>

      {/* Status grid */}
      {loading ? (
        <SkeletonCard lines={4} height={180} />
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm"
        >
          <div className="flex items-center gap-2 mb-3">
            <Network size={16} className="text-sky-300" />
            <h3 className="text-sm font-semibold text-white">Current state</h3>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <InfoTile
              label="Last training run"
              value={trainedAt ? fmtRelativeTime(trainedAt) : "Never trained"}
              hint={trainedAt ? new Date(trainedAt).toLocaleString() : "Click below to run"}
            />
            <InfoTile label="Graph users" value={graphUsers ?? "—"} />
            <InfoTile label="Embeddings stored" value={embeddings ?? "—"} />
            <InfoTile label="Embed dim"     value={health?.embed_dim ?? status?.embed_dim ?? "64"} />
            <InfoTile label="Num layers"    value={health?.num_layers ?? "—"} />
            <InfoTile label="Training days" value={health?.training_days ?? "—"} hint="lookback window" />
          </div>
        </motion.div>
      )}

      {/* CTA */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-900/30 via-exiqo-dark/40 to-pink-900/20 p-6 backdrop-blur-sm"
      >
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-white">Train GNN now</h3>
            <p className="text-sm text-exiqo-glow/70 mt-1">
              Runs pure-PyTorch GraphSAGE across all users from the last{" "}
              <span className="text-white font-semibold">{health?.training_days ?? 90}</span> days
              of transactions and persists fresh embeddings to Redis + Postgres.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            disabled={training}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold shadow-lg shadow-purple-500/30 hover:shadow-purple-500/50 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {training ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {training ? "Training GraphSAGE…" : "Train GNN Now"}
          </button>
        </div>

        {training && (
          <div className="mt-4 flex items-center gap-2 text-sm text-purple-200">
            <Loader2 size={14} className="animate-spin" />
            Training GraphSAGE embeddings… this usually takes 5-20 seconds.
          </div>
        )}

        {lastResult && !training && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mt-4 rounded-xl border p-4 ${
              lastResult.trained
                ? "border-emerald-500/30 bg-emerald-500/[0.07]"
                : "border-amber-500/30 bg-amber-500/[0.07]"
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              {lastResult.trained ? (
                <CheckCircle2 size={14} className="text-emerald-400" />
              ) : (
                <AlertTriangle size={14} className="text-amber-400" />
              )}
              <p className={`text-sm font-semibold ${lastResult.trained ? "text-emerald-200" : "text-amber-200"}`}>
                {lastResult.trained ? "Training complete" : `Training did not run · ${lastResult.reason || "unknown"}`}
              </p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <InfoTile label="Users in graph"    value={lastResult.users_in_graph ?? lastResult.graph_users ?? "—"} />
              <InfoTile label="Epochs run"        value={lastResult.epochs_run ?? lastResult.epochs ?? "—"} />
              <InfoTile label="Duration"          value={lastResult.duration_sec ? `${Number(lastResult.duration_sec).toFixed(2)}s` : "—"} />
              <InfoTile label="Final loss"        value={lastResult.final_loss ? Number(lastResult.final_loss).toFixed(4) : "—"} />
            </div>
            {lastResult.hint && (
              <p className="text-[11px] text-exiqo-glow/50 mt-2 italic">{lastResult.hint}</p>
            )}
          </motion.div>
        )}
      </motion.div>

      {/* Health row */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm"
      >
        <div className="flex items-center gap-2 mb-3">
          <Settings2 size={16} className="text-purple-300" />
          <h3 className="text-sm font-semibold text-white">Phase 10 health</h3>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <InfoTile
            label="Feature flag"
            value={
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block w-2 h-2 rounded-full"
                  style={{ background: health?.feature_flag_enabled ? "#22c55e" : "#94a3b8" }}
                />
                {health?.feature_flag_enabled ? "Enabled" : "Disabled"}
              </span>
            }
          />
          <InfoTile label="Min users for training" value={health?.min_users_for_training ?? "—"} />
          <InfoTile
            label="Backend probe"
            value={
              health ? (
                <span className="inline-flex items-center gap-1.5 text-emerald-300 text-sm">
                  <CheckCircle2 size={12} /> reachable
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-amber-300 text-sm">
                  <AlertTriangle size={12} /> offline
                </span>
              )
            }
          />
          <InfoTile
            label="Storage"
            value={
              <span className="inline-flex items-center gap-1.5">
                <Database size={12} className="text-exiqo-glow/40" />
                Redis + Postgres
              </span>
            }
          />
        </div>
      </motion.div>

      {error && (
        <p className="text-[11px] text-amber-300 inline-flex items-center gap-1">
          <AlertTriangle size={11} /> {error}
        </p>
      )}

      <p className="text-[11px] text-exiqo-glow/40 inline-flex items-center gap-1">
        <Clock size={11} />
        GNN embeddings have a TTL of {health?.embed_ttl_sec ?? 86400}s in Redis. The DB copy is durable.
      </p>

      <ConfirmDialog
        open={confirmOpen}
        title="Train GraphSAGE over all users?"
        message="This will run GraphSAGE over all users. Continue?"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleConfirmTrain}
        busy={training}
      />
    </div>
  );
};

export default GNNTrainingPanel;
