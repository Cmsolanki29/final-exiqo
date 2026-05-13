import React, { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Bell,
  Calendar,
  CheckCircle,
  Clock,
  Loader2,
  RefreshCw,
  X,
  XCircle,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getSubscriptionRemindersPending, postSubscriptionReminderAction } from "../services/api";
import { useToast } from "../components/common/Toast";
import { SkeletonCard } from "../components/common/SkeletonCard";
import { PageHeader } from "../components/Dashboard/shared/PageHeader";
import { GlassCard } from "../components/intro/GlassCard";
import { inr } from "../lib/format";

const ACCOUNTABILITY_MIN = 10;

function hoursUntilFire(iso) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  return (t - Date.now()) / (1000 * 60 * 60);
}

function urgencyFromHours(h) {
  if (h == null) return { label: "Scheduled", ring: "border-white/15 bg-white/[0.04]", badge: "bg-white/10 text-white/80" };
  if (h < 24)
    return {
      label: "Critical",
      ring: "border-rose-500/35 bg-rose-500/10",
      badge: "bg-rose-500/90 text-white",
    };
  if (h < 72)
    return {
      label: "Urgent",
      ring: "border-amber-500/35 bg-amber-500/10",
      badge: "bg-amber-500/90 text-white",
    };
  return {
    label: "Upcoming",
    ring: "border-cyan-500/30 bg-cyan-500/10",
    badge: "bg-cyan-600/90 text-white",
  };
}

