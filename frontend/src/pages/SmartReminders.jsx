import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Bell,
  Calendar,
  CheckCircle,
  Clock,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  getSubscriptionRemindersPending,
  postSubscriptionIntelRemindersScheduleUpcoming,
  postSubscriptionReminderAction,
} from "../services/api";
import { useToast } from "../components/common/Toast";
import { SkeletonCard } from "../components/common/SkeletonCard";
import { PageHeader } from "../components/Dashboard/shared/PageHeader";
import { GlassCard } from "../components/intro/GlassCard";
import { inr } from "../lib/format";

const ACCOUNTABILITY_MIN = 10;

/** Tier ≥2 = escalated renewal cadence — API requires min-length accountability text for remind_later. */
function snoozeRequiresAccountability(r) {
  return Number(r?.reminder_escalation_tier ?? 1) >= 2;
}

/** Maps scheduler keys (t10, t3, …) to “T-10 style” renewal windows from live subscription rows. */
const REMINDER_CADENCE_DAYS = {
  t20: 20,
  t15: 15,
  t10: 10,
  t7: 7,
  t5: 5,
  t3: 3,
  t2: 2,
  t1: 1,
};

function reminderWindowLabel(reminderType) {
  const k = String(reminderType || "").toLowerCase();
  const days = REMINDER_CADENCE_DAYS[k];
  if (days != null) {
    return `T-${days} (${days} day${days === 1 ? "" : "s"} before renewal charge)`;
  }
  return reminderType ? String(reminderType).toUpperCase() : "Renewal";
}

function reminderShortTag(reminderType) {
  const k = String(reminderType || "").toLowerCase();
  const days = REMINDER_CADENCE_DAYS[k];
  if (days != null) return `T-${days}`;
  return (reminderType || "ALT").toUpperCase();
}

function daysFromToday(iso) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  return Math.ceil((t - Date.now()) / 86400000);
}

function buildReminderNarrative(r) {
  const parts = [];
  const nb = r.next_billing_date;
  const d = nb != null ? daysFromToday(nb) : null;
  if (nb && d != null && !Number.isNaN(d)) {
    if (d > 0) {
      parts.push(`Next billing: ${new Date(nb).toLocaleDateString()} — ${d} day(s) until charge.`);
    } else if (d === 0) {
      parts.push(`Next billing: ${new Date(nb).toLocaleDateString()} — due today.`);
    } else {
      parts.push(`Billing anchor: ${new Date(nb).toLocaleDateString()} (${Math.abs(d)} day(s) on calendar).`);
    }
  }
  if (r.current_verdict) {
    parts.push(`Behaviour verdict: ${String(r.current_verdict).replace(/_/g, " ")}.`);
  }
  if (r.verdict_reason && String(r.verdict_reason).trim()) {
    parts.push(String(r.verdict_reason).trim());
  }
  const waste = Number(r.verdict_monthly_waste);
  if (waste > 0) {
    parts.push(`Potential waste from low usage (model): ~${inr(waste)}/mo.`);
  }
  if (r.intelligence_category) {
    parts.push(`Plan type: ${String(r.intelligence_category).replace(/_/g, " ")}.`);
  }
  if (r.linked_app_package) {
    parts.push(`Usage source (linked package): ${r.linked_app_package}.`);
  }
  if (parts.length === 0) {
    return "Renewal reminder tied to this subscription’s billing cycle and linked app usage in your workspace.";
  }
  return parts.join(" ");
}

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

function statePillClass(state) {
  if (state === "shown")
    return "bg-rose-500/25 text-rose-100 ring-1 ring-rose-500/30";
  if (state === "pending") return "bg-cyan-500/20 text-cyan-100 ring-1 ring-cyan-500/25";
  if (state === "snoozed") return "bg-violet-500/25 text-violet-100 ring-1 ring-violet-500/30";
  return "bg-white/10 text-white/70 ring-1 ring-white/15";
}

