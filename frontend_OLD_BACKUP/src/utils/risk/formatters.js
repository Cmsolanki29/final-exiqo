/**
 * formatters — lightweight display helpers shared across risk UI.
 */

export function fmtPercent(val, decimals = 0) {
  if (val == null || isNaN(val)) return "—";
  return `${(val * 100).toFixed(decimals)}%`;
}

export function fmtScore(val) {
  if (val == null || isNaN(val)) return "—";
  return Number(val).toFixed(3);
}

export function fmtRiskScore(val) {
  if (val == null || isNaN(val)) return "—";
  const n = parseFloat(val);
  return `${(n * 100).toFixed(0)}`;
}

export function fmtRelativeTime(date) {
  if (!date) return "";
  const d = new Date(date);
  if (isNaN(d.getTime())) return "";
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  // Future date (seeded data can have dates beyond today)
  if (diff < 0) {
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  }
  if (diff < 60)          return `${diff}s ago`;
  if (diff < 3600)        return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)       return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 30)  return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtCurrency(amount, currency = "INR") {
  if (amount == null || isNaN(amount)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}