export default function SmartReminders({ onBack }) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [snoozeTarget, setSnoozeTarget] = useState(null);
  const [snoozeReason, setSnoozeReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const uid = user?.id;

  const load = useCallback(async () => {
    if (!uid) {
      setReminders([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await getSubscriptionRemindersPending(uid);
      const list = Array.isArray(data?.reminders) ? data.reminders : [];
      setReminders(
        [...list].sort((a, b) => String(a.fire_at || "").localeCompare(String(b.fire_at || "")))
      );
    } catch (e) {
      showToast(e?.message || "Could not load reminders", "error");
      setReminders([]);
    } finally {
      setLoading(false);
    }
  }, [uid, showToast]);

  useEffect(() => {
    void load();
  }, [load]);

  const postAction = async (reminderId, payload) => {
    if (!uid) return;
    await postSubscriptionReminderAction(uid, reminderId, payload);
    await load();
  };

  const handleCancelNow = async (r) => {
    const ok = window.confirm(
      `Mark ${r.merchant || "this subscription"} for cancellation workflow?\n\nComplete the actual cancel in the merchant app.`
    );
    if (!ok) return;
    try {
      await postAction(r.id, { action: "cancel_now" });
      showToast("Recorded: cancel now — finish in the merchant app", "success");
    } catch (e) {
      showToast(e?.message || "Action failed", "error");
    }
  };

  const handleKeep = async (r) => {
    const ok = window.confirm(`Dismiss reminders for ${r.merchant || "this subscription"}?`);
    if (!ok) return;
    try {
      await postAction(r.id, { action: "keep" });
      showToast("Kept — related reminders dismissed", "success");
    } catch (e) {
      showToast(e?.message || "Action failed", "error");
    }
  };

  const openSnooze = (r) => {
    setSnoozeTarget(r);
    setSnoozeReason("");
    setReasonError("");
  };

  const submitSnooze = async () => {
    const trimmed = snoozeReason.trim();
    if (trimmed.length < ACCOUNTABILITY_MIN) {
      setReasonError(`Enter at least ${ACCOUNTABILITY_MIN} characters (accountability).`);
      return;
    }
    if (!uid || !snoozeTarget) return;
    setSubmitting(true);
    setReasonError("");
    try {
      await postSubscriptionReminderAction(uid, snoozeTarget.id, {
        action: "remind_later",
        accountability_reason: trimmed,
      });
      showToast("Reminder snoozed ~24h — please revisit soon", "success");
      setSnoozeTarget(null);
      setSnoozeReason("");
      await load();
    } catch (e) {
      setReasonError(e?.message || "Could not snooze");
    } finally {
      setSubmitting(false);
    }
  };

  if (!uid) {
    return (
      <GlassCard surface="panel" padding="md" className="border-white/10">
        <p className="text-center text-white/70">Sign in to manage reminders.</p>
      </GlassCard>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-8">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex min-h-[48px] items-center gap-2 text-sm font-semibold text-cyan-200/90 hover:text-cyan-100 md:min-h-0"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to intelligence hub
      </button>

      <PageHeader
        eyebrow="Accountability"
        title="Smart reminders"
        subtitle="Due renewal alerts (shown state). Snooze requires a short reason — matches backend rules (min 10 characters)."
        accentHex="#a78bfa"
        rightSlot={
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex min-h-[48px] items-center gap-2 rounded-xl border border-white/15 bg-white/[0.06] px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/[0.1] disabled:opacity-50 md:min-h-0"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden />
            Refresh list
          </button>
        }
      />

      {loading ? (
        <SkeletonCard lines={5} height={140} />
      ) : reminders.length === 0 ? (
        <GlassCard surface="panel" padding="lg" className="border-emerald-500/25 text-center">
          <CheckCircle className="mx-auto mb-3 h-14 w-14 text-emerald-400/90" aria-hidden />
          <h2 className="font-heading text-lg font-semibold text-white">Nothing due right now</h2>
          <p className="mt-2 text-sm text-white/60">
            Shown reminders appear when <code className="rounded bg-white/10 px-1">fire_at</code> is in the past.
            From the hub, use <strong>Schedule reminders</strong>, then in the list below try{" "}
            <strong>Simulate next day</strong> (demo) to surface alerts faster.
          </p>
        </GlassCard>
      ) : (
        <ul className="space-y-4">
          {reminders.map((r) => {
            const h = hoursUntilFire(r.fire_at);
            const u = urgencyFromHours(h);
            const esc = Number(r.escalation_level || 1);
            return (
              <li key={r.id}>
                <GlassCard surface="panel" padding="md" className={`border ring-1 ${u.ring}`}>
                  {esc >= 2 && (
                    <div
                      className={`mb-4 rounded-xl border px-3 py-2 text-sm ${
                        esc >= 3
                          ? "border-rose-500/40 bg-rose-500/15 text-rose-100"
                          : "border-amber-500/35 bg-amber-500/12 text-amber-100"
                      }`}
                    >
                      <p className="font-semibold">
                        {esc >= 3 ? "High priority" : "Follow-up"} — escalation tier {esc}
                      </p>
                      {esc >= 3 && (
                        <p className="mt-1 text-xs text-white/70">
                          Approx. exposure: {inr((r.monthly_cost || 0) * 3)} over ~3 months at this price.
                        </p>
                      )}
                    </div>
                  )}

                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${u.badge}`}>
                          {u.label}
                        </span>
                        <span className="rounded-full border border-white/15 bg-white/[0.06] px-2.5 py-0.5 text-[10px] font-semibold uppercase text-white/60">
                          {r.reminder_type || "alert"}
                        </span>
                      </div>
                      <h3 className="font-heading text-lg font-semibold text-white">{r.merchant || "Subscription"}</h3>
                      <div className="mt-2 flex flex-wrap gap-4 text-sm text-white/55">
                        <span className="inline-flex items-center gap-1.5">
                          <Calendar className="h-4 w-4 shrink-0 text-cyan-300/80" aria-hidden />
                          Fire: {r.fire_at ? new Date(r.fire_at).toLocaleString() : "—"}
                        </span>
                        {h != null ? (
                          <span className="inline-flex items-center gap-1.5">
                            <Clock className="h-4 w-4 shrink-0 text-cyan-300/80" aria-hidden />
                            {h < 0 ? `${Math.abs(Math.round(h))}h overdue` : `${Math.round(h)}h until fire`}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-white/45">Charge</p>
                      <p className="font-heading text-2xl font-semibold text-white">{inr(r.monthly_cost)}</p>
                      <p className="text-[11px] text-white/40">/ month</p>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    <button
                      type="button"
                      onClick={() => void handleCancelNow(r)}
                      className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/20 py-3 text-sm font-semibold text-rose-100 hover:bg-rose-500/30 md:min-h-0"
                    >
                      <XCircle className="h-4 w-4" aria-hidden />
                      Cancel now
                    </button>
                    <button
                      type="button"
                      onClick={() => openSnooze(r)}
                      className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/15 py-3 text-sm font-semibold text-amber-100 hover:bg-amber-500/25 md:min-h-0"
                    >
                      <Clock className="h-4 w-4" aria-hidden />
                      Remind later
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleKeep(r)}
                      className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-emerald-500/35 bg-emerald-500/15 py-3 text-sm font-semibold text-emerald-100 hover:bg-emerald-500/25 md:min-h-0"
                    >
                      <CheckCircle className="h-4 w-4" aria-hidden />
                      Keep subscription
                    </button>
                  </div>
                </GlassCard>
              </li>
            );
          })}
        </ul>
      )}

      {snoozeTarget ? (
        <div
          className="fixed inset-0 z-[110] flex items-end justify-center bg-black/75 p-0 sm:items-center sm:p-4"
          role="dialog"
          aria-modal="true"
        >
          <GlassCard
            surface="panel"
            padding="md"
            className="w-full max-w-md rounded-t-3xl border-white/15 sm:rounded-3xl"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Bell className="h-5 w-5 text-amber-300" aria-hidden />
                <h3 className="font-heading text-lg font-semibold text-white">Why keep it?</h3>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSnoozeTarget(null);
                  setReasonError("");
                }}
                className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 text-white/60 hover:bg-white/[0.06]"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-white/65">
              You are postponing <strong className="text-white">{snoozeTarget.merchant}</strong>. Explain in at least{" "}
              {ACCOUNTABILITY_MIN} characters — required by the API before snooze.
            </p>
            <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-white/45">
              Accountability note
            </label>
            <textarea
              value={snoozeReason}
              onChange={(e) => {
                setSnoozeReason(e.target.value);
                setReasonError("");
              }}
              rows={4}
              className="mt-2 w-full resize-none rounded-xl border border-white/15 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:border-amber-400/50 focus:outline-none focus:ring-1 focus:ring-amber-400/40"
              placeholder="e.g. Family uses this on weekends; I need it for work during crunch weeks…"
            />
            {reasonError ? (
              <p className="mt-2 flex items-start gap-2 text-sm text-rose-300">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                {reasonError}
              </p>
            ) : null}
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setSnoozeTarget(null);
                  setReasonError("");
                }}
                className="flex-1 rounded-xl border border-white/15 py-3 text-sm font-semibold text-white/80 hover:bg-white/[0.06]"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submitting || snoozeReason.trim().length < ACCOUNTABILITY_MIN}
                onClick={() => void submitSnooze()}
                className="flex-1 rounded-xl border border-amber-500/50 bg-amber-500/25 py-3 text-sm font-semibold text-amber-50 hover:bg-amber-500/35 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {submitting ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Submit & snooze 24h"}
              </button>
            </div>
          </GlassCard>
        </div>
      ) : null}
    </div>
  );
}
