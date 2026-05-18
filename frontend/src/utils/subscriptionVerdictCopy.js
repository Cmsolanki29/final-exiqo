/**
 * Plain-English labels for subscription intelligence (verdicts, usage, migrations).
 * Also maps legacy technical strings from older API/DB rows.
 */

export const VERDICT_BUCKETS_UI = [
  {
    key: "thriving",
    title: "Worth keeping",
    hint: "You use these regularly",
    IconKey: "TrendingUp",
    accent: "emerald",
  },
  {
    key: "declining",
    title: "Use is dropping",
    hint: "Worth reviewing before the next bill",
    IconKey: "TrendingDown",
    accent: "amber",
  },
  {
    key: "dormant",
    title: "Barely used",
    hint: "You rarely open these apps",
    IconKey: "AlertTriangle",
    accent: "orange",
  },
  {
    key: "upgrade_recommended",
    title: "Upgrade may help",
    hint: "You use the free version a lot",
    IconKey: "Zap",
    accent: "purple",
  },
];

const VERDICT_LABELS = {
  thriving: "Worth keeping",
  declining: "Use is dropping",
  dormant: "Barely used",
  dead: "Not being used",
  upgrade: "Upgrade may help",
  upgrade_recommended: "Upgrade may help",
};

const LEGACY_REASON_MAP = [
  [/healthy usage pattern vs prior month/i, "You use this regularly — about the same or more than last month."],
  [/less than 2 sessions\/month in recent window/i, "You opened this fewer than 2 times in the last 30 days."],
  [
    /usage down (\d+)% vs prior 30 days\.\s*approx\. waste flagged:\s*rs\.(\d+)\/mo/i,
    "You used this $1% less last month. You could save about ₹$2 per month if you cancel.",
  ],
  [/usage down (\d+)% vs prior 30 days/i, "You used this $1% less than the previous month."],
  [/no meaningful usage in 60\+ days/i, "Almost no usage in the last 60 days — you may be paying for nothing."],
  [/no device link yet/i, "Link your phone usage in Device Intelligence to get personalised advice."],
  [/migrated toward (.+)/i, "You seem to be using $1 more instead."],
  [
    /(\d+)h\/month in-app - pro tier likely roi-positive/i,
    "You spend about $1 hours a month here — a paid plan may be worth it.",
  ],
  [/approx\. waste flagged:\s*rs\.(\d+)\/mo/i, "You could save about ₹$1 per month if you cancel."],
];

export function verdictDisplayLabel(verdictKey) {
  const k = String(verdictKey || "").toLowerCase();
  return VERDICT_LABELS[k] || k.replace(/_/g, " ") || "Subscription";
}

export function humanizeVerdictReason(text, verdictKey) {
  const raw = String(text || "").trim();
  if (!raw) {
    const k = String(verdictKey || "").toLowerCase();
    if (k === "thriving") return "You use this regularly.";
    if (k === "declining") return "Your usage dropped compared to last month.";
    if (k === "dormant") return "You rarely open this app.";
    if (k === "dead") return "We did not see meaningful usage recently.";
    if (k === "upgrade" || k === "upgrade_recommended") return "You use this app a lot — a paid plan might help.";
    return "Based on your recent app usage.";
  }
  for (const [pattern, replacement] of LEGACY_REASON_MAP) {
    const m = raw.match(pattern);
    if (m) {
      let out = String(replacement);
      m.slice(1).forEach((cap, i) => {
        const token = `$${i + 1}`;
        out = out.split(token).join(String(cap));
      });
      return out;
    }
  }
  return String(raw)
    .replace(/\bvs prior 30 days\b/gi, "compared to last month")
    .replace(/\bApprox\. waste flagged\b/gi, "Possible savings")
    .replace(/\bRs\./g, "₹")
    .replace(/\broi-positive\b/gi, "good value");
}

export function formatUsage30d(hours) {
  const h = Number(hours);
  if (Number.isNaN(h)) return null;
  if (h < 0.5) return "Less than 30 minutes in the last 30 days";
  if (h < 2) return `About ${Math.round(h * 60)} minutes in the last 30 days`;
  return `About ${h.toFixed(1)} hours in the last 30 days`;
}

export function humanizeMigration(m) {
  if (!m) return m;
  return {
    ...m,
    title: m.title?.includes("migration detected")
      ? "You switched apps"
      : m.title || "App switch",
    description: m.description
      ? String(m.description)
          .replace(/^You shifted time from/i, "Your time moved from")
          .replace(/within (\w+)\.$/i, " (same type of app: $1).")
      : m.description,
    recommendation: m.recommendation
      ? String(m.recommendation)
          .replace(/^If the new habit stuck, cancel/i, "If you prefer the new app, cancel")
          .replace(/to save\s+Rs\./i, "to save about ₹")
      : m.recommendation,
  };
}

export function humanizeInsightType(type) {
  const t = String(type || "").toLowerCase();
  if (t.includes("migration")) return "App switch";
  if (t.includes("substitution")) return "Alternative app";
  if (t.includes("verdict")) return "Subscription check";
  return (type || "Insight").replace(/_/g, " ");
}
