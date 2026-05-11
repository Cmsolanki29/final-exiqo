import React, { useEffect, useState } from "react";
import { getFraudShieldAlerts, postFraudShieldAlertAction } from "../../services/api";
import { useToast } from "../common/Toast";
import { EmptyState } from "../common/EmptyState";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";

const fmt = (n) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(n || 0));

const patternTitle = (p) => (p ? p.replace(/_/g, " ") : "Fraud alert");

const severityFromScore = (s) => {
  if (s >= 85) return { label: "CRITICAL", cls: "crit" };
  if (s >= 60) return { label: "HIGH", cls: "high" };
  if (s >= 30) return { label: "MEDIUM", cls: "med" };
  return { label: "LOW", cls: "low" };
};

const SEVERITY_FILTERS = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SEVERITY_COLORS = {
  CRITICAL: "bg-red-900/60 text-red-300 border-red-700",
  HIGH: "bg-orange-900/60 text-orange-300 border-orange-700",
  MEDIUM: "bg-yellow-900/60 text-yellow-300 border-yellow-700",
  LOW: "bg-gray-800 text-gray-400 border-gray-600",
};

const getSeverityFromAlert = (a) => {
  if (a.severity) return a.severity;
  const s = a.risk_score || 0;
  if (s >= 85) return "CRITICAL";
  if (s >= 60) return "HIGH";
  if (s >= 30) return "MEDIUM";
  return "LOW";
};

const FraudAlertsList = ({ userId, onAlertsChanged }) => {
  const { showToast } = useToast();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [acting, setActing] = useState(null);
  const [severityFilter, setSeverityFilter] = useState("ALL");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getFraudShieldAlerts(userId);
      setAlerts(data.alerts || []);
    } catch (e) {
      setError(e.message || "Failed to load alerts");
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [userId]);

  const onAction = async (alertId, action) => {
    setActing(alertId);
    try {
      await postFraudShieldAlertAction(userId, alertId, action);
      await load();
      if (onAlertsChanged) onAlertsChanged();
      if (action === "REPORTED") {
        showToast("Fraud reported — note details on National Cyber Crime Portal ✅", "success");
      }
    } catch (e) {
      setError(e.message || "Action failed");
    } finally {
      setActing(null);
    }
  };

  if (loading) {
    return (
      <div className="glass-card fraud-alerts feature-card">
        <p className="muted small" style={{ marginBottom: 12 }}>
          Loading your fraud alerts…
        </p>
        <SkeletonCard lines={4} height={160} />
      </div>
    );
  }

  if (error && !alerts.length) {
    return (
      <div className="glass-card fraud-alerts feature-card">
        <ErrorCard message={error} onRetry={load} />
      </div>
    );
  }

  return (
    <div className="fraud-alerts glass-card">
      <div className="panel-head">
        <h3>📊 My fraud alerts</h3>
        <p className="muted small">
          <a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer">
            cybercrime.gov.in
          </a>{" "}
          · 1930
        </p>
      </div>

      {/* Severity filter chips */}
      {alerts.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4 mt-2">
          {SEVERITY_FILTERS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSeverityFilter(s)}
              className={`px-3 py-1 rounded-full text-sm font-medium border transition-all ${
                severityFilter === s
                  ? "bg-red-600 text-white border-red-600"
                  : "bg-transparent text-gray-400 border-gray-600 hover:border-red-400 hover:text-red-300"
              }`}
            >
              {s}
            </button>
          ))}
          {severityFilter !== "ALL" && (
            <span className="text-xs text-gray-500 self-center ml-1">
              — {alerts.filter((a) => getSeverityFromAlert(a) === severityFilter).length} alert
              {alerts.filter((a) => getSeverityFromAlert(a) === severityFilter).length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}

      {!alerts.length ? (
        <EmptyState
          icon="🛡️"
          title="No fraud attempts logged"
          subtitle="Stay vigilant — run a transaction check anytime for live scoring."
        />
      ) : (
        <div className="fraud-alert-grid">
          {(severityFilter === "ALL"
            ? alerts
            : alerts.filter((a) => getSeverityFromAlert(a) === severityFilter)
          ).map((a) => {
            const alertSeverity = getSeverityFromAlert(a);
            const sev = severityFromScore(a.risk_score);
            const pending = a.user_action === "PENDING";
            return (
              <article key={a.id} className={`fraud-alert-card ${sev.cls}`}>
                <header>
                  <span className={`fraud-sev ${sev.cls}`}>
                    {sev.label === "CRITICAL" ? "🔴" : sev.label === "HIGH" ? "🟡" : "⚪"}{" "}
                    {sev.label} — {patternTitle(a.pattern_matched)}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold border ml-2 ${SEVERITY_COLORS[alertSeverity] || SEVERITY_COLORS.MEDIUM}`}>
                    {alertSeverity}
                  </span>
                </header>
                <p className="fraud-alert-payee mono">{patternTitle(a.pattern_matched)}</p>
                <p className="muted small">
                  {a.created_at
                    ? new Date(a.created_at).toLocaleString("en-IN", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })
                    : ""}
                </p>
                <p className="fraud-alert-amt">
                  At risk / logged: {fmt(a.amount_at_risk)}
                  {a.money_saved > 0 && (
                    <span className="amount-positive"> · Money saved {fmt(a.money_saved)}</span>
                  )}
                </p>
                {a.hinglish_explanation && (
                  <blockquote className="fraud-alert-quote">{a.hinglish_explanation}</blockquote>
                )}
                <p className="fraud-alert-status">
                  Status:{" "}
                  {pending ? (
                    <span className="amount-negative">⚠️ PENDING — take action</span>
                  ) : a.user_action === "BLOCKED" ? (
                    <span className="amount-positive">✅ BLOCKED by FraudShield</span>
                  ) : a.user_action === "ALLOWED" ? (
                    <span>Allowed (paid)</span>
                  ) : (
                    <span>Reported</span>
                  )}
                </p>
                {pending && (
                  <div className="fraud-alert-actions">
                    <button
                      type="button"
                      className="btn-outline"
                      disabled={acting === a.id}
                      onClick={() => onAction(a.id, "ALLOWED")}
                    >
                      ✅ It was safe
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      disabled={acting === a.id}
                      onClick={() => onAction(a.id, "REPORTED")}
                    >
                      🚨 Was fraud — report
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={acting === a.id}
                      onClick={() => onAction(a.id, "BLOCKED")}
                    >
                      🛡️ I blocked it
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default FraudAlertsList;
