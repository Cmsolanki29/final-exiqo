import React, { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCcw } from "lucide-react";
import { getInsights } from "../../services/api";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";

const verdictMeta = {
  GOOD: { label: "? Great Financial Health!", cls: "good" },
  AVERAGE: { label: "?? Room for Improvement", cls: "average" },
  NEEDS_IMPROVEMENT: { label: "?? Take Action Now", cls: "warning" },
  CRITICAL: { label: "?? Immediate Attention Needed", cls: "critical" },
};

const AIInsightsPanel = ({ userId, month, year }) => {
  const [state, setState] = useState({ data: null, loading: true, error: "", refreshedAt: null });

  const fetchInsights = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const data = await getInsights(userId, month, year);
      setState({ data, loading: false, error: "", refreshedAt: new Date() });
    } catch (error) {
      setState((prev) => ({
        data: prev.data,
        loading: false,
        error: error.message || "AI insights temporarily unavailable",
        refreshedAt: prev.refreshedAt,
      }));
    }
  }, [userId, month, year]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  const insight = state.data?.insights || {};
  const verdict = verdictMeta[insight.spending_verdict] || verdictMeta.AVERAGE;

  const updatedAgo = useMemo(() => {
    if (!state.refreshedAt) return "just now";
    const mins = Math.max(1, Math.round((Date.now() - state.refreshedAt.getTime()) / 60000));
    return `${mins} min ago`;
  }, [state.refreshedAt]);

  return (
    <section className="glass-card ai-panel">
      <div className="panel-head">
        <h3>AI Insights</h3>
        <button type="button" className="ghost-btn" onClick={fetchInsights}>
          <RefreshCcw size={14} /> Regenerate Insights
        </button>
      </div>

      {state.loading ? (
        <div>
          <p className="muted small" style={{ marginBottom: 12 }}>
            AI is analysing your finances…
          </p>
          <SkeletonCard lines={5} height={220} />
        </div>
      ) : !state.data ? (
        <ErrorCard message={state.error || "Unable to load insights."} onRetry={fetchInsights} />
      ) : (
        <>
          {state.error ? (
            <div style={{ marginBottom: 12 }}>
              <ErrorCard message={state.error} onRetry={fetchInsights} />
            </div>
          ) : null}
          <div className={`verdict-pill ${verdict.cls}`}>{verdict.label}</div>
          <p className="insight-summary">{insight.summary || "AI insights temporarily unavailable"}</p>

          <div className="insight-section">
            <h4>?? Key Insights</h4>
            <ul>{(insight.key_insights || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
          </div>

          {(insight.warnings || []).length > 0 && (
            <div className="insight-section warnings">
              <h4>?? Warnings</h4>
              <ul>{insight.warnings.map((item, i) => <li key={i}>{item}</li>)}</ul>
            </div>
          )}

          <div className="insight-section">
            <h4>? Recommendations</h4>
            <ul>{(insight.recommendations || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
          </div>

          {(insight.positive_highlights || []).length > 0 && (
            <div className="insight-section">
              <h4>?? Positive Highlights</h4>
              <ul>{insight.positive_highlights.map((item, i) => <li key={i}>{item}</li>)}</ul>
            </div>
          )}

          <p className="muted-text">Last updated: {updatedAgo}</p>
        </>
      )}
    </section>
  );
};

export default AIInsightsPanel;
