import React, { useEffect, useState } from "react";
import { getFraudShieldGlobalSummary } from "../../services/api";
import { SkeletonCard } from "../common/SkeletonCard";

const fmt = (n) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(n || 0));

const FraudShieldSummary = ({ onViewDetails }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getFraudShieldGlobalSummary();
        if (!cancelled) setStats(data);
      } catch {
        if (!cancelled) setStats(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const blocked = stats?.threats_blocked_total ?? 0;
  const saved = stats?.money_saved_total_all_users ?? 0;

  return (
    <section className="glass-card fraud-dash-widget hover-glow">
      <div className="panel-head">
        <h3>🛡️ FraudShield status</h3>
      </div>
      {loading ? (
        <div>
          <p className="muted small" style={{ marginBottom: 10 }}>
            Loading FraudShield snapshot…
          </p>
          <SkeletonCard lines={2} height={72} />
        </div>
      ) : (
        <>
          <p className="fraud-dash-line">
            <strong>{blocked}</strong> threats blocked · <strong>{fmt(saved)}</strong> saved
          </p>
          <button type="button" className="btn-outline fraud-dash-link" onClick={onViewDetails}>
            View details →
          </button>
        </>
      )}
      <p className="muted small" style={{ marginTop: 8 }}>
        <a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer">
          cybercrime.gov.in
        </a>{" "}
        · 1930
      </p>
    </section>
  );
};

export default FraudShieldSummary;
