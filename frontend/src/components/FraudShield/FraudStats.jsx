import React, { useEffect, useState } from "react";
import { getFraudShieldStats } from "../../services/api";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";

const fmt = (n) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(n || 0));

const FraudStats = ({ userId }) => {
  const [s, setS] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErr("");
      try {
        const data = await getFraudShieldStats(userId);
        if (!cancelled) setS(data);
      } catch (e) {
        if (!cancelled) setErr(e.message || "Failed to load stats");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const reload = () => {
    setLoading(true);
    setErr("");
    (async () => {
      try {
        const data = await getFraudShieldStats(userId);
        setS(data);
      } catch (e) {
        setErr(e.message || "Failed to load stats");
      } finally {
        setLoading(false);
      }
    })();
  };

  if (loading) {
    return (
      <div className="glass-card fraud-stats feature-card">
        <p className="muted small" style={{ marginBottom: 12 }}>
          Loading your FraudShield stats…
        </p>
        <SkeletonCard lines={4} height={140} />
      </div>
    );
  }

  if (err || !s) {
    return (
      <div className="glass-card fraud-stats feature-card">
        <ErrorCard message={err || "No data"} onRetry={reload} />
      </div>
    );
  }

  const avgLoss = 45000;
  const userLoss = s.money_lost_total || 0;
  const belowAvg = userLoss < avgLoss;

  return (
    <div className="fraud-stats glass-card">
      <h3>📊 Your fraud protection report</h3>
      <div className="fraud-stats-grid">
        <div>
          <div className="muted small">🛡️ Attempts logged</div>
          <strong>{s.fraud_attempts_detected}</strong>
          <div className="muted small">Threats blocked: {s.threats_blocked ?? 0}</div>
        </div>
        <div>
          <div className="muted small">💰 Saved</div>
          <strong className="amount-positive">{fmt(s.money_saved_total)}</strong>
        </div>
        <div>
          <div className="muted small">😢 Lost (allowed)</div>
          <strong className="amount-negative">{fmt(s.money_lost_total)}</strong>
        </div>
      </div>

      <div className="fraud-stats-badge">
        <div className="muted small">Safety badge</div>
        <strong>
          🛡️ {s.badge} — {s.safety_score}/100
        </strong>
        <div className="fraud-score-bar wide" aria-hidden>
          <span style={{ width: `${Math.min(100, s.safety_score)}%` }} />
        </div>
      </div>

      <p>
        <strong>Most common threat:</strong> {s.most_common_fraud_type}
      </p>
      <p>
        <strong>Fraud-free days (since last loss):</strong> {s.fraud_free_days} days ✅
      </p>

      <div className="fraud-stats-compare">
        <p className="muted small">Compared to average Indian user (illustrative):</p>
        <p>Average loss to fraud (estimate): {fmt(avgLoss)}/year</p>
        <p>
          Your recorded loss: {fmt(userLoss)} {belowAvg ? "(below that estimate ✅)" : ""}
        </p>
      </div>

      <div className="fraud-badge-legend">
        <strong>Safety badges</strong>
        <ul>
          <li>
            <strong>VIGILANT</strong> → fewer losses, strong blocks
          </li>
          <li>
            <strong>CAREFUL</strong> → some alerts, limited losses
          </li>
          <li>
            <strong>AT_RISK</strong> → multiple risky events
          </li>
          <li>
            <strong>VULNERABLE</strong> → high fraud activity pattern
          </li>
        </ul>
      </div>

      <p className="muted small">
        <a href={s.cybercrime_url} target="_blank" rel="noreferrer">
          {s.cybercrime_url}
        </a>{" "}
        · {s.helpline}
      </p>
    </div>
  );
};

export default FraudStats;
