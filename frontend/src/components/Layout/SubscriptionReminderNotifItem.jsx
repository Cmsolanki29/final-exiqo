import React, { useState } from "react";
import { AlertCircle, Bell, Loader2 } from "lucide-react";
import { postSubscriptionReminderAction } from "../../services/api";
import {
  enrichReminderRow,
  reminderShortTag,
  snoozeRequiresAccountability,
  subscriptionTierBadge,
} from "../../utils/reminderBadges";

const ACCOUNTABILITY_MIN = 10;

/**
 * Tier 2+ renewal alerts stay in the bell until cancel / keep / remind-later with reason.
 */
export default function SubscriptionReminderNotifItem({ n, userId, onResolved, onOpenReminders }) {
  const reminder = enrichReminderRow(n._reminder || {});
  const tier = Number(reminder.reminder_escalation_tier ?? 1);
  const locked = Boolean(n._locked) || snoozeRequiresAccountability(tier);
  const cadence = reminderShortTag(reminder.reminder_type);
  const tierMeta = subscriptionTierBadge(tier);
  const [expanded, setExpanded] = useState(locked);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [busy, setBusy] = useState(false);

  const ts = n.created_at
    ? new Date(n.created_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })
    : "";

  const runAction = async (action, accountabilityReason) => {
    if (!userId || !reminder.id) return;
    setBusy(true);
    setReasonError("");
    try {
      const payload =
        action === "remind_later"
          ? { action, accountability_reason: accountabilityReason || undefined }
          : { action };
      await postSubscriptionReminderAction(userId, reminder.id, payload);
      onResolved?.(n.id);
      window.dispatchEvent(new CustomEvent("smartspend:reminders-changed"));
    } catch (e) {
      setReasonError(e?.message || "Could not update reminder");
    } finally {
      setBusy(false);
    }
  };

  const submitSnoozeWithReason = async () => {
    const trimmed = reason.trim();
    if (trimmed.length < ACCOUNTABILITY_MIN) {
      setReasonError(`Enter at least ${ACCOUNTABILITY_MIN} characters explaining why you are keeping it.`);
      return;
    }
    await runAction("remind_later", trimmed);
  };

  return (
    <div
      className={`rounded-xl border p-3 ${
        locked
          ? "border-amber-500/40 bg-amber-500/10 ring-1 ring-inset ring-amber-500/25"
          : "border-rose-500/25 bg-rose-500/10 ring-1 ring-inset ring-white/10"
      }`}
    >
      <div className="flex gap-2">
        <Bell className={`mt-0.5 h-4 w-4 shrink-0 ${locked ? "text-amber-300" : "text-rose-300"}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${tierMeta.className}`}
            >
              {cadence} · {tierMeta.label}
            </span>
            {locked ? (
              <span className="rounded-full bg-amber-500/25 px-2 py-0.5 text-[9px] font-bold uppercase text-amber-100">
                Action required
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-xs font-semibold text-white">{n.title}</p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-gray-400">{n.body}</p>
          <p className="mt-1 text-[10px] text-gray-600">{ts}</p>
          {locked ? (
            <p className="mt-2 text-[11px] leading-relaxed text-amber-100/90">
              Stays in notifications until you cancel, keep, or snooze with a reason (min {ACCOUNTABILITY_MIN}{" "}
              characters). Cannot be dismissed with “mark read”.
            </p>
          ) : null}
        </div>
      </div>

      {locked && expanded ? (
        <div className="mt-3 space-y-2 border-t border-amber-500/20 pt-3">
          <label className="block text-[10px] font-semibold uppercase tracking-wide text-white/45">
            Why are you keeping {reminder.merchant || "this subscription"}?
          </label>
          <textarea
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              setReasonError("");
            }}
            rows={3}
            disabled={busy}
            className="w-full resize-none rounded-lg border border-white/15 bg-black/30 px-2.5 py-2 text-xs text-white placeholder:text-white/30 focus:border-amber-400/50 focus:outline-none"
            placeholder="e.g. I need this for job applications every week…"
          />
          {reasonError ? (
            <p className="flex items-start gap-1.5 text-[11px] text-rose-300">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              {reasonError}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              disabled={busy}
              onClick={() => void runAction("cancel_now")}
              className="rounded-lg border border-rose-500/40 bg-rose-500/15 px-2.5 py-1.5 text-[10px] font-bold text-rose-100 hover:bg-rose-500/25 disabled:opacity-50"
            >
              Cancel now
            </button>
            <button
              type="button"
              disabled={busy || reason.trim().length < ACCOUNTABILITY_MIN}
              onClick={() => void submitSnoozeWithReason()}
              className="rounded-lg border border-amber-500/40 bg-amber-500/20 px-2.5 py-1.5 text-[10px] font-bold text-amber-50 hover:bg-amber-500/30 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Snooze 24h (with reason)"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void runAction("keep")}
              className="rounded-lg border border-emerald-500/35 bg-emerald-500/15 px-2.5 py-1.5 text-[10px] font-bold text-emerald-100 hover:bg-emerald-500/25 disabled:opacity-50"
            >
              Keep subscription
            </button>
          </div>
        </div>
      ) : null}

      {!locked ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          <button
            type="button"
            disabled={busy}
            onClick={() => void runAction("cancel_now")}
            className="rounded-lg border border-rose-500/35 px-2 py-1 text-[10px] font-semibold text-rose-100"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void runAction("remind_later")}
            className="rounded-lg border border-white/15 px-2 py-1 text-[10px] font-semibold text-white/80"
          >
            Snooze 24h
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => typeof onOpenReminders === "function" ? onOpenReminders() : undefined}
            className="rounded-lg border border-cyan-500/30 px-2 py-1 text-[10px] font-semibold text-cyan-100"
          >
            Open reminders
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-2 text-[10px] font-semibold text-amber-200/90 underline"
        >
          {expanded ? "Hide form" : "Respond here"}
        </button>
      )}
    </div>
  );
}
