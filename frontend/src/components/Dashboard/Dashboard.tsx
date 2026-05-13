/**
 * Summary dashboard: KPIs, health, guardian shortcuts, charts only.
 * AI Guardian + inline anomalies/transactions removed (duplicates Insights, Simulator,
 * FraudShield, Transactions tabs). Readability: opaque `GlassCard surface="panel"` on charts;
 * Aurora variant="app" + solid TopBar in shell.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";
import {
  BadgeCheck,
  Landmark,
  PiggyBank,
  Receipt,
  RefreshCw,
  Shield,
  Sparkles,
  Wallet,
} from "lucide-react";
import useSmartSpend from "../../hooks/useSmartSpend";
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
import { GlassCard } from "../intro/GlassCard";
import { ShieldMark } from "../intro/ShieldMark";
import { SkeletonStats } from "../common/SkeletonCard";
import GuardianPill from "./shared/GuardianPill";
import { KPITile } from "./shared/KPITile";
import NerveCentreCard from "./NerveCentreCard";
import AIFinancialCommandCenter, { type CommandCard } from "./AIFinancialCommandCenter";
import LiveInsightsFeed, { type FeedItem } from "./LiveInsightsFeed";

const monthKey = (y: number, m: number) => `${y}-${String(m).padStart(2, "0")}`;

function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "Recently";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "Recently";
  const mins = Math.floor((Date.now() - t) / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

type TrendPoint = { month: string; income?: number; expense?: number; saved?: number };

type NextFest = { name: string; days_remaining: number } | null;

type DashboardProps = {
  userId: number;
  month: number;
  year: number;
  onMonthChange?: (m: number) => void;
  onYearChange?: (y: number) => void;
  userName?: string;
  setActiveTab?: (tab: string) => void;
};

export default function Dashboard({
  userId,
  month,
  year,
  userName = "there",
  setActiveTab,
}: DashboardProps) {
  const reduce = useReducedMotion();
  const { user: authUser } = useAuth();
  const { spending, trends, health, anomalies, loading, error, loadWarnings, refetch } = useSmartSpend(
    userId,
    month,
    year
  );
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
  const [lastRefresh, setLastRefresh] = useState<Date>(() => new Date());

  const row3Ref = useRef<HTMLElement | null>(null);
  const r3 = useInView(row3Ref, { once: true, amount: 0.2 });

  const onDataRefresh = useCallback(async () => {
    await refetch();
    setLastRefresh(new Date());
  }, [refetch]);

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
        const pending = (alertsRes?.alerts || []).filter((a: { user_action?: string }) => a.user_action === "PENDING").length;
        const waste = Number(subsRes?.monthly_waste || 0);
        const nf = festRes?.next_festival || null;
        const darkList = darkRes?.patterns || (Array.isArray(darkRes) ? darkRes : []) || [];
        const darkCount = Array.isArray(darkList) ? darkList.length : 0;
        const emis = emiRes?.emis_detected || emiRes?.emis || [];
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
    return () => {
      cancelled = true;
    };
  }, [userId]);

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
    return () => {
      cancelled = true;
    };
  }, [userId, month, year]);

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
    return () => {
      cancelled = true;
    };
  }, [canLiveIntel, authUser?.id]);

  const displayName = (userName || "there").trim() || "there";

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  }, []);

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
    return (Array.isArray(spending) ? spending : []).reduce((acc: number, row: { total_amount?: number }) => acc + Number(row.total_amount || 0), 0);
  }, [trendRow, spending]);

  const netMonth = useMemo(() => {
    if (!trendRow) return 0;
    // Match KPI subtitle: net of credits − debits (API `saved` clamps at 0 for “savings” semantics).
    return Number(trendRow.income || 0) - Number(trendRow.expense || 0);
  }, [trendRow]);

  const savedYtd = useMemo(() => {
    return trendList
      .filter((t) => String(t.month || "").startsWith(`${year}-`))
      .reduce((acc: number, t) => acc + Number(t.saved || 0), 0);
  }, [trendList, year]);

  const sparkExpense = useMemo(() => {
    return trendList.slice(-6).map((t) => Number(t.expense || 0));
  }, [trendList]);

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

  const savedSpark = useMemo(() => {
    return trendList.slice(-6).map((t) => Number(t.saved || 0));
  }, [trendList]);

  const healthRec = health && typeof health === "object" && "recommendations" in health ? (health as { recommendations?: string[] }).recommendations : undefined;
  const healthNarrationLine =
    narration || (Array.isArray(healthRec) && healthRec[0]) || "Your guardian is monitoring cashflow, subscriptions, and anomalies.";

  const healthComp =
    health && typeof health === "object" && "components" in health
      ? ((health as { components?: Record<string, number> }).components || {})
      : {};

  const commandCards = useMemo((): CommandCard[] => {
    const goSubs = () => setActiveTab?.("subscriptions");
    const goFraud = () => setActiveTab?.("fraud");
    const goInsights = () => setActiveTab?.("insights");
    const out: CommandCard[] = [];

    if (canLiveIntel && aiIntel.summary?.success) {
      const sum = aiIntel.summary;
      const s = sum.summary;
      const v = sum.verdicts || {};
      const declining = (v.declining || []) as Array<Record<string, unknown>>;
      const dormant = (v.dormant || []) as Array<Record<string, unknown>>;
      const firstRisk = declining[0] || dormant[0];
      const waste = Number(s?.verdict_monthly_waste_sum_inr || 0);
      const atRisk = Number(s?.at_risk_count || 0);
      if (atRisk > 0 || waste > 0.01) {
        out.push({
          id: "risk-waste",
          urgency: "critical",
          badge: "Critical",
          title: firstRisk
            ? `${String(firstRisk.subscription_name || "Subscription")} flagged`
            : "Subscription waste detected",
          body: String(
            firstRisk?.reasoning || "Declining or dormant usage — review renewals and overlap."
          ),
          metricLabel: "Flagged waste",
          metricValue: `${apiUtils.formatINR(waste)}/mo`,
          ctaLabel: "Review",
          onCta: goSubs,
        });
      }
      const upgrades = (v.upgrade_recommended || []) as Array<Record<string, unknown>>;
      const u0 = upgrades[0];
      if (u0) {
        out.push({
          id: "upgrade",
          urgency: "opportunity",
          badge: "Opportunity",
          title: `${String(u0.subscription_name || "Subscription")} — upgrade signal`,
          body: String(u0.reasoning || "High in-app time may justify a paid tier."),
          metricLabel: "Usage (30d)",
          metricValue: `${Number(u0.current_usage_hours || 0).toFixed(0)}h`,
          ctaLabel: "Review",
          onCta: goSubs,
        });
      }
      const mig = (sum.migrations || []) as Array<Record<string, unknown>>;
      const m0 = mig[0];
      if (m0 && out.length < 3) {
        out.push({
          id: "migration",
          urgency: "warning",
          badge: "Migration",
          title: String(m0.title || "Category shift"),
          body: String(m0.description || "We detected a usage migration in the same category."),
          metricLabel: "Save up to",
          metricValue: `${apiUtils.formatINR(Number(m0.potential_savings_monthly || 0))}/mo`,
          ctaLabel: "Subscriptions",
          onCta: goSubs,
        });
      }
      if (out.length < 3) {
        const ytdSave = Number(s?.savings_amount_saved_ytd_inr || 0);
        out.push({
          id: "savings-ytd",
          urgency: "safe",
          badge: "Optimization",
          title: "Year-to-date subscription savings",
          body: "Ledgered wins from cancellations and prevention.",
          metricLabel: "Saved YTD",
          metricValue: apiUtils.formatINR(ytdSave),
          ctaLabel: "Details",
          onCta: goSubs,
        });
      }
      return out.slice(0, 3);
    }

    if (intel.monthlyWaste > 0.01) {
      out.push({
        id: "waste-fallback",
        urgency: "warning",
        badge: "Warning",
        title: "Possible subscription waste",
        body: "Leakage flagged for this workspace view.",
        metricLabel: "Est. monthly waste",
        metricValue: apiUtils.formatINR(intel.monthlyWaste),
        ctaLabel: "Subscriptions",
        onCta: goSubs,
      });
    }
    if (intel.fraudPending > 0) {
      out.push({
        id: "fraud",
        urgency: "critical",
        badge: "Critical",
        title: `${intel.fraudPending} FraudShield alert${intel.fraudPending > 1 ? "s" : ""}`,
        body: "Review before large transfers or new payees.",
        metricLabel: "Queue",
        metricValue: String(intel.fraudPending),
        ctaLabel: "Open FraudShield",
        onCta: goFraud,
      });
    }
    out.push({
      id: "intel-tip",
      urgency: "info",
      badge: "Info",
      title: canLiveIntel ? "Signals warming up" : "Live subscription AI",
      body: canLiveIntel
        ? "We will populate this rail as new verdicts and migrations arrive."
        : "Switch the workspace selector to your signed-in user to stream subscription intelligence here.",
      ctaLabel: canLiveIntel ? "Insights" : "Transactions",
      onCta: canLiveIntel ? goInsights : () => setActiveTab?.("transactions"),
    });
    return out.slice(0, 3);
  }, [canLiveIntel, aiIntel.summary, intel.monthlyWaste, intel.fraudPending, setActiveTab]);

  const aiSignalCount = useMemo(() => {
    let n = 0;
    if (canLiveIntel && aiIntel.summary?.success) {
      const s = aiIntel.summary.summary;
      n += Number(s?.at_risk_count || 0) > 0 ? 1 : 0;
      n += Number(s?.migrations_detected || 0) > 0 ? 1 : 0;
      n += Number(s?.upgrade_recommended_count || 0) > 0 ? 1 : 0;
      n += 4;
    } else {
      n = 3 + (intel.fraudPending > 0 ? 2 : 0) + (intel.monthlyWaste > 0 ? 1 : 0);
    }
    return Math.max(4, Math.min(14, n));
  }, [canLiveIntel, aiIntel.summary, intel.fraudPending, intel.monthlyWaste]);

  const feedItems = useMemo((): FeedItem[] => {
    const rows: FeedItem[] = [];
    const goSubs = () => setActiveTab?.("subscriptions");
    const goTxn = () => setActiveTab?.("transactions");
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
      } catch {
        /* ignore */
      }
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

    return rows.slice(0, 8);
  }, [canLiveIntel, aiIntel.insights, anomalies, healthRec, authUser?.id, setActiveTab]);

  if (loading) {
    return (
      <main className="relative mx-auto max-w-[1600px] px-0 pb-24 pt-2 md:pb-8">
        <GlassCard surface="panel" className="mb-4 border-white/[0.08]">
          <SkeletonStats />
        </GlassCard>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <GlassCard key={i} surface="panel" padding="sm" className="h-48 animate-ss-shimmer bg-[length:200%_100%]">
              <div className="h-4 w-1/3 rounded bg-white/[0.06]" />
              <div className="mt-6 h-8 w-2/3 rounded bg-white/[0.06]" />
            </GlassCard>
          ))}
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="relative mx-auto max-w-[1600px] px-0 pt-2">
        <ErrorCard message={error} onRetry={onDataRefresh} />
      </main>
    );
  }

  const festSub =
    intel.nextFest != null
      ? `${intel.nextFest.name} is in ${intel.nextFest.days_remaining} days`
      : "Your money is calm today.";

  const fadeIn = { initial: reduce ? false : { opacity: 0, y: 14 }, animate: { opacity: 1, y: 0 } };

  return (
    <motion.main
      className="relative mx-auto max-w-[1600px] px-0 pb-28 pt-1 md:pb-10"
      initial={reduce ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: reduce ? 0.15 : 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      {Array.isArray(loadWarnings) && loadWarnings.length > 0 ? (
        <div
          role="status"
          className="mb-4 rounded-xl border border-amber-400/25 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-50/95"
        >
          <span className="font-semibold text-amber-100">Partial data: </span>
          {loadWarnings.join(" · ")}
        </div>
      ) : null}
      <p className="mb-4 text-sm leading-relaxed text-white/60">
        <span className="font-semibold text-white">{greeting}, {displayName}</span>
        <span className="text-white/35"> · </span>
        <span>{festSub}</span>
      </p>

      <AIFinancialCommandCenter
        signalCount={aiSignalCount}
        cards={commandCards}
        loading={Boolean(canLiveIntel && aiIntel.loading)}
        aiActive={canLiveIntel && !aiIntel.loading && Boolean(aiIntel.summary?.success)}
      />

      {/* Row 1 — KPIs + health */}
      <section className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-12 xl:gap-6">
        <div className="space-y-4 xl:col-span-7">
          <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] sm:grid sm:grid-cols-3 sm:overflow-visible [&::-webkit-scrollbar]:hidden">
            <div className="min-w-[min(100%,280px)] shrink-0 snap-center sm:min-w-0">
              <KPITile
                title="Available balance (MTD)"
                value={apiUtils.formatINR(netMonth)}
                subtitle="Net of credits − debits this month"
                icon={Wallet}
                trendPct={netDeltaPct}
                sparklineValues={sparkExpense}
                delay={0}
              />
            </div>
            <div className="min-w-[min(100%,280px)] shrink-0 snap-center sm:min-w-0">
              <KPITile
                title="This month spend"
                value={apiUtils.formatINR(monthSpend)}
                subtitle={`${month}/${year}`}
                icon={Receipt}
                trendPct={spendDeltaPct}
                sparklineValues={sparkExpense}
                delay={reduce ? 0 : 0.08}
              />
            </div>
            <div className="min-w-[min(100%,280px)] shrink-0 snap-center sm:min-w-0">
              <KPITile
                title="Saved this year"
                value={apiUtils.formatINR(savedYtd)}
                subtitle="Sum of monthly savings in calendar year"
                icon={PiggyBank}
                sparklineValues={savedSpark}
                delay={reduce ? 0 : 0.16}
              />
            </div>
          </div>
        </div>

        <div className="relative space-y-4 xl:col-span-5">
          <motion.div
            className="pointer-events-none absolute right-2 top-4 opacity-[0.08]"
            aria-hidden
            animate={reduce ? undefined : { rotate: 360 }}
            transition={{ duration: 120, repeat: Infinity, ease: "linear" }}
          >
            <ShieldMark stage="complete" size={200} />
          </motion.div>
          <HealthScoreGauge healthData={health ?? {}} narration={healthNarrationLine} variant="hero" />
          {Object.keys(healthComp).length > 0 ? (
            <div className="grid grid-cols-2 gap-3 rounded-2xl border border-white/[0.08] bg-black/20 p-4 md:grid-cols-4">
              {[
                ["Savings", healthComp.savings_points, 30],
                ["Security", healthComp.anomaly_points, 20],
                ["Expense ratio", healthComp.expense_points, 25],
                ["Consistency", healthComp.consistency_points, 15],
              ].map(([label, val, max]) => (
                <div key={String(label)} className="text-center">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-white/45">{label}</p>
                  <p className="mt-1 font-heading text-xl font-bold tabular-nums text-white">
                    {Math.round((Number(val || 0) / Number(max || 1)) * 100)}%
                  </p>
                  <p className="text-[10px] text-white/35">
                    {Number(val || 0).toFixed(0)}/{max}
                  </p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <LiveInsightsFeed
        items={feedItems}
        loading={Boolean(canLiveIntel && aiIntel.loading && feedItems.length === 0)}
        onViewAll={() => setActiveTab?.("insights")}
      />

      <motion.section
        className="mt-6"
        initial={reduce ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: reduce ? 0 : 0.12, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <NerveCentreCard userId={userId} setActiveTab={setActiveTab} />
      </motion.section>

      {/* Row 2 — Guardian strip */}
      <motion.section
        className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
        initial={reduce ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: reduce ? 0 : 0.2, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <GuardianPill
          label="FraudShield"
          sub={`${intel.fraudPending} pending alerts`}
          icon={Shield}
          glow={intel.fraudPending > 0 ? "rose" : "violet"}
          disabled={intel.loading}
          delay={0}
          onClick={() => setActiveTab?.("fraud")}
        />
        <GuardianPill
          label="Subscriptions"
          sub={intel.monthlyWaste > 0 ? `${apiUtils.formatINR(intel.monthlyWaste)} wasted/mo` : "No obvious waste"}
          icon={Sparkles}
          glow={intel.monthlyWaste > 0 ? "amber" : "cyan"}
          disabled={intel.loading}
          delay={reduce ? 0 : 0.06}
          onClick={() => setActiveTab?.("subscriptions")}
        />
        <GuardianPill
          label="Dark Patterns"
          sub={`${intel.darkCount} caught this month`}
          icon={Landmark}
          glow="violet"
          disabled={intel.loading}
          delay={reduce ? 0 : 0.12}
          onClick={() => setActiveTab?.("dark-patterns")}
        />
        <GuardianPill
          label="EMI Tracker"
          sub={`${intel.emiCount} active EMIs tracked`}
          icon={Receipt}
          glow="cyan"
          disabled={intel.loading}
          delay={reduce ? 0 : 0.18}
          onClick={() => setActiveTab?.("emi")}
        />
      </motion.section>

      {/* Row 3 — Spending story */}
      <motion.section
        ref={row3Ref}
        className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-6"
        {...fadeIn}
        transition={{ duration: reduce ? 0.15 : 0.5, ease: [0.22, 1, 0.36, 1], delay: reduce || !r3 ? 0 : 0 }}
      >
        <div className="lg:col-span-7">
          <MonthlyTrendChart trendsData={trends} animateOnView={Boolean(r3 || reduce)} />
        </div>
        <div className="lg:col-span-5">
          <SpendingPieChart
            spendingData={spending}
            month={month}
            year={year}
            prevMonthExpense={prevMonthExpense}
            animateOnView={Boolean(r3 || reduce)}
          />
        </div>
      </motion.section>

      {/* Row 4 — Footer */}
      <footer className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] pt-4 text-[11px] text-exiqo-glow/55">
        <button
          type="button"
          onClick={() => onDataRefresh()}
          className="inline-flex min-h-[48px] items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-exiqo-glow/90 transition hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 md:min-h-0"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          Last refreshed {Math.max(1, Math.round((Date.now() - lastRefresh.getTime()) / 60000))} min ago · Tap to refresh
        </button>
        <div className="flex flex-wrap items-center gap-3">
          <span className="tabular-nums opacity-80">build {process.env.REACT_APP_BUILD || "dev"}</span>
          <span className="inline-flex items-center gap-1 text-exiqo-glow/70">
            <BadgeCheck className="h-3.5 w-3.5 text-emerald-400/90" aria-hidden />
            AA-ready
          </span>
          <span className="inline-flex items-center gap-1 text-exiqo-glow/70">
            <Shield className="h-3.5 w-3.5 text-exiqo-purple" aria-hidden />
            DPDP-aware
          </span>
        </div>
      </footer>
    </motion.main>
  );
}
