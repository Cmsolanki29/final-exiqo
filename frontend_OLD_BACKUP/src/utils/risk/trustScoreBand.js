/**
 * trustScoreBand — maps a 0-1000 trust score to a visual band.
 */

export function trustScoreBand(score) {
  if (score >= 800) return { label: "Thriving",    color: "#10b981", bg: "#ecfdf5", grade: "A" };
  if (score >= 600) return { label: "Healthy",     color: "#3b82f6", bg: "#eff6ff", grade: "B" };
  if (score >= 400) return { label: "Coping",      color: "#f59e0b", bg: "#fffbeb", grade: "C" };
  return              { label: "Vulnerable",  color: "#ef4444", bg: "#fef2f2", grade: "D" };
}
