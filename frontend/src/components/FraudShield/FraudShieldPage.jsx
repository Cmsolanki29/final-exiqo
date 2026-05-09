import React, { useCallback, useEffect, useState } from "react";
import { getFraudShieldAnalyze, getFraudShieldStats } from "../../services/api";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";
import FraudAlertsList from "./FraudAlertsList";
import FraudEducation from "./FraudEducation";
import FraudStats from "./FraudStats";
import TransactionChecker from "./TransactionChecker";

const SUBTABS = [
  { id: "check", label: "Check Transaction", icon: "🔍" },
  { id: "alerts", label: "My Alerts", icon: "📊" },
  { id: "education", label: "Fraud Education", icon: "📚" },
  { id: "stats", label: "My Stats", icon: "📈" },
];

const badgeEmoji = (badge) => {
  if (badge === "VIGILANT") return "🛡️";
  if (badge === "CAREFUL") return "🛡️";
  if (badge === "AT_RISK") return "⚠️";
  if (badge === "VULNERABLE") return "🚨";
  return "🛡️";
};

const FraudShieldPage = ({ userId, userName }) => {
  const [sub, setSub] = useState("check");
  const [stats, setStats] = useState(null);
  const [analyze, setAnalyze] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [alertsTick, setAlertsTick] = useState(0);

  const displayName = userName || "User";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setStats(null);
    setAnalyze(null);
    try {
      const s = await getFraudShieldStats(userId);
      setStats(s);
    } catch (e) {
      setError(e.message || "Failed to load stats");
    }
    try {
      const a = await getFraudShieldAnalyze(userId);
      setAnalyze(a);
    } catch {
      setAnalyze(null);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load, alertsTick]);

  const onAlertsChanged = () => setAlertsTick((t) => t + 1);

  const safetyScore = stats?.safety_score ?? 0;
  const badge = stats?.badge ?? "CAREFUL";
  const blocked = stats?.threats_blocked ?? 0;
  const saved = stats?.money_saved_total ?? 0;

  return (
    <div className="fraud-shield-page fade-in">
      <header className="fraud-shield-hero glass-card">
        <div>
          <h2 className="fraud-shield-title">
            <span className="fraud-shield-icon">🛡️</span> SmartSpend FraudShield
          </h2>
          <p className="fraud-shield-tagline">
            Protecting <strong>you</strong> from financial fraud
          </p>
          {analyze && !loading && (
            <p className="muted small">
              {analyze.fraud_alerts_found} alerts on file · {analyze.total_transactions_analyzed} transactions scanned
              (30d)
            </p>
          )}
        </div>
        <div className="fraud-shield-helpline">
          <a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer">
            cybercrime.gov.in
          </a>
          <span className="muted"> · National Helpline: 1930</span>
        </div>
      </header>

      <nav className="fraud-subtabs" aria-label="FraudShield sections">
        {SUBTABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`fraud-subtab ${sub === t.id ? "active" : ""}`}
            onClick={() => setSub(t.id)}
          >
            <span>{t.icon}</span> {t.label}
          </button>
        ))}
      </nav>

      <section className="glass-card fraud-shield-summary-bar feature-card">
        {loading ? (
          <div>
            <p className="muted small" style={{ marginBottom: 10 }}>
              Loading protection stats…
            </p>
            <SkeletonCard lines={3} height={72} />
          </div>
        ) : error ? (
          <ErrorCard message={error} onRetry={load} />
        ) : (
          <>
            <div>
              <div className="muted small">Safety Score</div>
              <div className="fraud-score-line">
                <strong>{safetyScore}/100</strong>
                <span className="fraud-badge-pill">
                  {badgeEmoji(badge)} {badge}
                </span>
              </div>
              <div className="fraud-score-bar" aria-hidden>
                <span style={{ width: `${Math.min(100, safetyScore)}%` }} />
              </div>
            </div>
            <div className="fraud-summary-metrics">
              <div>
                <span className="muted small">Threats blocked</span>
                <strong>{blocked}</strong>
              </div>
              <div>
                <span className="muted small">Money saved</span>
                <strong className="amount-positive">
                  {new Intl.NumberFormat("en-IN", {
                    style: "currency",
                    currency: "INR",
                    maximumFractionDigits: 0,
                  }).format(saved)}
                </strong>
              </div>
            </div>
          </>
        )}
      </section>

      {sub === "check" && (
        <TransactionChecker
          userId={userId}
          userName={displayName}
          onReportSuccess={onAlertsChanged}
        />
      )}
      {sub === "alerts" && (
        <FraudAlertsList userId={userId} onAlertsChanged={onAlertsChanged} />
      )}
      {sub === "education" && <FraudEducation />}
      {sub === "stats" && <FraudStats userId={userId} />}
    </div>
  );
};

export default FraudShieldPage;
