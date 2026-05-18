import { CASE_REF } from "./constants";

/** Demo CyberSafe notifications merged into the app notification center */
export const CYBERSAFE_NOTIFICATIONS = [
  {
    id: "cs-fraud-alert",
    type: "cybersafe_fraud",
    title: "",
    body: "Suspicious transaction detected — ₹12,500 UPI payment flagged. Report to Cybercell within 24 hrs for best chance of recovery.",
    actionLabel: "Report Now",
    actionTarget: "report",
    is_read: false,
    created_at: new Date().toISOString(),
  },
  {
    id: "cs-case-update",
    type: "cybersafe_case",
    title: "",
    body: `Bank account freeze requested for Case #${CASE_REF}. Cybercell is actively tracking the scammer.`,
    is_read: false,
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "cs-reminder",
    type: "cybersafe_reminder",
    title: "",
    body: `12 hours remaining in your 24-hr window — Case #${CASE_REF} needs your attention.`,
    is_read: false,
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
];

export const CYBERSAFE_NOTIFICATION_IDS = CYBERSAFE_NOTIFICATIONS.map((n) => n.id);

export function mergeCyberSafeNotifications(apiNotifications = [], { includeCyberSafe = true } = {}) {
  const apiIds = new Set((apiNotifications || []).map((n) => n.id));
  const extras = includeCyberSafe
    ? CYBERSAFE_NOTIFICATIONS.filter((n) => !apiIds.has(n.id))
    : [];
  return [...extras, ...(apiNotifications || [])];
}
