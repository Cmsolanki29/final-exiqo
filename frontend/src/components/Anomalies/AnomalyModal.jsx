import React, { useEffect, useState } from "react";
import { getAnomalyExplanation } from "../../services/api";
import { apiUtils } from "../../services/api";

const AnomalyModal = ({ isOpen, onClose, transaction, userId }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [explanation, setExplanation] = useState("");

  useEffect(() => {
    if (!isOpen || !transaction || !userId) return;

    const run = async () => {
      setLoading(true);
      setError("");
      setExplanation("");
      try {
        const result = await getAnomalyExplanation(userId, transaction.transaction_id);
        setExplanation(result.explanation || "No AI explanation available.");
      } catch (err) {
        setError(err.message || "Unable to fetch explanation");
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [isOpen, transaction, userId]);

  if (!isOpen || !transaction) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>AI Fraud Explanation</h3>
          <button type="button" className="ghost-btn" onClick={onClose}>?</button>
        </div>

        <div className="tx-summary">
          <strong>{transaction.merchant}</strong>
          <span>{apiUtils.formatINR(transaction.amount)}</span>
          <span>{transaction.transaction_date}</span>
          <span className={`risk-chip ${String(transaction.risk_level || "LOW").toLowerCase()}`}>
            {transaction.risk_level}
          </span>
        </div>

        <div className="modal-body">
          {loading ? (
            <p>?? AI analyzing transaction...</p>
          ) : error ? (
            <p className="amount-negative">{error}</p>
          ) : (
            <p>{explanation}</p>
          )}
        </div>

        <div className="modal-actions">
          <button type="button" className="secondary-btn">? Mark as Safe</button>
          <button type="button" className="danger-btn">?? Report Fraud</button>
          <button type="button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
};

export default AnomalyModal;
