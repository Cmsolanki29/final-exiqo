import React from "react";
import {
  cadenceBadgeClass,
  enrichReminderRow,
  reminderCadencePhrase,
  reminderShortTag,
  reminderStateLabel,
  reminderStatePillClass,
  reminderWindowLabel,
  subscriptionTierBadge,
  urgencyFromFireAt,
} from "../../utils/reminderBadges";

/**
 * CRITICAL + T-10 + Tier 1 + Due now — same row on every reminder surface.
 */
export default function ReminderBadges({
  reminder,
  showUrgency = true,
  showState = true,
  className = "",
}) {
  const r = enrichReminderRow(reminder || {});
  const subTier = subscriptionTierBadge(r.reminder_escalation_tier);
  const urgency = urgencyFromFireAt(r.fire_at);

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      {showUrgency ? (
        <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${urgency.badge}`}>
          {urgency.label}
        </span>
      ) : null}
      <span
        className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase ${cadenceBadgeClass(r.reminder_type)}`}
        title={reminderWindowLabel(r.reminder_type)}
      >
        {reminderShortTag(r.reminder_type)}
      </span>
      <span
        className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase ${subTier.className}`}
        title={subTier.title}
      >
        {subTier.label}
      </span>
      {showState && r.state ? (
        <span
          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${reminderStatePillClass(r.state)}`}
        >
          {reminderStateLabel(r.state)}
        </span>
      ) : null}
    </div>
  );
}

export function ReminderCadenceLine({ reminder }) {
  const r = enrichReminderRow(reminder || {});
  const tier = subscriptionTierBadge(r.reminder_escalation_tier);
  return (
    <p className="text-xs text-white/55">
      {reminderCadencePhrase(r.reminder_type)} · {tier.label}
    </p>
  );
}
