import React from "react";
import { AlertTriangle, PiggyBank, Scale, Wallet } from "lucide-react";
import StatCard from "./StatCard";
import { apiUtils } from "../../services/api";

function monthKey(y, m) {
  return `${y}-${String(m).padStart(2, "0")}`;
}

function previousMonthExpense(trends, month, year) {
  if (!Array.isArray(trends) || !trends.length) return 0;
  const key = monthKey(year, month);
  const idx = trends.findIndex((t) => t.month === key);
  if (idx <= 0) return 0;
  return Number(trends[idx - 1]?.expense || 0);
}

export default function StatCards({ summary, anomalyStats, spendingData, trends, month, year }) {
  const amountSaved = summary?.this_month_saved ?? summary?.amount_saved ?? 0;
  const savingsRate = summary?.savings_rate ?? 0;
  const healthScore = summary?.health_score ?? 0;
  const healthGrade = summary?.health_grade;

  const spendingArr = Array.isArray(spendingData) ? spendingData : [];
  const totalSpent = spendingArr.reduce((acc, row) => acc + Number(row.total_amount || 0), 0);

  const prevSpent =
    month && year ? previousMonthExpense(trends, month, year) : 0;

  const highRiskAlerts = Number(anomalyStats?.high_risk_count ?? 0);

  const savedVariant = amountSaved >= 0 ? "success" : "danger";
  const healthVariant =
    healthScore >= 70 ? "success" : healthScore >= 40 ? "warning" : "danger";
  const alertsVariant = highRiskAlerts > 0 ? "danger" : "success";
  const spentVariant = "default";

  const healthSubtitle = healthGrade
    ? `Grade ${healthGrade}${
        healthScore >= 70
          ? " - Strong discipline"
          : healthScore >= 40
            ? " - Room to improve"
            : " - Needs attention"
      }`
    : healthScore >= 70
      ? "Strong financial discipline"
      : healthScore >= 40
        ? "Room to improve"
        : "Needs attention";

  return (
    <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        title="Amount Saved"
        value={apiUtils.formatINR(amountSaved)}
        subtitle={`${Number(savingsRate).toFixed(1)}% savings rate`}
        icon={PiggyBank}
        trend={savingsRate >= 0 ? "up" : "down"}
        trendValue={`${Math.abs(Number(savingsRate)).toFixed(1)}%`}
        variant={savedVariant}
      />
      <StatCard
        title="Health Score"
        value={`${healthScore}/100`}
        subtitle={healthSubtitle}
        icon={Scale}
        variant={healthVariant}
      />
      <StatCard
        title="Active Alerts"
        value={highRiskAlerts}
        subtitle="High / critical risk anomalies"
        icon={AlertTriangle}
        variant={alertsVariant}
      />
      <StatCard
        title="Total Spent"
        value={apiUtils.formatINR(totalSpent)}
        subtitle="This period total debits"
        icon={Wallet}
        trend={prevSpent > 0 ? (totalSpent >= prevSpent ? "up" : "down") : undefined}
        trendValue={prevSpent > 0 ? `vs ${apiUtils.formatINR(prevSpent)} prior` : undefined}
        variant={spentVariant}
      />
    </div>
  );
}
