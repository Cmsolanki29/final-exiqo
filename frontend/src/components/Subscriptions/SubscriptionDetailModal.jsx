import React, { useCallback, useEffect, useState } from "react";
import { Loader2, Star, TrendingDown, TrendingUp, X } from "lucide-react";
import {
  getSubscriptionRecommendation,
  postSubscriptionEvaluate,
} from "../../services/api";
import { useToast } from "../common/Toast";
import { GlassCard } from "../intro/GlassCard";
import { inr } from "../../lib/format";

/**
 * Deep-dive sheet for a verdict row or a lightweight insight-derived row.
 * @param {{ open: boolean, row: object | null, userId: number | null, onClose: () => void, onRefresh?: () => void }} props
 */
export default function SubscriptionDetailModal({ open, row, userId, onClose, onRefresh }) {
  const { showToast } = useToast();
  const [paragraph, setParagraph] = useState("");
  const [loadingParagraph, setLoadingParagraph] = useState(false);
  const [evaluating, setEvaluating] = useState(false);

  const loadParagraph = useCallback(async () => {
    if (!userId || !row?.subscription_id) return;
    setLoadingParagraph(true);
    setParagraph("");
    try {
      const data = await getSubscriptionRecommendation(userId, row.subscription_id);
      setParagraph(data?.paragraph || "");
    } catch (e) {
      setParagraph("");
      showToast(e?.message || "Could not load recommendation", "error");
    } finally {
      setLoadingParagraph(false);
    }
  }, [userId, row?.subscription_id, showToast]);

  useEffect(() => {
    if (!open || !row?.subscription_id) return;
    void loadParagraph();
  }, [open, row?.subscription_id, loadParagraph]);

  if (!open || !row) return null;

  const usageDelta =
    typeof row.current_usage_hours === "number" && typeof row.previous_usage_hours === "number"
      ? row.current_usage_hours - row.previous_usage_hours
      : null;
  const pct =
    typeof row.usage_change_percentage === "number"
      ? row.usage_change_percentage
      : typeof row.current_usage_hours === "number" &&
          typeof row.previous_usage_hours === "number" &&
          row.previous_usage_hours > 0.05
        ? ((row.current_usage_hours - row.previous_usage_hours) / row.previous_usage_hours) * 100
        : null;

  const verdictKey = String(row.verdict || "").toLowerCase();
  const stars = Math.min(5, Math.max(0, Math.round(Number(row.confidence_score || 0) * 5)));

  const handleEvaluate = async () => {
    if (!userId || !row.subscription_id) return;
    setEvaluating(true);
    try {
      await postSubscriptionEvaluate(userId, row.subscription_id);
      showToast("Subscription re-evaluated", "success");
      onRefresh?.();
      await loadParagraph();
    } catch (e) {
      showToast(e?.message || "Evaluate failed", "error");
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sub-detail-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <GlassCard
        surface="panel"
        padding="md"
        elevation="raised"
        className="max-h-[min(92vh,720px)] w-full max-w-2xl overflow-y-auto rounded-t-3xl border-white/15 sm:rounded-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 -mx-2 -mt-2 mb-4 flex items-start justify-between gap-3 border-b border-white/10 bg-[#0a0618]/95 px-2 py-3 backdrop-blur-md sm:static sm:mb-4 sm:border-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-0">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-cyan-300/80">Subscription</p>
            <h2 id="sub-detail-title" className="font-heading text-xl font-semibold text-white">
              {row.subscription_name || "Subscription"}
            </h2>
            <p className="mt-1 text-xs text-white/50">ID #{row.subscription_id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-white/15 text-white/70 transition hover:bg-white/[0.08] hover:text-white md:h-10 md:w-10"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-violet-500/25 bg-violet-500/10 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-white/45">Monthly</p>
              <p className="mt-1 font-heading text-2xl font-semibold text-white">{inr(row.monthly_cost)}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-white/45">Verdict</p>
              <p className="mt-1 text-sm font-semibold capitalize text-white">{verdictKey.replace(/_/g, " ") || "—"}</p>
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold text-white">AI reasoning</h3>
            <div className="rounded-2xl border border-white/10 bg-black/25 p-4 text-sm leading-relaxed text-white/75">
              {row.reasoning || row.body || "—"}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-white/50">Confidence</span>
              <div className="flex gap-0.5">
                {[0, 1, 2, 3, 4].map((i) => (
                  <Star
                    key={i}
                    className={`h-4 w-4 ${i < stars ? "fill-amber-400 text-amber-400" : "text-white/15"}`}
                    aria-hidden
                  />
                ))}
              </div>
              <span className="text-xs font-semibold text-white/70">
                {Math.round(Number(row.confidence_score || 0) * 100)}%
              </span>
            </div>
          </div>

          {(typeof row.current_usage_hours === "number" || typeof row.previous_usage_hours === "number") && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-white">Usage (30-day window)</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-cyan-500/25 bg-cyan-500/10 p-4">
                  <p className="text-[11px] text-white/50">Recent</p>
                  <p className="mt-1 text-xl font-bold text-white">
                    {typeof row.current_usage_hours === "number" ? `${row.current_usage_hours.toFixed(1)}h` : "—"}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-[11px] text-white/50">Prior</p>
                  <p className="mt-1 text-xl font-bold text-white">
                    {typeof row.previous_usage_hours === "number" ? `${row.previous_usage_hours.toFixed(1)}h` : "—"}
                  </p>
                </div>
              </div>
              {pct != null && !Number.isNaN(pct) ? (
                <div className="mt-3 flex items-center justify-between rounded-2xl border border-white/10 px-4 py-3">
                  <span className="text-sm text-white/60">Change vs prior</span>
                  <span className={`flex items-center gap-1 text-lg font-bold ${pct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                    {pct >= 0 ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                    {pct >= 0 ? "+" : ""}
                    {pct.toFixed(0)}%
                  </span>
                </div>
              ) : usageDelta != null ? (
                <p className="mt-2 text-xs text-white/45">Δ usage ≈ {usageDelta >= 0 ? "+" : ""}{usageDelta.toFixed(1)}h</p>
              ) : null}
            </div>
          )}

          <div>
            <h3 className="mb-2 text-sm font-semibold text-white">Narrative</h3>
            <div className="min-h-[4rem] rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm leading-relaxed text-white/70">
              {loadingParagraph ? (
                <span className="inline-flex items-center gap-2 text-white/50">
                  <Loader2 className="h-4 w-4 animate-spin" /> Generating…
                </span>
              ) : (
                paragraph || "No narrative yet."
              )}
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={handleEvaluate}
              disabled={evaluating}
              className="inline-flex min-h-[48px] flex-1 items-center justify-center rounded-xl border border-cyan-400/40 bg-cyan-500/20 py-3 text-sm font-semibold text-cyan-100 hover:bg-cyan-500/30 disabled:opacity-50 md:min-h-0"
            >
              {evaluating ? <Loader2 className="h-4 w-4 animate-spin" /> : "Re-run evaluation"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex min-h-[48px] flex-1 items-center justify-center rounded-xl border border-white/15 bg-white/[0.06] py-3 text-sm font-semibold text-white hover:bg-white/[0.1] md:min-h-0"
            >
              Close
            </button>
          </div>
          <p className="text-center text-[11px] text-white/40">
            Cancellation happens in the merchant app — use reminders below to stay accountable.
          </p>
        </div>
      </GlassCard>
    </div>
  );
}
