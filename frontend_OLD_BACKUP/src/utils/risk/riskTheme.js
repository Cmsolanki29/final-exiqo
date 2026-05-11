/**
 * riskTheme — maps a risk action string to visual properties.
 * action: "allow" | "review" | "challenge" | "block" | null
 */

export const RISK_ACTIONS = {
  allow: {
    label:    "Safe",
    color:    "#10b981",
    bg:       "#ecfdf5",
    border:   "#6ee7b7",
    iconName: "ShieldCheck",
    chipClass: "risk-chip-safe",
  },
  review: {
    label:    "Review",
    color:    "#d97706",
    bg:       "#fffbeb",
    border:   "#fcd34d",
    iconName: "Eye",
    chipClass: "risk-chip-review",
  },
  challenge: {
    label:    "Verify",
    color:    "#ea580c",
    bg:       "#fff7ed",
    border:   "#fdba74",
    iconName: "AlertTriangle",
    chipClass: "risk-chip-challenge",
  },
  block: {
    label:    "Blocked",
    color:    "#dc2626",
    bg:       "#fef2f2",
    border:   "#fca5a5",
    iconName: "ShieldOff",
    chipClass: "risk-chip-block",
  },
};

export function riskTheme(action) {
  const key = (action || "").toLowerCase();
  return RISK_ACTIONS[key] || {
    label:    "Unknown",
    color:    "#6b7280",
    bg:       "#f3f4f6",
    border:   "#d1d5db",
    iconName: "Shield",
    chipClass: "risk-chip-neutral",
  };
}
