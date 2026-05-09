import React, { useMemo, useState } from "react";
import { AlertTriangle, Eye } from "lucide-react";
import { apiUtils } from "../../services/api";
import { EmptyState } from "../common/EmptyState";
import AnomalyModal from "./AnomalyModal";

const riskClass = (risk) => String(risk || "LOW").toLowerCase();

const AnomalyList = ({ anomalies = [], userId }) => {
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("risk");
  const [visible, setVisible] = useState(10);
  const [selected, setSelected] = useState(null);

  const filtered = useMemo(() => {
    let list = [...anomalies];

    if (severityFilter !== "ALL") {
      list = list.filter((a) => String(a.risk_level).toUpperCase() === severityFilter);
    }

    if (sortBy === "date") {
      list.sort((a, b) => new Date(b.transaction_date) - new Date(a.transaction_date));
    } else if (sortBy === "amount") {
      list.sort((a, b) => Number(b.amount || 0) - Number(a.amount || 0));
    } else {
      list.sort((a, b) => Number(b.risk_score || 0) - Number(a.risk_score || 0));
    }

    return list;
  }, [anomalies, severityFilter, sortBy]);

  const visibleRows = filtered.slice(0, visible);

  return (
    <section className="glass-card anomaly-card-wrap">
      <div className="panel-head">
        <div>
          <h3>?? Suspicious Transactions Detected by AI</h3>
          <p>{filtered.length} transactions flagged this month</p>
        </div>

        <div className="filter-row">
          {["ALL", "CRITICAL", "HIGH", "MEDIUM"].map((risk) => (
            <button
              type="button"
              key={risk}
              onClick={() => setSeverityFilter(risk)}
              className={`chip-btn ${severityFilter === risk ? "active" : ""}`}
            >
              {risk}
            </button>
          ))}

          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="risk">Risk Score</option>
            <option value="date">Date</option>
            <option value="amount">Amount</option>
          </select>
        </div>
      </div>

      {visibleRows.length === 0 ? (
        <EmptyState
          icon="✅"
          title={anomalies.length === 0 ? "No suspicious transactions this period" : "No rows match this filter"}
          subtitle={
            anomalies.length === 0
              ? "Isolation Forest did not flag anomalies for the current view — great news."
              : "Try another severity or sort option."
          }
        />
      ) : (
        <div className="anomaly-list">
          {visibleRows.map((a) => (
            <article key={a.transaction_id} className={`anomaly-item ${riskClass(a.risk_level)}`}>
              <div className="anomaly-main">
                <span className={`risk-chip ${riskClass(a.risk_level)}`}>{a.risk_level}</span>
                <strong>{a.merchant || "Unknown Merchant"}</strong>
                <span>{apiUtils.formatINR(a.amount)}</span>
                <span>{String(a.transaction_date)}</span>
              </div>
              <p className="muted-text">{a.reason}</p>
              <div className="anomaly-actions">
                <span className="muted-text">Risk Score: {a.risk_score}</span>
                <button type="button" onClick={() => setSelected(a)}>
                  <Eye size={16} /> Explain
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {filtered.length > visible && (
        <button className="ghost-btn" type="button" onClick={() => setVisible((v) => v + 10)}>
          <AlertTriangle size={16} /> Load More
        </button>
      )}

      <AnomalyModal
        isOpen={Boolean(selected)}
        onClose={() => setSelected(null)}
        transaction={selected}
        userId={userId}
      />
    </section>
  );
};

export default AnomalyList;
