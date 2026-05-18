/**
 * Shared renewal reminder labels: T-15 / T-10 / T-3 cadence + Tier 1 / Tier 2.
 * Use everywhere reminders are shown (Smart Reminders, hub banner, notifications).
 */

export const REMINDER_CADENCE_DAYS = {
  t20: 20,
  t15: 15,
  t10: 10,
  t7: 7,
  t5: 5,
  t3: 3,
  t2: 2,
  t1: 1,
};

export function reminderWindowLabel(reminderType) {
  const k = String(reminderType || "").toLowerCase();
  const days = REMINDER_CADENCE_DAYS[k];
  if (days != null) {
    return `${days} day${days === 1 ? "" : "s"} before your renewal charge`;
  }
  return reminderType ? String(reminderType).toUpperCase() : "Renewal";
}

export function reminderShortTag(reminderType) {
  const k = String(reminderType || "").toLowerCase();
  const days = REMINDER_CADENCE_DAYS[k];
  if (days != null) return `T-${days}`;
  return (reminderType || "—").toUpperCase();
}

export function cadenceBadgeClass(reminderType) {
  const k = String(reminderType || "").toLowerCase();
  const days = REMINDER_CADENCE_DAYS[k];
  if (days == null) return "border-white/15 bg-white/[0.06] text-white/70";
  if (days <= 1) return "border-rose-500/40 bg-rose-500/20 text-rose-100";
  if (days <= 3) return "border-orange-500/35 bg-orange-500/15 text-orange-100";
  if (days <= 7) return "border-amber-500/35 bg-amber-500/15 text-amber-100";
  if (days <= 10) return "border-violet-500/40 bg-violet-500/15 text-violet-100";
  return "border-cyan-500/35 bg-cyan-500/15 text-cyan-100";
}

export function subscriptionTierBadge(reminderEscalationTier) {
  const t = Math.max(1, Number(reminderEscalationTier ?? 1));
  if (t >= 3) {
    return {
      label: "Tier 3",
      className: "border-rose-500/40 bg-rose-500/20 text-rose-100",
      title: "Strongest reminders — from 20 days before renewal down to 1 day",
    };
  }
  if (t >= 2) {
    return {
      label: "Tier 2",
      className: "border-amber-500/40 bg-amber-500/20 text-amber-100",
      title: "More reminders — T-15, T-10, T-5, T-2, and T-1 before renewal",
    };
  }
  return {
    label: "Tier 1",
    className: "border-cyan-500/40 bg-cyan-500/20 text-cyan-100",
    title: "First renewal cycle — T-10, T-3, and T-1 before renewal",
  };
}

export function reminderStateLabel(state) {
  const s = String(state || "").toLowerCase();
  if (s === "shown") return "Due now";
  if (s === "pending") return "Scheduled";
  if (s === "snoozed") return "Snoozed";
  if (s === "dismissed") return "Dismissed";
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

export function reminderStatePillClass(state) {
  const s = String(state || "").toLowerCase();
  if (s === "shown") return "bg-rose-500/25 text-rose-100 ring-1 ring-rose-500/30";
  if (s === "pending") return "bg-cyan-500/20 text-cyan-100 ring-1 ring-cyan-500/25";
  if (s === "snoozed") return "bg-violet-500/25 text-violet-100 ring-1 ring-violet-500/30";
  return "bg-white/10 text-white/70 ring-1 ring-white/15";
}

export function urgencyFromFireAt(fireAtIso) {
  if (!fireAtIso) return { label: "Scheduled", badge: "bg-white/10 text-white/80" };
  const h = (new Date(fireAtIso).getTime() - Date.now()) / (1000 * 60 * 60);
  if (h < 24) return { label: "Critical", badge: "bg-rose-500/90 text-white" };
  if (h < 72) return { label: "Urgent", badge: "bg-amber-500/90 text-white" };
  return { label: "Upcoming", badge: "bg-cyan-600/90 text-white" };
}

/** Plain phrase for notifications / subtitles */
export function reminderCadencePhrase(reminderType) {
  const k = String(reminderType || "").toLowerCase();
  const map = {
    t1: "1 day before renewal",
    t2: "2 days before renewal",
    t3: "3 days before renewal",
    t5: "5 days before renewal",
    t7: "7 days before renewal",
    t10: "10 days before renewal",
    t15: "15 days before renewal",
    t20: "20 days before renewal",
  };
  return map[k] || reminderShortTag(reminderType);
}

export function snoozeRequiresAccountability(reminderEscalationTier) {
  return Number(reminderEscalationTier ?? 1) >= 2;
}

/** Canonical cadence + tier per merchant (matches backend REMINDER_SHOWCASE_TARGETS). */
export const SHOWCASE_BY_MERCHANT = [
  ["netflix", "t3", 1],
  ["spotify", "t10", 1],
  ["youtube", "t1", 1],
  ["linkedin", "t15", 2],
  ["chatgpt", "t5", 2],
  ["canva", "t3", 1],
  ["amazon", "t10", 2],
];

function merchantKey(merchant) {
  return String(merchant || "")
    .trim()
    .toLowerCase();
}

/** Apply showcase T-* / Tier labels when API rows are stale or duplicated. */
export function enrichReminderRow(reminder) {
  if (!reminder) return reminder;
  const merchant = merchantKey(reminder.merchant);
  const hit = SHOWCASE_BY_MERCHANT.find(([key]) => merchant.includes(key));
  if (!hit) return reminder;
  const state = String(reminder.state || "").toLowerCase();
  if (state !== "shown" && state !== "snoozed" && state !== "pending") {
    return reminder;
  }
  return {
    ...reminder,
    reminder_type: hit[1],
    reminder_escalation_tier: hit[2],
    escalation_level: hit[2] >= 2 ? 2 : 1,
  };
}

/** One visible card per merchant for the action queue; enriches cadence labels. */
export function normalizeRemindersForDisplay(reminders) {
  const list = Array.isArray(reminders) ? reminders : [];
  const enriched = list.map((r) => enrichReminderRow(r));
  const shownByMerchant = new Map();
  const out = [];

  for (const r of enriched) {
    const state = String(r.state || "").toLowerCase();
    const mkey = merchantKey(r.merchant) || `sub-${r.subscription_id}`;
    if (state === "shown") {
      if (shownByMerchant.has(mkey)) continue;
      shownByMerchant.set(mkey, true);
    }
    out.push(r);
  }
  return out;
}
