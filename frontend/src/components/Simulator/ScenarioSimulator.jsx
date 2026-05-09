import React, { useState } from "react";
import { apiUtils, simulateScenario } from "../../services/api";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";

const presets = [
  "Food spending +30%",
  "Shopping +50%",
  "Start Rs.5000 SIP",
  "Salary cut 20%",
  "Add Rs.15000 rent",
];

const ScenarioSimulator = ({ userId, month, year }) => {
  const [scenario, setScenario] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    if (!scenario.trim()) return;
    setLoading(true);
    setError("");
    try {
      const data = await simulateScenario(userId, scenario, month, year);
      setResult(data);
    } catch (err) {
      setError(err.message || "Simulation failed");
    } finally {
      setLoading(false);
    }
  };

  const verdictClass = String(result?.verdict || "").toLowerCase();

  return (
    <section className="glass-card">
      <div className="panel-head">
        <h3>Scenario Simulator</h3>
      </div>

      <div className="preset-wrap">
        {presets.map((label) => (
          <button key={label} type="button" className="chip-btn" onClick={() => setScenario(label)}>
            {label}
          </button>
        ))}
      </div>

      <div className="sim-input-row">
        <input
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          placeholder="Or describe your scenario..."
        />
        <button type="button" onClick={run} disabled={loading || !scenario.trim()}>
          ?? Simulate
        </button>
      </div>

      {loading && (
        <div style={{ marginTop: 12 }}>
          <p className="muted small" style={{ marginBottom: 12 }}>
            Running scenario against your profile…
          </p>
          <SkeletonCard lines={4} height={140} />
        </div>
      )}
      {error && (
        <div style={{ marginTop: 12 }}>
          <ErrorCard message={error} onRetry={() => scenario.trim() && run()} />
        </div>
      )}

      {result && !loading && (
        <article className="simulation-result">
          <h4>SCENARIO: {result.scenario_title || scenario}</h4>
          <div className="sim-grid">
            <p>
              Savings: {apiUtils.formatINR(result.current_state?.monthly_savings || 0)} ? {apiUtils.formatINR(result.projected_state?.monthly_savings || 0)}
            </p>
            <p>
              Health: {result.current_state?.health_score || 0}/100 ? {result.projected_state?.health_score || 0}/100
            </p>
            <p>
              Rate: {(result.current_state?.savings_rate || 0).toFixed?.(1) || result.current_state?.savings_rate || 0}% ? {(result.projected_state?.savings_rate || 0).toFixed?.(1) || result.projected_state?.savings_rate || 0}%
            </p>
            <p>Annual Impact: {apiUtils.formatINR(result.impact?.annual_impact || 0)}</p>
          </div>
          <div className={`verdict-pill ${verdictClass}`}>Verdict: {result.verdict}</div>
          <p>{result.advice}</p>
          {(result.alternatives || []).length > 0 && (
            <ul>
              {result.alternatives.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          )}
        </article>
      )}
    </section>
  );
};

export default ScenarioSimulator;
