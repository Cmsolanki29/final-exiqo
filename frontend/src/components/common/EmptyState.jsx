import React from "react";

export const EmptyState = ({ icon, title, subtitle, action }) => (
  <div
    className="empty-state-polish"
    style={{
      padding: "48px 24px",
      textAlign: "center",
      color: "#64748b",
    }}
  >
    <div style={{ fontSize: "48px", marginBottom: "16px" }} aria-hidden>
      {icon || "📭"}
    </div>
    <div
      style={{
        fontSize: "16px",
        fontWeight: "600",
        color: "#94a3b8",
        marginBottom: "8px",
      }}
    >
      {title}
    </div>
    <div style={{ fontSize: "13px", marginBottom: "20px", maxWidth: "420px", marginInline: "auto" }}>
      {subtitle}
    </div>
    {action}
  </div>
);
