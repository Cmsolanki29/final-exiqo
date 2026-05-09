import React from "react";

export const SkeletonCard = ({ lines = 3, height = 120 }) => (
  <div className="skeleton-card feature-card" style={{ minHeight: height }}>
    {Array.from({ length: lines }, (_, i) => (
      <div key={i} className="skeleton-line" style={{ width: `${Math.max(40, 85 - i * 15)}%` }} />
    ))}
  </div>
);

export const SkeletonStats = () => (
  <div
    style={{
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
      gap: "16px",
    }}
  >
    {Array.from({ length: 4 }, (_, i) => (
      <SkeletonCard key={i} lines={2} height={100} />
    ))}
  </div>
);