/** variant: active = due (shown), snoozed = remind later, scheduled = future pending */
function ReminderQueueCard({ r, variant, onCancelNow, onOpenSnooze, onKeep }) {
  const h = hoursUntilFire(r.fire_at);
  const isActive = variant === "active";
  const u = isActive
    ? urgencyFromHours(h)
    : variant === "snoozed"
      ? {
          label: "Deferred",
          ring: "border-violet-500/35 bg-violet-500/10",
          badge: "bg-violet-600/90 text-white",
        }
      : {
          label: "Scheduled",
          ring: "border-cyan-500/30 bg-cyan-500/10",
          badge: "bg-cyan-600/90 text-white",
        };
  const esc = Number(r.escalation_level || 1);

  let clockLine = null;
  if (h != null && !Number.isNaN(h)) {
    if (variant === "snoozed" && h > 0) {
      clockLine = `${Math.round(h)}h until this reminder surfaces again`;
    } else if (variant === "scheduled" && h > 0) {
      clockLine = `${Math.round(h)}h until this alert fires`;
    } else if (isActive) {
      const needReason = snoozeRequiresAccountability(r);
      clockLine =
        h < 0
          ? needReason
            ? `${Math.abs(Math.round(h))}h past alert time — take action or snooze (escalation: short reason required)`
            : `${Math.abs(Math.round(h))}h past alert time — take action or snooze 24h (no reason on first cycle)`
          : `${Math.round(h)}h until this alert fires`;
    } else if (variant === "snoozed" && h <= 0) {
      clockLine = "Due now — will move to your action queue on refresh";
    }
  }

  return (
    <GlassCard surface="panel" padding="md" className={`border ring-1 ${u.ring}`}>
      {esc >= 2 && isActive && (
        <div
          className={`mb-4 rounded-xl border px-3 py-2 text-sm ${
            esc >= 3
              ? "border-rose-500/40 bg-rose-500/15 text-rose-100"
              : "border-amber-500/35 bg-amber-500/12 text-amber-100"
          }`}
        >
          <p className="font-semibold">
            {esc >= 3
              ? `High priority — tier ${esc} (strongest nudges + exposure estimate below)`
              : `Escalation active — tier ${esc} (denser pre-renewal reminders after a kept cycle)`}
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
            <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${u.badge}`}>{u.label}</span>
            <span
              className="rounded-full border border-white/15 bg-white/[0.06] px-2.5 py-0.5 text-[10px] font-semibold uppercase text-white/60"
              title={reminderWindowLabel(r.reminder_type)}
            >
              {reminderShortTag(r.reminder_type)}
            </span>
            {r.state ? (
              <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${statePillClass(r.state)}`}>
                {r.state}
              </span>
            ) : null}
          </div>
          <h3 className="font-heading text-lg font-semibold text-white">{r.merchant || "Subscription"}</h3>
          <p className="mt-2 text-sm leading-relaxed text-white/70">{buildReminderNarrative(r)}</p>
          {!isActive ? (
            <p className="mt-2 text-sm text-white/55">
              {variant === "snoozed"
                ? "You chose Remind later — this row stays here until the next fire time (then it returns to your action queue)."
                : "This renewal window is scheduled; when it fires and becomes due, the three action buttons will appear."}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-4 text-sm text-white/55">
            <span className="inline-flex items-center gap-1.5">
              <Calendar className="h-4 w-4 shrink-0 text-cyan-300/80" aria-hidden />
              Alert fires: {r.fire_at ? new Date(r.fire_at).toLocaleString() : "—"}
            </span>
            {clockLine ? (
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-4 w-4 shrink-0 text-cyan-300/80" aria-hidden />
                {clockLine}
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

      {isActive ? (
        <div className="relative z-10 mt-4 grid gap-2 sm:grid-cols-3">
          <button
            type="button"
            onClick={() => void onCancelNow(r)}
            className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/20 py-3 text-sm font-semibold text-rose-100 hover:bg-rose-500/30 md:min-h-0"
          >
            <XCircle className="h-4 w-4" aria-hidden />
            Cancel now
          </button>
          <button
            type="button"
            onClick={() => onOpenSnooze(r)}
            className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/15 py-3 text-sm font-semibold text-amber-100 hover:bg-amber-500/25 md:min-h-0"
          >
            <Clock className="h-4 w-4" aria-hidden />
            Remind later
          </button>
          <button
            type="button"
            onClick={() => void onKeep(r)}
            className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-xl border border-emerald-500/35 bg-emerald-500/15 py-3 text-sm font-semibold text-emerald-100 hover:bg-emerald-500/25 md:min-h-0"
          >
            <CheckCircle className="h-4 w-4" aria-hidden />
            Keep subscription
          </button>
        </div>
      ) : null}
    </GlassCard>
  );
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

  const uid = user?.id != null && Number(user.id) > 0 ? Number(user.id) : null;

  const load = useCallback(
    async (options = {}) => {
      const silent = Boolean(options.silent);
      if (!uid) {
        setReminders([]);
        if (!silent) setLoading(false);
        return;
      }
      if (!silent) setLoading(true);
      try {
        try {
          await postSubscriptionIntelRemindersScheduleUpcoming(uid);
        } catch {
          /* non-fatal — list may still load */
        }
        const data = await getSubscriptionRemindersPending(uid, { include_upcoming: true });
        const list = Array.isArray(data?.reminders) ? data.reminders : [];
        setReminders(
          [...list].sort((a, b) => String(a.fire_at || "").localeCompare(String(b.fire_at || "")))
        );
      } catch (e) {
        showToast(e?.message || "Could not load reminders", "error");
        setReminders([]);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [uid, showToast]
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onSync = () => {
      void load();
    };
    window.addEventListener("ss-subscription-intel-refresh", onSync);
    return () => window.removeEventListener("ss-subscription-intel-refresh", onSync);
  }, [load]);

  const postAction = async (reminderId, payload) => {
    if (!uid) return;
    await postSubscriptionReminderAction(uid, reminderId, payload);
    await load({ silent: true });
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

  const requestSnooze = useCallback(
    (r) => {
      if (snoozeRequiresAccountability(r)) {
        setSnoozeTarget(r);
        setSnoozeReason("");
        setReasonError("");
        return;
      }
      const ok = window.confirm(
        "Snooze this alert about 24 hours? On tier 1 (first renewal cycle) no written reason is required. After escalation to denser reminders, Remind later will ask why you are keeping the subscription."
      );
      if (!ok || !uid) return;
      void (async () => {
        try {
          await postSubscriptionReminderAction(uid, r.id, { action: "remind_later" });
          showToast("Reminder snoozed ~24h", "success");
          await load({ silent: true });
        } catch (e) {
          showToast(e?.message || "Could not snooze", "error");
        }
      })();
    },
    [uid, load, showToast]
  );

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
      await load({ silent: true });
    } catch (e) {
      setReasonError(e?.message || "Could not snooze");
    } finally {
      setSubmitting(false);
    }
  };

  const { needsAttention, snoozed, scheduled } = useMemo(() => {
    const na = [];
    const sn = [];
    const sc = [];
    for (const r of reminders) {
      const st = String(r.state || "");
      if (st === "shown") na.push(r);
      else if (st === "snoozed") sn.push(r);
      else if (st === "pending") sc.push(r);
      else sc.push(r);
    }
    const byFire = (a, b) => String(a.fire_at || "").localeCompare(String(b.fire_at || ""));
    na.sort(byFire);
    sn.sort(byFire);
    sc.sort(byFire);
    return { needsAttention: na, snoozed: sn, scheduled: sc };
  }, [reminders]);

  if (!uid) {
    return (
      <GlassCard surface="panel" padding="md" className="border-white/10">
        <p className="text-center text-white/70">Sign in to manage reminders.</p>
      </GlassCard>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (typeof onBack === "function") onBack();
          }}
          className="inline-flex min-h-[48px] w-fit items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10 md:min-h-0"
        >
          <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden />
          Back to intelligence hub
        </button>
        <nav className="text-xs text-exiqo-glow/55" aria-label="Breadcrumb">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-white/50">Intelligence hub</span>
            <span className="text-white/25" aria-hidden>
              /
            </span>
            <span className="font-medium text-white/75">Smart reminders</span>
          </div>
        </nav>
      </div>

      <GlassCard surface="panel" padding="md" className="border-violet-500/20">
        <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-violet-300/90">Smart subscription reminder system</p>
        <p className="mt-2 text-sm text-white/70">
          Billing &amp; renewal tracking, T-10 / T-3 / T-1 cadences (denser T-15→T-1 after escalation), snooze 24h
          without a note on <strong className="text-white/90">tier 1</strong>, mandatory short reason on{" "}
          <strong className="text-white/90">tier 2+</strong> remind-later, plus cancel / keep — wired to your live{" "}
          <code className="rounded bg-black/30 px-1 text-[11px]">scheduled_reminders</code> and{" "}
          <code className="rounded bg-black/30 px-1 text-[11px]">subscriptions</code> rows.
        </p>
        <ul className="mt-3 grid gap-1.5 text-xs text-white/60 sm:grid-cols-2">
          <li className="flex gap-2">
            <span className="text-emerald-400">✔</span> Auto reminders from next billing date
          </li>
          <li className="flex gap-2">
            <span className="text-emerald-400">✔</span> Escalation when tiers increase
          </li>
          <li className="flex gap-2">
            <span className="text-emerald-400">✔</span> Tier 1: one-tap snooze · Tier 2+: 10+ char reason (API)
          </li>
          <li className="flex gap-2">
            <span className="text-emerald-400">✔</span> Cancel now / keep — updates reminder + subscription state
          </li>
        </ul>
      </GlassCard>

      <PageHeader
        eyebrow="Accountability"
        title="Smart reminders"
        subtitle="Alerts use your real renewal dates, monthly charge, and verdict fields from the DB. First-cycle (tier 1) snooze has no reason; after escalation (tier 2+), Remind later requires at least 10 characters — same rules as the API."
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
          <h2 className="font-heading text-lg font-semibold text-white">No renewal reminders in your queue</h2>
          <p className="mt-2 text-sm text-white/60">
            We just synced the scheduler for renewals in the next 30 days. If you still see this, you may have no
            upcoming billing dates in range, or all reminders are already dismissed. From the hub, use{" "}
            <strong>Schedule reminders</strong> again, or in demo mode use <strong>Simulate next day</strong> to pull{" "}
            <code className="rounded bg-white/10 px-1">fire_at</code> forward so due alerts appear.
          </p>
        </GlassCard>
      ) : (
        <div className="space-y-10">
          {needsAttention.length === 0 && reminders.length > 0 ? (
            <p className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100/95">
              Nothing in your <strong className="text-white">action queue</strong> right now — you still have deferred
              or upcoming windows below.
            </p>
          ) : null}

          {needsAttention.length > 0 ? (
            <section className="space-y-4" aria-labelledby="reminders-needs-response">
              <div>
                <h2 id="reminders-needs-response" className="font-heading text-base font-semibold text-white">
                  Needs your response
                </h2>
                <p className="mt-1 text-sm text-white/55">
                  These alerts are <strong className="text-white/80">shown</strong> (due). Cancel now, snooze ~24h
                  (reason only if this subscription is on <strong className="text-white/80">escalation tier 2+</strong>
                  ), or keep — the list refreshes from the API.
                </p>
              </div>
              <ul className="space-y-4">
                {needsAttention.map((r) => (
                  <li key={r.id}>
                    <ReminderQueueCard
                      r={r}
                      variant="active"
                      onCancelNow={handleCancelNow}
                      onOpenSnooze={requestSnooze}
                      onKeep={handleKeep}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {snoozed.length > 0 ? (
            <section className="space-y-4" aria-labelledby="reminders-snoozed">
              <div>
                <h2 id="reminders-snoozed" className="font-heading text-base font-semibold text-white">
                  Remind me later
                </h2>
                <p className="mt-1 text-sm text-white/55">
                  You snoozed these with an accountability note. They stay here until the next{" "}
                  <code className="rounded bg-white/10 px-1 text-[11px]">fire_at</code>, then return to{" "}
                  <strong className="text-white/80">Needs your response</strong>.
                </p>
              </div>
              <ul className="space-y-4">
                {snoozed.map((r) => (
                  <li key={r.id}>
                    <ReminderQueueCard
                      r={r}
                      variant="snoozed"
                      onCancelNow={handleCancelNow}
                      onOpenSnooze={requestSnooze}
                      onKeep={handleKeep}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {scheduled.length > 0 ? (
            <section className="space-y-4" aria-labelledby="reminders-scheduled">
              <div>
                <h2 id="reminders-scheduled" className="font-heading text-base font-semibold text-white">
                  Upcoming alerts
                </h2>
                <p className="mt-1 text-sm text-white/55">
                  Scheduled (<strong className="text-white/80">pending</strong>) windows before they surface for
                  action.
                </p>
              </div>
              <ul className="space-y-4">
                {scheduled.map((r) => (
                  <li key={r.id}>
                    <ReminderQueueCard
                      r={r}
                      variant="scheduled"
                      onCancelNow={handleCancelNow}
                      onOpenSnooze={requestSnooze}
                      onKeep={handleKeep}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
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
            <div className="mb-3 flex items-center gap-2">
              <Bell className="h-5 w-5 text-amber-300" aria-hidden />
              <h3 className="font-heading text-lg font-semibold text-white">Escalation: why keep this subscription?</h3>
            </div>
            <p className="text-sm text-white/65">
              This subscription is on <strong className="text-white">renewal escalation tier 2 or higher</strong>{" "}
              (denser pre-bill reminders). You chose <strong className="text-white">Remind later</strong> for{" "}
              <strong className="text-white">{snoozeTarget.merchant}</strong>. Enter at least {ACCOUNTABILITY_MIN}{" "}
              characters — the API rejects snooze without it for escalated cycles.
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
                  const ok = window.confirm(
                    "Close without snoozing? On escalation tier, the reminder stays until you submit a reason or choose cancel / keep."
                  );
                  if (!ok) return;
                  setSnoozeTarget(null);
                  setSnoozeReason("");
                  setReasonError("");
                }}
                className="flex-1 rounded-xl border border-white/15 py-3 text-sm font-semibold text-white/80 hover:bg-white/[0.06]"
              >
                Not now
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
