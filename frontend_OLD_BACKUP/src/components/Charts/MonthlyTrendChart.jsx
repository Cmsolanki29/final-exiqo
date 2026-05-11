import React from "react";
import { EmptyState } from "../common/EmptyState";
import {
  Area,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiUtils } from "../../services/api";

const monthLabel = (iso) => {
  const [year, month] = String(iso).split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("en-IN", { month: "short" });
};

const MonthlyTrendChart = ({ trendsData = [] }) => {
  const chartData = trendsData.map((row) => ({
    ...row,
    label: monthLabel(row.month),
  }));

  return (
    <section className="glass-card chart-card">
      <div className="panel-head">
        <h3>12-Month Financial Trends</h3>
      </div>

      {chartData.length === 0 ? (
        <EmptyState icon="📈" title="No trend data yet" subtitle="Add more monthly activity to see your 12-month curve." />
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="4 4" stroke="#334155" />
            <XAxis dataKey="label" stroke="#94a3b8" />
            <YAxis
              stroke="#94a3b8"
              tickFormatter={(v) =>
                v >= 100000 ? `?${(v / 100000).toFixed(1)}L` : `?${Math.round(v / 1000)}k`
              }
            />
            <Tooltip
              formatter={(value, name) => [apiUtils.formatINR(value), name]}
              labelFormatter={(label, payload) => {
                const raw = payload?.[0]?.payload?.month || label;
                const [y, m] = String(raw).split("-");
                const d = new Date(Number(y), Number(m) - 1, 1);
                return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
              }}
              contentStyle={{ borderRadius: 12, border: "1px solid #334155", background: "#0f172a" }}
              labelStyle={{ color: "#f1f5f9" }}
            />
            <Legend />
            <Area type="monotone" dataKey="saved" fill="#3b82f622" stroke="none" />
            <Line type="monotone" dataKey="income" stroke="#10b981" strokeWidth={2.5} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="expense" stroke="#ef4444" strokeWidth={2.5} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="saved" stroke="#3b82f6" strokeWidth={2.5} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </section>
  );
};

export default MonthlyTrendChart;
