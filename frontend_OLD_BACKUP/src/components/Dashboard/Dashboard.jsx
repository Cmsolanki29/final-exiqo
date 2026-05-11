import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Shield, Sparkles, TrendingDown } from "lucide-react";
import useSmartSpend from "../../hooks/useSmartSpend";
import { apiUtils, getFestivals, getFraudShieldAlerts, getSubscriptions } from "../../services/api";
import { getBusinessImpact } from "../../services/riskApi";
import AnomalyList from "../Anomalies/AnomalyList";
import StatCards from "../Cards/StatCards";
import HealthScoreGauge from "../Charts/HealthScoreGauge";
import MonthlyTrendChart from "../Charts/MonthlyTrendChart";
import SpendingPieChart from "../Charts/SpendingPieChart";
import AIInsightsPanel from "../Insights/AIInsightsPanel";
import ScenarioSimulator from "../Simulator/ScenarioSimulator";
import TransactionTable from "../Transactions/TransactionTable";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonStats } from "../common/SkeletonCard";
import FestivalDashboardWidget from "./FestivalDashboardWidget";
import FraudShieldSummary from "./FraudShieldSummary";
import PurchaseDashboardWidget from "./PurchaseDashboardWidget";

const Dashboard = ({
  userId,
  month,
  year,
  onOpenFraudShield,
  onOpenFestival,
  onOpenPurchase,
  userName = "there",
  setActiveTab,
}) => {
  const { summary, spending, trends, anomalies, anomalyStats, health, merchants, loading, error, refetch } =
    useSmartSpend(userId, month, year);

  const [intel, setIntel] = useState({
    loading: true,
    fraudPending: 0,
    monthlyWaste: 0,
    nextFest: null,
  });
  const [impact, setImpact] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIntel((s) => ({ ...s, loading: true }));
      try {
        const [alertsRes, subsRes, festRes] = await Promise.all([
          getFraudShieldAlerts(userId),
          getSubscriptions(userId),
          getFestivals(userId),
        ]);
        const pending = (alertsRes?.alerts || []).filter((a) => a.user_action === "PENDING").length;
        const waste = Number(subsRes?.monthly_waste || 0);
        const nf = festRes?.next_festival || null;
        if (!cancelled) {
          setIntel({ loading: false, fraudPending: pending, monthlyWaste: waste, nextFest: nf });
        }
      } catch {
        if (!cancelled) {
          setIntel({ loading: false, fraudPending: 0, monthlyWaste: 0, nextFest: null });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  useEffect(() => {
    let cancelled = false;
    getBusinessImpact()
      .then((d) => { if (!cancelled) setImpact(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <main className="dashboard-wrap" style={{ marginTop: 16 }}>
        <section className="glass-card" style={{ marginBottom: 16 }}>
          <SkeletonStats />
        </section>
        <div className="dashboard-grid">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="glass-card feature-card">
              <div className="skeleton" style={{ height: 200 }} />
            </div>
          ))}
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main style={{ marginTop: 16 }}>
        <ErrorCard message={error} onRetry={refetch} />
      </main>
    );
  }

  const displayName = userName?.trim() || "there";

  return (
    <motion.main
      className="dashboard-wrap fade-in tab-panel-enter"
      style={{ marginTop: 8 }}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <section className="mb-4">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-white md:text-xl">Financial intelligence</h2>
            <p className="text-xs text-exiqo-glow/65 md:text-sm">Priorities for {displayName}</p>
          </div>
          {intel.loading ? (
            <span className="rounded-lg border border-exiqo-purple/25 bg-exiqo-dark/50 px-2.5 py-1 text-[11px] text-exiqo-glow/80">
              Syncing insights…
            </span>
          ) : null}
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <button
            type="button"
            disabled={intel.loading}
            onClick={() => setActiveTab?.("fraud")}
            className="group relative overflow-hidden rounded-2xl border border-exiqo-purple/35 bg-gradient-to-br from-exiqo-purple/20 to-exiqo-dark/60 p-4 text-left shadow-lg shadow-exiqo-purple/10 transition hover:shadow-purple-glow disabled:opacity-60"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-exiqo-purple to-exiqo-pink">
                <Shield className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">
                  {Number(intel.fraudPending || 0) > 0
                    ? `${intel.fraudPending} fraud alert${intel.fraudPending > 1 ? "s" : ""}`
                    : "No pending fraud reviews"}
                </p>
                <p className="text-xs text-exiqo-glow/65">Open Fraud Shield</p>
              </div>
            </div>
            <div className="pointer-events-none absolute inset-0 translate-x-[-100%] bg-gradient-to-r from-transparent via-white/[0.06] to-transparent transition-transform duration-1000 group-hover:translate-x-[100%]" />
          </button>

          <button
            type="button"
            disabled={intel.loading}
            onClick={() => setActiveTab?.("subscriptions")}
            className="group relative overflow-hidden rounded-2xl border border-exiqo-pink/35 bg-gradient-to-br from-exiqo-pink/15 to-exiqo-dark/60 p-4 text-left shadow-lg transition hover:shadow-pink-glow disabled:opacity-60"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-exiqo-pink to-rose-600">
                <TrendingDown className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">
                  {Number(intel.monthlyWaste || 0) > 0
                    ? `${apiUtils.formatINR(intel.monthlyWaste)} est. waste / mo`
                    : "Subscriptions look lean"}
                </p>
                <p className="text-xs text-exiqo-glow/65">Optimize recurring spend</p>
              </div>
            </div>
            <div className="pointer-events-none absolute inset-0 translate-x-[-100%] bg-gradient-to-r from-transparent via-white/[0.06] to-transparent transition-transform duration-1000 group-hover:translate-x-[100%]" />
          </button>

          <button
            type="button"
            disabled={intel.loading || !intel.nextFest}
            onClick={() => setActiveTab?.("festival")}
            className="group relative overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-500/15 to-exiqo-dark/60 p-4 text-left shadow-lg transition hover:shadow-emerald-500/30 disabled:opacity-60"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">
                  {intel.nextFest
                    ? `${intel.nextFest.name} in ${intel.nextFest.days_remaining} days`
                    : "Festival planner"}
                </p>
                <p className="text-xs text-exiqo-glow/65">Plan savings ahead</p>
              </div>
            </div>
            <div className="pointer-events-none absolute inset-0 translate-x-[-100%] bg-gradient-to-r from-transparent via-white/[0.06] to-transparent transition-transform duration-1000 group-hover:translate-x-[100%]" />
          </button>
        </div>
      </section>

      <StatCards
        summary={summary}
        anomalyStats={anomalyStats}
        spendingData={spending}
        trends={trends}
        month={month}
        year={year}
      />

      <FraudShieldSummary onViewDetails={onOpenFraudShield} />

      <section className="dash-widgets-pair">
        <FestivalDashboardWidget userId={userId} onPlanNow={onOpenFestival} />
        <PurchaseDashboardWidget userId={userId} onOpenPlanner={onOpenPurchase} />
      </section>

      <section className="row-two">
        <SpendingPieChart spendingData={spending} month={month} year={year} />
        <MonthlyTrendChart trendsData={trends} />
      </section>

      <section className="row-three">
        <HealthScoreGauge healthData={health} />
        <AIInsightsPanel userId={userId} month={month} year={year} />
      </section>

      <AnomalyList anomalies={anomalies} userId={userId} />

      <section className="row-five">
        <ScenarioSimulator userId={userId} month={month} year={year} />
        <section className="glass-card feature-card">
          <div className="panel-head">
            <h3>Top Merchants</h3>
          </div>
          {(merchants || []).length === 0 ? (
            <div className="empty-box">No merchant data available</div>
          ) : (
            <ul className="merchant-list card-list">
              {merchants.map((m, idx) => (
                <li key={`${m.merchant}-${idx}`}>
                  <span>{m.merchant}</span>
                  <strong>{apiUtils.formatINR(m.total_spend || 0)}</strong>
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>

      {/* Business Impact row — live from /api/business-impact */}
      {impact && (
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card"
          style={{ borderLeft: "3px solid #a855f7", marginTop: 8 }}
        >
          <div className="panel-head" style={{ marginBottom: 8 }}>
            <h3 style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Shield size={15} style={{ color: "#a855f7" }} />
              AI Business Impact
            </h3>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 10 }}>
            {[
              { label: "Frauds Prevented",    value: impact.total_fraud_prevented,                       suffix: "" },
              { label: "Money Saved",          value: apiUtils.formatINR(impact.total_money_saved_inr),  suffix: "" },
              { label: "Detection Rate",       value: `${impact.detection_rate_pct}%`,                   suffix: "" },
              { label: "Avg Fraud Amount",     value: apiUtils.formatINR(impact.avg_fraud_amount_inr),   suffix: "" },
            ].map(({ label, value }) => (
              <div key={label} style={{ textAlign: "center" }}>
                <p className="muted small">{label}</p>
                <strong style={{ fontSize: 18 }}>{value}</strong>
              </div>
            ))}
          </div>
          {impact.projection_sentence && (
            <p style={{ fontSize: 11, color: "#a78bfa", fontStyle: "italic", lineHeight: 1.5 }}>
              📊 {impact.projection_sentence}
            </p>
          )}
        </motion.section>
      )}

      <TransactionTable userId={userId} month={month} year={year} />
    </motion.main>
  );
};

export default Dashboard;
