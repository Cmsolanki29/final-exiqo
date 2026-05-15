/**
 * Dashboard — Stripe / Mercury / Linear-grade calm fintech dashboard.
 *
 * Design principles
 * ─────────────────────────────────────────────────────────────────────────────
 *  • Calm > loud. Reduced visual noise, generous spacing.
 *  • One card primitive (PremiumCard) used everywhere — single look.
 *  • Solid `bg-[#0A0612]` page wrapper masks the global aurora orbs so the
 *    dashboard reads as a flat, focused surface (other pages remain unchanged).
 *  • Depth via shadow-glow per variant, never via heavy borders.
 *  • Subtle motion only: fade-in + count-up + sparkline draw. No bouncing.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  CreditCard,
  EyeOff,
  PiggyBank,
  Receipt,
  RefreshCw,
  Shield,
  Sparkles,
  Wallet,
} from "lucide-react";
import useSmartSpend from "../../hooks/useSmartSpend";
import useDashboardData from "../../hooks/useDashboardData";
import { useAuth } from "../../context/AuthContext";
import {
  apiUtils,
  getDarkPatterns,
  getEmiReport,
  getFestivals,
  getFraudShieldAlerts,
  getHealthNarrative,
  getSubscriptions,
} from "../../services/api";
import {
  getAISummary,
  getInsightsFeed,
  markInsightRead,
} from "../../services/subscriptionIntelligence";
import HealthScoreGauge from "../Charts/HealthScoreGauge";
import MonthlyTrendChart from "../Charts/MonthlyTrendChart";
import SpendingPieChart from "../Charts/SpendingPieChart";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";
import { AuroraBackground } from "../intro/AuroraBackground";
import DashboardGreeting from "./DashboardGreeting";
import KPICard from "./shared/KPICard";
import QuickActionCard from "./shared/QuickActionCard";
import PremiumCard from "./shared/PremiumCard";
import NerveCentreCard from "./NerveCentreCard";
import LiveInsightsFeed, { type FeedItem } from "./LiveInsightsFeed";

const monthKey = (y: number, m: number) => `${y}-${String(m).padStart(2, "0")}`;

function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "Recently";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "Recently";
  const mins = Math.floor((Date.now() - t) / 60000);
  if (mins < 1)  return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatRelativeMinutes(date: Date): string {
  const mins = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
  if (mins < 1)   return "just now";
  if (mins < 60)  return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)   return `${hrs} hr ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

type TrendPoint = { month: string; income?: number; expense?: number; saved?: number };
type NextFest  = { name: string; days_remaining: number } | null;

type DashboardProps = {
  userId: number;
  month: number;
  year: number;
  onMonthChange?: (m: number) => void;
  onYearChange?: (y: number) => void;
  setActiveTab?: (tab: string) => void;
};

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function Dashboard({
  userId,
  month,
  year,
  setActiveTab,
}: DashboardProps) {
  const { user: authUser } = useAuth();
  const { spending, trends, health, anomalies, loading, error, loadWarnings, refetch } = useSmartSpend(
    userId,
    month,
    year
  );
  // Live freshness signals (real DB) — last_synced from bank_connections,
  // fraud_pending_count from fraud_alerts. Drives the greeting metadata row
  // and the dashboard's "Last refreshed" footer button.
  const {
    lastSynced: dashLastSynced,
    lastLogin:  dashLastLogin,
    fraudPending: dashFraudPending,
    loading:    dashHeaderLoading,
    refetch:    refetchHeader,
  } = useDashboardData(userId);
  const trendList = useMemo(() => (Array.isArray(trends) ? trends : []) as TrendPoint[], [trends]);

  const canLiveIntel = Boolean(authUser?.id && Number(authUser.id) === Number(userId));
  const [aiIntel, setAiIntel] = useState<{
    loading: boolean;
    summary: Awaited<ReturnType<typeof getAISummary>> | null;
    insights: Array<Record<string, unknown>>;
  }>({ loading: false, summary: null, insights: [] });

  const [intel, setIntel] = useState({
    loading: true,
    fraudPending: 0,
    monthlyWaste: 0,
    nextFest: null as NextFest,
    darkCount: 0,
    emiCount: 0,
  });

  const [narration, setNarration] = useState<string | null>(null);

  const onDataRefresh = useCallback(async () => {
    await Promise.all([refetch(), refetchHeader()]);
  }, [refetch, refetchHeader]);

  // ── Pull guardian intel (fraud, subscriptions, festivals, dark, EMI) ─────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIntel((s) => ({ ...s, loading: true }));
      try {
        const [alertsRes, subsRes, festRes, darkRes, emiRes] = await Promise.all([
          getFraudShieldAlerts(userId),
          getSubscriptions(userId),
          getFestivals(userId),
          getDarkPatterns(userId).catch(() => []),
          getEmiReport(userId).catch(() => ({ emis_detected: [] })),
        ]);
        const pending  = (alertsRes?.alerts || []).filter((a: { user_action?: string }) => a.user_action === "PENDING").length;
        const waste    = Number(subsRes?.monthly_waste || 0);
        const nf       = festRes?.next_festival || null;
        const darkList = darkRes?.patterns || (Array.isArray(darkRes) ? darkRes : []) || [];
        const darkCount = Array.isArray(darkList) ? darkList.length : 0;
        const emis     = emiRes?.emis_detected || emiRes?.emis || [];
        const emiCount = Array.isArray(emis) ? emis.length : Number(emiRes?.emi_detected_count || 0);

        if (!cancelled) {
          setIntel({ loading: false, fraudPending: pending, monthlyWaste: waste, nextFest: nf, darkCount, emiCount });
        }
      } catch {
        if (!cancelled) {
          setIntel({ loading: false, fraudPending: 0, monthlyWaste: 0, nextFest: null, darkCount: 0, emiCount: 0 });
        }
      }
    })();
    return () => { cancelled = true; };
  }, [userId]);

  // ── Health narrative ─────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await getHealthNarrative(userId, month, year);
        const text = typeof res?.narrative === "string" ? res.narrative : res?.narrative?.summary;
        if (!cancelled) setNarration(text || null);
      } catch {
        if (!cancelled) setNarration(null);
      }
    })();
    return () => { cancelled = true; };
  }, [userId, month, year]);

  // ── Subscription intelligence (live AI feed) ─────────────────────────────
  useEffect(() => {
    if (!canLiveIntel || !authUser?.id) {
      setAiIntel({ loading: false, summary: null, insights: [] });
      return;
    }
    let cancelled = false;
    (async () => {
      setAiIntel((s) => ({ ...s, loading: true }));
      try {
        const [sum, feed] = await Promise.all([
          getAISummary(authUser.id),
          getInsightsFeed(authUser.id, false, 14),
        ]);
        if (!cancelled) {
          setAiIntel({
            loading: false,
            summary: sum,
            insights: Array.isArray(feed?.insights) ? feed.insights : [],
          });
        }
      } catch {
        if (!cancelled) setAiIntel({ loading: false, summary: null, insights: [] });
      }
    })();
    return () => { cancelled = true; };
  }, [canLiveIntel, authUser?.id]);

  // ── Derived KPIs ─────────────────────────────────────────────────────────
  const trendRow = useMemo(() => {
    const key = monthKey(year, month);
    return trendList.find((t) => t.month === key) || null;
  }, [trendList, month, year]);

  const prevMonthExpense = useMemo(() => {
    const key = monthKey(year, month);
    const idx = trendList.findIndex((t) => t.month === key);
    if (idx <= 0) return 0;
    return Number(trendList[idx - 1]?.expense || 0);
  }, [trendList, month, year]);

  const monthSpend = useMemo(() => {
    const fromTrend = Number(trendRow?.expense || 0);
    if (fromTrend > 0) return fromTrend;
    return (Array.isArray(spending) ? spending : []).reduce(
      (acc: number, row: { total_amount?: number }) => acc + Number(row.total_amount || 0),
      0
    );
  }, [trendRow, spending]);

  const monthIncome = Number(trendRow?.income || 0);
  const netMonth    = monthIncome - monthSpend;

  const savedYtd = useMemo(() => {
    return trendList
      .filter((t) => String(t.month || "").startsWith(`${year}-`))
      .reduce((acc: number, t) => acc + Number(t.saved || 0), 0);
  }, [trendList, year]);

  const sparkExpense = useMemo(() => trendList.slice(-6).map((t) => Number(t.expense || 0)), [trendList]);
  const sparkIncome  = useMemo(() => trendList.slice(-6).map((t) => Number(t.income  || 0)), [trendList]);
  const sparkSaved   = useMemo(() => trendList.slice(-6).map((t) => Number(t.saved   || 0)), [trendList]);

  const spendDeltaPct = useMemo(() => {
    if (prevMonthExpense <= 0) return null;
    return ((monthSpend - prevMonthExpense) / prevMonthExpense) * 100;
  }, [monthSpend, prevMonthExpense]);

  const netDeltaPct = useMemo(() => {
    const key = monthKey(year, month);
    const idx = trendList.findIndex((t) => t.month === key);
    if (idx <= 0) return null;
    const prev = Number(trendList[idx - 1]?.saved || 0);
    if (prev === 0) return null;
    return ((netMonth - prev) / Math.abs(prev)) * 100;
  }, [trendList, month, year, netMonth]);

  const healthRec =
    health && typeof health === "object" && "recommendations" in health
      ? (health as { recommendations?: string[] }).recommendations
      : undefined;
  const healthNarrationLine =
    narration ||
    (Array.isArray(healthRec) && healthRec[0]) ||
    "Your guardian is monitoring cashflow, subscriptions, and anomalies.";

  const healthComp =
    health && typeof health === "object" && "components" in health
      ? ((health as { components?: Record<string, number> }).components || {})
      : {};

  // ── Live AI feed ─────────────────────────────────────────────────────────
  const feedItems = useMemo((): FeedItem[] => {
    const rows: FeedItem[] = [];
    const goSubs     = () => setActiveTab?.("subscriptions");
    const goTxn      = () => setActiveTab?.("transactions");
    const goInsights = () => setActiveTab?.("insights");

    const markRead = async (insId: number) => {
      if (!authUser?.id) return;
      try {
        await markInsightRead(authUser.id, insId);
        setAiIntel((prev) => ({
          ...prev,
          insights: prev.insights.map((x) =>
            Number(x.id) === insId ? { ...x, read_at: new Date().toISOString() } : x
          ),
        }));
      } catch { /* ignore */ }
    };

    if (canLiveIntel && aiIntel.insights.length) {
      for (const raw of aiIntel.insights.slice(0, 6)) {
        const ins = raw as Record<string, unknown>;
        const typ = String(ins.insight_type || "").toLowerCase();
        const sev: FeedItem["severity"] =
          typ.includes("verdict") && String(ins.body || "").toLowerCase().includes("dormant")
            ? "critical"
            : typ.includes("migration") || typ.includes("substitution")
              ? "warning"
              : "info";
        const unread = !ins.read_at;
        rows.push({
          id: `ins-${ins.id}`,
          severity: sev,
          badge: typ.replace(/_/g, " ") || "Insight",
          timeLabel: formatRelativeTime(ins.created_at as string),
          title: String(ins.title || "Insight"),
          body: String(ins.body || "").slice(0, 280),
          actions: [
            { label: "Subscriptions", onClick: goSubs },
            ...(unread && authUser?.id
              ? [{ label: "Mark read", variant: "ghost" as const, onClick: () => void markRead(Number(ins.id)) }]
              : []),
          ],
        });
      }
    }

    const ax = Array.isArray(anomalies) ? anomalies : [];
    for (const a of ax.slice(0, 4)) {
      const rec = a as Record<string, unknown>;
      const lvl = String(rec.risk_level || "MEDIUM").toUpperCase();
      const sev: FeedItem["severity"] =
        lvl === "CRITICAL" ? "critical" : lvl === "HIGH" ? "warning" : "info";
      rows.push({
        id: `anom-${rec.id}`,
        severity: sev,
        badge: `Anomaly · ${lvl}`,
        timeLabel: formatRelativeTime(rec.transaction_date as string),
        title: String(rec.merchant || rec.description || "Suspicious transaction"),
        body: `Risk score ${Number(rec.risk_score || 0).toFixed(0)} · Review in Transactions.`,
        rightLabel: "Amount",
        rightValue: apiUtils.formatINR(Number(rec.amount || 0)),
        actions: [{ label: "View transactions", onClick: goTxn }],
      });
    }

    if (Array.isArray(healthRec) && healthRec[0]) {
      rows.push({
        id: "health-rec",
        severity: "positive",
        badge: "Health",
        timeLabel: "Guidance",
        title: "Financial health tip",
        body: String(healthRec[0]).slice(0, 240),
        actions: [{ label: "Insights", onClick: goInsights }],
      });
    }

    return rows.slice(0, 6);
  }, [canLiveIntel, aiIntel.insights, anomalies, healthRec, authUser?.id, setActiveTab]);

  // ── Loading / error states ───────────────────────────────────────────────
  if (loading) {
    return (
      <DashboardWrapper>
        <div className="space-y-6">
          <SkeletonCard lines={3} height={84} />
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <SkeletonCard key={i} lines={4} height={170} />
            ))}
          </div>
        </div>
      </DashboardWrapper>
    );
  }
  if (error) {
    return (
      <DashboardWrapper>
        <ErrorCard message={error} onRetry={onDataRefresh} />
      </DashboardWrapper>
    );
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <DashboardWrapper>
      {/* Partial-data warning — exclude anomalyStats since Dashboard doesn't render it */}
      {Array.isArray(loadWarnings) && (loadWarnings as string[]).filter((w) => !w.startsWith("anomalyStats:")).length > 0 && (
        <div
          role="status"
          className="rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-4 py-2.5 text-sm text-amber-200"
        >
          <span className="font-semibold">Partial data: </span>
          {(loadWarnings as string[]).filter((w) => !w.startsWith("anomalyStats:")).join(" · ")}
        </div>
      )}

      {/* 1 — Greeting */}
      <DashboardGreeting
        monthSpend={monthSpend}
        monthIncome={monthIncome}
        // Prefer the dashboard endpoint's count (single source of truth);
        // fall back to the per-feature intel call we already make below.
        fraudPending={dashFraudPending || intel.fraudPending}
        savedYtd={savedYtd}
        lastSync={dashLastSynced}
        lastLogin={dashLastLogin}
        loading={dashHeaderLoading}
      />

      {/* 2 — KPI row */}
      <section className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <KPICard
          variant="purple"
          label="Available balance (MTD)"
          value={netMonth}
          formatValue={apiUtils.formatINR}
          subtitle="Net of credits − debits this month"
          icon={Wallet}
          trendPct={netDeltaPct}
          sparkline={sparkIncome}
          delay={0}
        />
        <KPICard
          variant="rose"
          label="This month spend"
          value={monthSpend}
          formatValue={apiUtils.formatINR}
          subtitle={`${month}/${year}`}
          icon={Receipt}
          trendPct={spendDeltaPct}
          sparkline={sparkExpense}
          delay={0.06}
        />
        <KPICard
          variant="emerald"
          label="Saved this year"
          value={savedYtd}
          formatValue={apiUtils.formatINR}
          subtitle="Sum of monthly savings YTD"
          icon={PiggyBank}
          sparkline={sparkSaved}
          delay={0.12}
        />
      </section>

      {/* 3 — Quick actions row (no truncation) */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <QuickActionCard
          variant="emerald"
          icon={Shield}
          title="FraudShield"
          status={intel.fraudPending > 0
            ? `${intel.fraudPending} pending alert${intel.fraudPending > 1 ? "s" : ""}`
            : "All clear · 0 pending alerts"}
          badge={intel.fraudPending}
          onClick={() => setActiveTab?.("fraud")}
          delay={0}
        />
        <QuickActionCard
          variant="purple"
          icon={Sparkles}
          title="Subscriptions AI"
          status={intel.monthlyWaste > 0
            ? `${apiUtils.formatINR(intel.monthlyWaste)} wasted/mo`
            : "No obvious waste this month"}
          onClick={() => setActiveTab?.("subscriptions")}
          delay={0.05}
        />
        <QuickActionCard
          variant="amber"
          icon={EyeOff}
          title="Dark Patterns"
          status={`${intel.darkCount} caught this month`}
          badge={intel.darkCount}
          onClick={() => setActiveTab?.("dark-patterns")}
          delay={0.10}
        />
        <QuickActionCard
          variant="cyan"
          icon={CreditCard}
          title="EMI Tracker"
          status={`${intel.emiCount} active EMI${intel.emiCount === 1 ? "" : "s"} tracked`}
          onClick={() => setActiveTab?.("emi")}
          delay={0.15}
        />
      </section>

      {/* 4 — Health gauge + Living budget */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Health Score */}
        <PremiumCard variant="purple" topAccent interactive={false}>
          <div className="mb-2 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">
                Financial Health
              </p>
              <h2 className="mt-1 text-xl font-semibold text-white">
                Your money health score
              </h2>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-emerald-300">
              <span className="h-1 w-2 rounded-full bg-emerald-400" />
              Stable
            </span>
          </div>

          <HealthScoreGauge
            healthData={health ?? {}}
            narration={healthNarrationLine}
            variant="hero"
          />

          {Object.keys(healthComp).length > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-2">
              {[
                ["Savings",       healthComp.savings_points,    30],
                ["Security",      healthComp.anomaly_points,    20],
                ["Expense ratio", healthComp.expense_points,    25],
                ["Consistency",   healthComp.consistency_points,15],
              ].map(([label, val, max]) => {
                const pct = Math.round((Number(val || 0) / Number(max || 1)) * 100);
                return (
                  <div
                    key={String(label)}
                    className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5"
                  >
                    <div className="flex items-baseline justify-between">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
                        {String(label)}
                      </p>
                      <p className="text-sm font-bold tabular-nums text-white">{pct}%</p>
                    </div>
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/[0.05]">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-purple-500 to-fuchsia-400"
                        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </PremiumCard>

        {/* Living budget engine — wrap NerveCentreCard in PremiumCard styling */}
        <PremiumCard variant="emerald" topAccent interactive={false} className="!p-0">
          <NerveCentreCard userId={userId} setActiveTab={setActiveTab} />
        </PremiumCard>
      </section>

      {/* 5 — Live AI insights */}
      <LiveInsightsFeed
        items={feedItems}
        loading={Boolean(canLiveIntel && aiIntel.loading && feedItems.length === 0)}
        onViewAll={() => setActiveTab?.("insights")}
      />

      {/* 6 — Spending charts */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <PremiumCard variant="purple" interactive={false}>
            <MonthlyTrendChart trendsData={trends} animateOnView={true} />
          </PremiumCard>
        </div>
        <div className="lg:col-span-5">
          <PremiumCard variant="cyan" interactive={false}>
            <SpendingPieChart
              spendingData={spending}
              month={month}
              year={year}
              prevMonthExpense={prevMonthExpense}
              animateOnView={true}
            />
          </PremiumCard>
        </div>
      </section>

      {/* 7 — Footer */}
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] pt-5 text-[11px] text-gray-500">
        <button
          type="button"
          onClick={onDataRefresh}
          className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-purple-500/25 hover:bg-purple-500/[0.06] hover:text-white"
          title={
            (dashLastSynced ?? dashLastLogin)
              ? (dashLastSynced ?? dashLastLogin)!.toLocaleString("en-IN")
              : undefined
          }
        >
          <RefreshCw size={13} aria-hidden />
          {dashLastSynced
            ? `Bank synced ${formatRelativeMinutes(dashLastSynced)} · Tap to refresh`
            : dashLastLogin
              ? `Last active ${formatRelativeMinutes(dashLastLogin)} · Tap to refresh`
              : "Tap to refresh dashboard"}
        </button>
        <span className="tabular-nums text-gray-600">
          build {process.env.REACT_APP_BUILD || "dev"} · DPDP-aware · WCAG-AA ready
        </span>
      </footer>
    </DashboardWrapper>
  );
}

// ─── Page wrapper ─────────────────────────────────────────────────────────────
// Solid bg-[#0A0612] masks the global aurora orbs so the dashboard feels flat
// and focused. Only the dashboard page is affected — other pages keep their
// existing aurora background.
function DashboardWrapper({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative -mx-4 -mt-4 min-h-[calc(100vh-4rem)] bg-[#0A0612] px-4 pt-6 sm:-mx-5 sm:-mt-5 sm:px-5 sm:pt-7 lg:-mx-7 lg:-mt-7 lg:px-7 lg:pt-8">
      {/* Star/particle background — same AuroraBackground used on the Transactions page */}
      <AuroraBackground variant="app" starCount={48} />

      {/* Very subtle radial gradient — barely perceptible accent */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          background:
            "radial-gradient(circle at 90% -10%, rgba(139,92,246,0.06) 0%, transparent 55%)",
        }}
      />
      <div className="relative z-10 mx-auto max-w-7xl space-y-8 pb-24">
        {children}
      </div>
    </main>
  );
}
