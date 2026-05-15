/**
 * DNNShadowReport — Phase 11 Deep Neural Network shadow / promotion UI.
 *
 * Backend endpoints used:
 *   GET  /api/risk/dnn/status              (admin)
 *   GET  /api/risk/dnn/shadow/evaluation   (admin)
 *   GET  /api/risk/dnn/health              (public — promotion + model_loaded)
 *   POST /api/risk/dnn/train               (admin)
 *
 * Layout:
 *   - Promotion-status banner (amber/green)
 *   - Side-by-side XGBoost (prod) vs DNN (shadow) comparison
 *   - Model info row (branches, hidden_dim, model_loaded, etc.)
 *   - Recent training runs table
 *   - "Trigger retraining" button with confirmation + toast
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Layers,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Activity,
  Play,
  Cpu,
  Box,
} from "lucide-react";
import {
  getDnnStatus,
  getDnnShadowEvaluation,
  getDnnHealth,
  triggerDnnTrain,
  getModelStatus,
} from "../../services/riskApi";
import { SkeletonCard } from "../../components/common/SkeletonCard";
import { useToast } from "../../components/common/Toast";
import { fmtRelativeTime } from "../../utils/risk/formatters";

// ── Display helpers ────────────────────────────────────────────────────────
function fmtNumber(v, digits = 3) {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  return Number(v).toFixed(digits);
}

function MetricRow({ label, value, hint }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-2 border-b border-white/5 last:border-0">
      <span className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
        {label}
      </span>
      <div className="text-right">
        <span className="text-sm font-bold text-white tabular-nums">{value ?? "—"}</span>
        {hint && <p className="text-[10px] text-gray-500">{hint}</p>}
      </div>
    </div>
  );
}

function StatusDot({ ok }) {
  return (
    <span
      className="inline-block w-2 h-2 rounded-full"
      style={{ background: ok ? "#22c55e" : "#94a3b8" }}
    />
  );
}

// ── Confirmation dialog (lightweight inline) ───────────────────────────────
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
        <p className="text-sm text-gray-300 mt-2">{message}</p>
        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="px-3 py-1.5 text-sm rounded-lg border border-white/10 text-gray-300 hover:bg-white/[0.05] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-gradient-to-r from-teal-500 to-emerald-500 text-white font-semibold disabled:opacity-50"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            {busy ? "Training…" : "Confirm"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────
const DNNShadowReport = () => {
  const { showToast } = useToast();

  const [status, setStatus] = useState(null);
  const [shadow, setShadow] = useState(null);
  const [health, setHealth] = useState(null);
  const [prodMetrics, setProdMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [training, setTraining] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const [s, e, h, m] = await Promise.allSettled([
      getDnnStatus(),
      getDnnShadowEvaluation(),
      getDnnHealth(),
      getModelStatus(),
    ]);
    const errs = {};
    if (s.status === "fulfilled") setStatus(s.value);
    else errs.status = s.reason?.message;
    if (e.status === "fulfilled") setShadow(e.value);
    else errs.shadow = e.reason?.message;
    if (h.status === "fulfilled") setHealth(h.value);
    if (m.status === "fulfilled") setProdMetrics(m.value);
    setErrors(errs);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const promoted = !!health?.promoted;
  const modelLoaded = !!health?.model_loaded;

  const xgbMetrics = useMemo(() => {
    // getModelStatus() typically returns {accuracy, precision, recall, roc_auc, ...}
    return prodMetrics?.metrics || prodMetrics || {};
  }, [prodMetrics]);

  const shadowMetrics = useMemo(() => {
    return shadow?.metrics || shadow || {};
  }, [shadow]);

  const handleConfirmTrain = async () => {
    setTraining(true);
    try {
      const data = await triggerDnnTrain();
      showToast(
        `DNN retraining complete${data?.duration_sec ? ` in ${Number(data.duration_sec).toFixed(1)}s` : ""}`,
        "success"
      );
      setConfirmOpen(false);
      fetchAll();
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || "Training failed";
      showToast(msg, "error");
    } finally {
      setTraining(false);
    }
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
            <Layers size={20} className="text-teal-300" />
            <h2 className="text-2xl font-bold text-white">DNN Shadow Report</h2>
            <span className="text-[10px] font-bold bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded uppercase tracking-wider">
              Phase 11 · 2026
            </span>
          </div>
          <p className="text-gray-400 text-sm mt-1">
            Multi-branch DNN running in shadow alongside XGBoost — promoted only after the
            24-hour regression check passes.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-white/10 bg-white/[0.03] text-gray-300 hover:bg-white/[0.07] transition"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            disabled={training}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-teal-500 to-emerald-500 text-white shadow disabled:opacity-50"
          >
            {training ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            {training ? "Training…" : "Trigger retraining"}
          </button>
        </div>
      </motion.div>

      {/* Promotion banner */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className={`rounded-2xl border p-4 backdrop-blur-sm flex items-start gap-3 ${
          promoted
            ? "border-emerald-500/30 bg-emerald-500/[0.06]"
            : "border-amber-500/30 bg-amber-500/[0.06]"
        }`}
      >
        {promoted ? (
          <CheckCircle2 size={18} className="text-emerald-400 mt-0.5 shrink-0" />
        ) : (
          <AlertTriangle size={18} className="text-amber-400 mt-0.5 shrink-0" />
        )}
        <div>
          <p className={`text-sm font-semibold ${promoted ? "text-emerald-200" : "text-amber-200"}`}>
            {promoted ? "PROMOTED" : "Shadow mode"}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            {promoted
              ? "DNN is blending into production scores."
              : "DNN score is logged only, not served to users. Set PHASE_11_DNN_PROMOTED=true in .env to promote."}
          </p>
        </div>
      </motion.div>

      {/* Comparison */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SkeletonCard lines={4} height={220} />
          <SkeletonCard lines={4} height={220} />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* XGBoost (production) */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm"
          >
            <div className="flex items-center gap-2 mb-2">
              <Cpu size={16} className="text-indigo-300" />
              <h3 className="text-sm font-semibold text-white">XGBoost (production)</h3>
              <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/20 font-semibold">
                LIVE
              </span>
            </div>
            <MetricRow label="ROC AUC"          value={fmtNumber(xgbMetrics.roc_auc)} />
            <MetricRow label="PR AUC"           value={fmtNumber(xgbMetrics.pr_auc)} />
            <MetricRow label="Val AUC-PR"       value={fmtNumber(xgbMetrics.val_aucpr)} />
            <MetricRow label="Recall@5% FPR"    value={fmtNumber(xgbMetrics.recall_at_5pct_fpr)} />
            <MetricRow label="Prec@80% Recall"  value={fmtNumber(xgbMetrics.precision_at_80_recall)} />
          </motion.div>

          {/* DNN (shadow) */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="rounded-2xl border border-teal-500/20 bg-teal-500/[0.04] p-5 backdrop-blur-sm"
          >
            <div className="flex items-center gap-2 mb-2">
              <Layers size={16} className="text-teal-300" />
              <h3 className="text-sm font-semibold text-white">DNN (shadow)</h3>
              <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-teal-500/15 text-teal-300 border border-teal-500/20 font-semibold">
                {promoted ? "PROMOTED" : "SHADOW"}
              </span>
            </div>
            {/* Live shadow evaluation metrics (populated after 24h of shadow logging) */}
            <MetricRow label="Shadow accuracy"   value={fmtNumber(shadowMetrics.accuracy)} />
            <MetricRow label="Shadow MAE"        value={fmtNumber(shadowMetrics.mae)} />
            <MetricRow label="Improvement Δ"     value={fmtNumber(shadowMetrics.improvement_delta)} hint="vs XGBoost" />
            <MetricRow label="Sample size (24h)" value={shadowMetrics.sample_size ?? "—"} />
            <MetricRow label="Last evaluated"    value={shadowMetrics.evaluated_at ? fmtRelativeTime(shadowMetrics.evaluated_at) : "—"} />
            {/* Fallback: show model test-set ROC/PR AUC until live shadow logging accumulates */}
            {!shadowMetrics.accuracy && (status?.metrics?.test_roc_auc || status?.metrics?.test_pr_auc) && (
              <div className="mt-2 pt-2 border-t border-white/[0.06]">
                <p className="text-[10px] text-gray-600 mb-1 uppercase tracking-wider">Test-set (no live shadow yet)</p>
                <MetricRow label="Test ROC AUC" value={fmtNumber(status?.metrics?.test_roc_auc)} hint="from training run" />
                <MetricRow label="Test PR AUC"  value={fmtNumber(status?.metrics?.test_pr_auc)}  hint="from training run" />
              </div>
            )}
          </motion.div>
        </div>
      )}

      {/* Model info row */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm"
      >
        <div className="flex items-center gap-2 mb-3">
          <Box size={16} className="text-purple-300" />
          <h3 className="text-sm font-semibold text-white">Model architecture</h3>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-sm">
          <InfoTile label="Branches"           value={status?.metrics?.config?.branches   ?? status?.last_run?.branches   ?? status?.branches   ?? "—"} />
          <InfoTile label="Hidden dim"         value={status?.metrics?.config?.hidden_dim ?? status?.last_run?.hidden_dim ?? status?.hidden_dim  ?? "—"} />
          <InfoTile label="Epochs trained"     value={status?.metrics?.epochs  ?? status?.last_run?.epochs  ?? status?.epochs_trained    ?? "—"} />
          <InfoTile label="Training positives" value={status?.metrics?.n_pos_train ?? status?.last_run?.n_pos_train ?? status?.training_positives ?? "—"} />
          <InfoTile
            label="Label source"
            value={
              status?.last_run?.label_source ??
              status?.metrics?.label_source ??
              "anomaly_flag"
            }
          />
          <InfoTile label="Blend weight" value={fmtNumber(health?.blend_weight, 2)} />
          <InfoTile
            label="Model loaded"
            value={
              <span className="inline-flex items-center gap-1.5">
                <StatusDot ok={modelLoaded} />
                {modelLoaded ? "Yes" : "No"}
              </span>
            }
          />
        </div>
      </motion.div>

      {/* Recent training runs */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm"
      >
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} className="text-pink-300" />
          <h3 className="text-sm font-semibold text-white">Recent training runs</h3>
        </div>
        {Array.isArray(status?.recent_runs) && status.recent_runs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                  <th className="py-2 pr-3 font-semibold">Run</th>
                  <th className="py-2 pr-3 font-semibold">Started</th>
                  <th className="py-2 pr-3 font-semibold">Epochs</th>
                  <th className="py-2 pr-3 font-semibold">Final loss</th>
                  <th className="py-2 pr-3 font-semibold">Duration</th>
                </tr>
              </thead>
              <tbody>
                {status.recent_runs.map((r, i) => (
                  <tr key={r.run_id ?? i} className="border-b border-white/5 last:border-0">
                    <td className="py-2 pr-3 font-mono text-xs text-white">{r.run_id ?? `run-${i + 1}`}</td>
                    <td className="py-2 pr-3 text-gray-400">{r.started_at ? fmtRelativeTime(r.started_at) : "—"}</td>
                    <td className="py-2 pr-3 text-gray-400">{r.epochs ?? "—"}</td>
                    <td className="py-2 pr-3 text-gray-400 tabular-nums">{fmtNumber(r.final_loss ?? r.loss)}</td>
                    <td className="py-2 pr-3 text-gray-400 tabular-nums">{r.duration_sec ? `${Number(r.duration_sec).toFixed(1)}s` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-500 py-4 text-center">
            No training runs recorded yet. Click <span className="font-semibold text-gray-300">Trigger retraining</span> to run a fresh DNN training.
          </p>
        )}
      </motion.div>

      {(errors.status || errors.shadow) && (
        <p className="text-[11px] text-amber-300 inline-flex items-center gap-1">
          <AlertTriangle size={11} />
          {errors.status || errors.shadow}
        </p>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title="Retrain DNN?"
        message="This will run a fresh training cycle on the multi-branch DNN using current labels. It typically takes 10-60 seconds and runs synchronously."
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleConfirmTrain}
        busy={training}
      />
    </div>
  );
};

function InfoTile({ label, value }) {
  return (
    <div className="rounded-lg border border-white/5 bg-black/20 p-3 min-h-[64px]">
      <p className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">
        {label}
      </p>
      <p className="text-sm font-bold text-white">{value ?? "—"}</p>
    </div>
  );
}

export default DNNShadowReport;
