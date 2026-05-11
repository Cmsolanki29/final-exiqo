import React from "react";
import { RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";

const gradeColor = {
  A: "#22c55e",
  B: "#3b82f6",
  C: "#f59e0b",
  D: "#f97316",
  F: "#ef4444",
};

const TrendBadge = ({ trend }) => {
  const up = trend === "IMPROVING";
  const down = trend === "DECLINING";
  return (
    <span className={`trend-badge ${up ? "up" : down ? "down" : "flat"}`}>
      {trend} {up ? "?" : down ? "?" : "?"}
    </span>
  );
};

const Breakdown = ({ label, value, max }) => {
  const ratio = Math.max(0, Math.min(100, (Number(value || 0) / max) * 100));
  return (
    <div className="breakdown-row">
      <div className="breakdown-head">
        <span>{label}</span>
        <span>{value}/{max}</span>
      </div>
      <div className="breakdown-track">
        <div className="breakdown-fill" style={{ width: `${ratio}%` }} />
      </div>
    </div>
  );
};

const HealthScoreGauge = ({ healthData = {} }) => {
  const score = Number(healthData.score || 0);
  const grade = healthData.grade || "F";
  const comp = healthData.components || {};

  const chartData = [{ name: "score", value: score, fill: gradeColor[grade] || "#ef4444" }];

  return (
    <section className="glass-card chart-card">
      <div className="panel-head">
        <h3>Financial Health</h3>
        <TrendBadge trend={healthData.trend || "STABLE"} />
      </div>

      <div className="gauge-wrap">
        <ResponsiveContainer width="100%" height={240}>
          <RadialBarChart
            innerRadius="70%"
            outerRadius="100%"
            startAngle={180}
            endAngle={0}
            data={chartData}
            barSize={16}
          >
            <RadialBar minAngle={15} background clockWise dataKey="value" cornerRadius={10} />
          </RadialBarChart>
        </ResponsiveContainer>

        <div className="gauge-center">
          <p className="gauge-score">{score}</p>
          <p className="gauge-sub">/100</p>
          <span className="grade-pill" style={{ background: gradeColor[grade] || "#ef4444" }}>
            {grade}
          </span>
        </div>
      </div>

      <div className="breakdown-list">
        <Breakdown label="Savings Rate" value={comp.savings_points || 0} max={30} />
        <Breakdown label="Security" value={comp.anomaly_points || 0} max={20} />
        <Breakdown label="Expense Ratio" value={comp.expense_points || 0} max={25} />
        <Breakdown label="Consistency" value={comp.consistency_points || 0} max={15} />
        <Breakdown label="Diversity" value={comp.diversity_points || 0} max={10} />
      </div>
    </section>
  );
};

export default HealthScoreGauge;
