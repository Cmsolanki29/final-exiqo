import React, { useMemo } from "react";
import { EmptyState } from "../common/EmptyState";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { apiUtils } from "../../services/api";

const categoryColors = {
  "Food & Dining": "#f97316",
  Transportation: "#3b82f6",
  Shopping: "#8b5cf6",
  "Bills & Utilities": "#10b981",
  Entertainment: "#f59e0b",
  Healthcare: "#ef4444",
  Finance: "#06b6d4",
  Uncategorized: "#6b7280",
  Other: "#6b7280",
};

const colorFor = (category, index) =>
  categoryColors[category] || ["#6b7280", "#14b8a6", "#a855f7", "#0ea5e9", "#22c55e"][index % 5];

const SpendingPieChart = ({ spendingData = [], month, year }) => {
  const total = useMemo(
    () => spendingData.reduce((acc, item) => acc + Number(item.total_amount || 0), 0),
    [spendingData]
  );

  return (
    <section className="glass-card chart-card">
      <div className="panel-head">
        <h3>Spending by Category</h3>
        <p>{`${month}/${year}`}</p>
      </div>

      {spendingData.length === 0 ? (
        <EmptyState icon="🥧" title="No spending data" subtitle="No categorized debits for this month yet." />
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={spendingData}
              dataKey="total_amount"
              nameKey="category"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={3}
              animationDuration={700}
            >
              {spendingData.map((entry, idx) => (
                <Cell key={entry.category} fill={colorFor(entry.category, idx)} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, _, payload) => [apiUtils.formatINR(value), payload?.payload?.category]}
              contentStyle={{ borderRadius: 12, border: "1px solid #334155", background: "#0f172a" }}
              labelStyle={{ color: "#f1f5f9" }}
            />
            <Legend verticalAlign="bottom" iconType="circle" />
            <text x="50%" y="49%" textAnchor="middle" fill="#94a3b8" fontSize={12}>
              Total
            </text>
            <text x="50%" y="56%" textAnchor="middle" fill="#f1f5f9" fontSize={16} fontWeight={700}>
              {apiUtils.formatINR(total)}
            </text>
          </PieChart>
        </ResponsiveContainer>
      )}
    </section>
  );
};

export default SpendingPieChart;
