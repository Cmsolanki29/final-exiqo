import React from "react";

export const ErrorCard = ({ message, onRetry }) => (
  <div
    className="error-card-polish feature-card"
    style={{
      padding: "24px",
      borderRadius: "16px",
      background: "rgba(239, 68, 68, 0.1)",
      border: "1px solid rgba(239, 68, 68, 0.3)",
      textAlign: "center",
    }}
  >
    <div style={{ fontSize: "32px", marginBottom: "12px" }} aria-hidden>
      ⚠️
    </div>
    <div
      style={{
        color: "#ef4444",
        fontSize: "14px",
        marginBottom: "16px",
      }}
    >
      {message || "Something went wrong. Please try again."}
    </div>
    {onRetry && (
      <button type="button" className="btn-primary" onClick={onRetry}>
        🔄 Retry
      </button>
    )}
  </div>
);
