import React, { useCallback, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  CheckCircle,
  DollarSign,
  ExternalLink,
  Gavel,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useSubscriptionIntelligence } from "../context/SubscriptionIntelligenceContext";
import { persistMigrations } from "../services/subscriptionIntelligence";
import { useToast } from "../components/common/Toast";
import { SkeletonCard } from "../components/common/SkeletonCard";
import { PageHeader } from "../components/Dashboard/shared/PageHeader";
import { GlassCard } from "../components/intro/GlassCard";
import SubscriptionDetailModal from "../components/Subscriptions/SubscriptionDetailModal";
import { inr } from "../lib/format";

const VERDICT_BUCKETS = [
  { key: "thriving", title: "Thriving", Icon: TrendingUp, accent: "emerald" },
  { key: "declining", title: "Declining", Icon: TrendingDown, accent: "amber" },
  { key: "dormant", title: "Dormant", Icon: AlertTriangle, accent: "orange" },
  { key: "upgrade_recommended", title: "Upgrade recommended", Icon: Zap, accent: "purple" },
];

const accentRing = {
  emerald: "ring-emerald-500/30 border-emerald-500/20 bg-emerald-500/10",
  amber: "ring-amber-500/30 border-amber-500/20 bg-amber-500/10",
  orange: "ring-orange-500/30 border-orange-500/20 bg-orange-500/10",
  purple: "ring-purple-500/30 border-purple-500/20 bg-purple-500/10",
  cyan: "ring-cyan-500/30 border-cyan-500/20 bg-cyan-500/10",
  rose: "ring-rose-500/30 border-rose-500/20 bg-rose-500/10",
};

function InsightTypeIcon({ type }) {
  const t = String(type || "").toLowerCase();
  if (t.includes("migration")) {
    return <ArrowRight className="h-5 w-5 shrink-0 text-cyan-300" aria-hidden />;
  }
  if (t.includes("substitution")) {
    return <Sparkles className="h-5 w-5 shrink-0 text-violet-300" aria-hidden />;
  }
  if (t.includes("verdict")) {
    return <Gavel className="h-5 w-5 shrink-0 text-amber-300" aria-hidden />;
  }
  return <Zap className="h-5 w-5 shrink-0 text-white/40" aria-hidden />;
}

function insightToDetailRow(ins) {
  return {
    subscription_id: ins.subscription_id,
    subscription_name: ins.title,
    body: ins.body,
    reasoning: ins.body,
    verdict: ins.insight_type,
    monthly_cost: 0,
    confidence_score: 0.55,
  };
}

export default function SubscriptionIntelligence({ onOpenReminders }) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const {
    userId,
    summary,
    migrations,
    insights,
    savings,
    loading,
    savingsLoading,
    refreshAll,
    createReminders,
    markInsightReadById,
  } = useSubscriptionIntelligence();

  const [refreshing, setRefreshing] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [persisting, setPersisting] = useState(false);
  const [detailRow, setDetailRow] = useState(null);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshAll();
      showToast("Analysis refreshed", "success");
    } catch (e) {
      showToast(e?.message || "Refresh failed", "error");
    } finally {
      setRefreshing(false);
    }
  }, [refreshAll, showToast]);

  const handleScheduleReminders = useCallback(async () => {
    setScheduling(true);
    try {
      await createReminders();
      showToast("Reminders scheduled for upcoming renewals", "success");
    } catch (e) {
      showToast(e?.message || "Could not schedule reminders", "error");
    } finally {
      setScheduling(false);
    }
  }, [createReminders, showToast]);

  const handlePersistMigrations = useCallback(async () => {
    if (!userId) return;
    setPersisting(true);
    try {
      const res = await persistMigrations(userId);
      showToast(`Saved ${res.upserted || 0} migration insight(s)`, "success");
      await refreshAll();
    } catch (e) {
      showToast(e?.message || "Persist failed", "error");
    } finally {
      setPersisting(false);
    }
  }, [userId, refreshAll, showToast]);

  if (!user?.id) {
    return (
      <GlassCard surface="panel" padding="md" className="border-white/10">
        <p className="text-center text-white/70">Sign in to view subscription intelligence.</p>
      </GlassCard>
    );
  }

  if (loading && !summary) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <SkeletonCard lines={5} height={120} />
        <SkeletonCard lines={4} height={200} />
      </div>
    );
  }

  const s = summary?.summary;

  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-4">
      <PageHeader
        eyebrow="AI + behaviour"
        title="Subscription intelligence"
        subtitle="Verdicts, category migrations, savings rollups, and unread insights — refreshed from your live data."
        accentHex="#22d3ee"
        rightSlot={
          <div className="flex flex-wrap justify-end gap-2">
            {typeof onOpenReminders === "function" ? (
              <button
                type="button"
                onClick={onOpenReminders}
                className="inline-flex min-h-[48px] items-center gap-2 rounded-xl border border-amber-400/35 bg-amber-500/15 px-4 py-2.5 text-sm font-semibold text-amber-100 transition hover:bg-amber-500/25 md:min-h-0"
              >
                <Bell className="h-4 w-4" aria-hidden />
                Smart reminders
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex min-h-[48px] items-center gap-2 rounded-xl border border-white/15 bg-white/[0.06] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.1] disabled:opacity-50 md:min-h-0"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden />
              Refresh analysis
            </button>
            <button
              type="button"
              onClick={handleScheduleReminders}
              disabled={scheduling}
              className="inline-flex min-h-[48px] items-center gap-2 rounded-xl border border-violet-400/40 bg-violet-500/20 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-500/30 disabled:opacity-50 md:min-h-0"
            >
              <Bell className="h-4 w-4" aria-hidden />
              Schedule reminders
            </button>
          </div>
        }
      />

      {/* Savings */}
      <GlassCard surface="panel" padding="md" className="border-emerald-500/25">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-200">
            <DollarSign className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h2 className="font-heading text-lg font-semibold text-white">Savings dashboard</h2>
            <p className="text-sm text-white/55">From tracked cancellations and waste avoided (subscription savings ledger).</p>
          </div>
        </div>
        {savingsLoading && !savings ? (
          <SkeletonCard lines={2} height={72} />
        ) : savings ? (
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile
              label="This month"
              value={inr(savings.this_month?.amount_saved_inr)}
              hint={`${savings.this_month?.subscriptions_cancelled || 0} cancelled`}
              ring="emerald"
            />
            <StatTile
              label="This year"
              value={inr(savings.this_year?.amount_saved_inr)}
              hint={`${savings.this_year?.subscriptions_cancelled || 0} cancelled`}
              ring="cyan"
            />
            <StatTile
              label="All time"
              value={inr(savings.all_time?.amount_saved_inr)}
              hint={`${savings.all_time?.subscriptions_cancelled || 0} total`}
              ring="purple"
            />
          </div>
        ) : (
          <p className="text-sm text-white/55">No savings rows yet — data appears after cancellations are recorded.</p>
        )}
      </GlassCard>

      {/* Roll-up stats */}
      {s ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Subscriptions tracked"
            value={String(s.subscriptions_tracked ?? 0)}
            hint="In intelligence scope"
            ring="cyan"
            icon={<CheckCircle className="h-4 w-4 text-emerald-300" aria-hidden />}
          />
          <StatTile
            label="Thriving"
            value={String(s.thriving_count ?? 0)}
            hint="Healthy usage"
            ring="emerald"
            icon={<TrendingUp className="h-4 w-4 text-emerald-300" aria-hidden />}
          />
          <StatTile
            label="At risk"
            value={String(s.at_risk_count ?? 0)}
            hint="Declining + dormant"
            ring="amber"
            icon={<AlertTriangle className="h-4 w-4 text-amber-200" aria-hidden />}
          />
          <StatTile
            label="Flagged waste"
            value={`${inr(s.verdict_monthly_waste_sum_inr || 0)}/mo`}
            hint={`~${inr(s.verdict_yearly_waste_sum_inr || 0)} /yr`}
            ring="rose"
            icon={<DollarSign className="h-4 w-4 text-rose-200" aria-hidden />}
          />
        </div>
      ) : null}

      {/* Verdicts */}
      {summary?.verdicts ? (
        <section className="space-y-4">
          <h2 className="font-heading text-xl font-semibold text-white">AI verdicts</h2>
          {VERDICT_BUCKETS.map(({ key, title, Icon, accent }) => {
            const list = summary.verdicts[key] || [];
            if (!list.length) return null;
            return (
              <GlassCard
                key={key}
                surface="panel"
                padding="md"
                className={`border ring-1 ${accentRing[accent]}`}
              >
                <div className="mb-3 flex items-center gap-2">
                  <Icon className="h-5 w-5 text-white/80" aria-hidden />
                  <h3 className="font-semibold text-white">{title}</h3>
                  <span className="ml-auto text-xs font-semibold text-white/50">{list.length}</span>
                </div>
                <ul className="space-y-3">
                  {list.map((v) => (
                    <li key={v.subscription_id}>
                      <button
                        type="button"
                        onClick={() =>
                          setDetailRow({
                            ...v,
                            verdict: key,
                          })
                        }
                        className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-left transition hover:border-violet-400/40 hover:bg-white/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
                      >
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <p className="font-semibold text-white">{v.subscription_name || "Subscription"}</p>
                            <p className="mt-1 text-sm leading-relaxed text-white/65">{v.reasoning}</p>
                            {typeof v.current_usage_hours === "number" ? (
                              <p className="mt-2 text-xs text-white/45">
                                Usage (30d): {v.current_usage_hours.toFixed(1)}h / mo
                              </p>
                            ) : null}
                          </div>
                          <div className="shrink-0 text-right">
                            <p className="text-lg font-bold text-white">{inr(v.monthly_cost)}</p>
                            <p className="text-[11px] text-white/45">per month · tap for details</p>
                          </div>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              </GlassCard>
            );
          })}
          {VERDICT_BUCKETS.every(({ key }) => !(summary.verdicts[key] || []).length) ? (
            <GlassCard surface="panel" padding="md" className="border-white/10">
              <p className="text-sm text-white/60">No verdict buckets yet. Link usage or add subscriptions, then refresh.</p>
            </GlassCard>
          ) : null}
        </section>
      ) : null}

      {/* Migrations */}
      <section className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <h2 className="font-heading text-xl font-semibold text-white">Category migrations</h2>
          {migrations?.length ? (
            <button
              type="button"
              onClick={handlePersistMigrations}
              disabled={persisting}
              className="inline-flex min-h-[48px] items-center justify-center rounded-xl border border-cyan-400/35 bg-cyan-500/15 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/25 disabled:opacity-50 md:min-h-0"
            >
              {persisting ? "Saving…" : "Persist to insight feed"}
            </button>
          ) : null}
        </div>
        {migrations?.length ? (
          <ul className="space-y-3">
            {migrations.map((m) => (
              <li key={`${m.primary_subscription_id}-${m.secondary_subscription_id}`}>
                <GlassCard surface="panel" padding="md" className="border-cyan-500/20 ring-1 ring-cyan-500/15">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-white">{m.title}</h3>
                      <p className="mt-2 text-sm text-white/70">{m.description}</p>
                      <p className="mt-2 text-sm font-medium text-cyan-200/90">{m.recommendation}</p>
                    </div>
                    <div className="shrink-0 text-right lg:pl-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-white/45">Potential</p>
                      <p className="text-xl font-bold text-emerald-300">{inr(m.potential_savings_monthly)}/mo</p>
                      <p className="text-xs text-white/50">{inr(m.potential_savings_yearly)} / yr</p>
                    </div>
                  </div>
                </GlassCard>
              </li>
            ))}
          </ul>
        ) : (
          <GlassCard surface="panel" padding="md" className="border-white/10">
            <p className="text-sm text-white/60">No migrations detected yet. When usage shifts within a category, they will appear here.</p>
          </GlassCard>
        )}
      </section>

      {/* Insights */}
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-heading text-xl font-semibold text-white">Recent insights</h2>
          <span className="text-xs font-semibold text-white/45">Unread first</span>
        </div>
        {insights?.length ? (
          <ul className="space-y-3">
            {insights.slice(0, 8).map((ins) => {
              const unread = !ins.read_at;
              return (
                <li key={ins.id}>
                  <GlassCard
                    surface="panel"
                    padding="md"
                    className={unread ? "border-violet-400/30 ring-1 ring-violet-500/20" : "border-white/10"}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                      <div className="flex shrink-0 items-start gap-3">
                        <div className="mt-0.5 grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-white/[0.05]">
                          <InsightTypeIcon type={ins.insight_type} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-white/40">
                            {ins.insight_type?.replace(/_/g, " ")}
                          </p>
                          <h3 className="font-semibold text-white">{ins.title}</h3>
                          <p className="mt-2 whitespace-pre-wrap text-sm text-white/65">{ins.body}</p>
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
                        {ins.subscription_id ? (
                          <button
                            type="button"
                            onClick={() => setDetailRow(insightToDetailRow(ins))}
                            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-cyan-400/35 bg-cyan-500/15 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-500/25"
                          >
                            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                            Open detail
                          </button>
                        ) : null}
                        {unread ? (
                          <button
                            type="button"
                            onClick={() =>
                              markInsightReadById(ins.id).catch(() => showToast("Could not mark read", "error"))
                            }
                            className="text-xs font-semibold text-violet-300 hover:text-violet-200 sm:text-right"
                          >
                            Mark read
                          </button>
                        ) : (
                          <span className="text-[11px] text-white/35 sm:text-right">Read</span>
                        )}
                      </div>
                    </div>
                  </GlassCard>
                </li>
              );
            })}
          </ul>
        ) : (
          <GlassCard surface="panel" padding="md" className="border-white/10">
            <p className="text-sm text-white/60">No insights in the feed yet. Run persist on migrations or open the hub below to sync verdicts.</p>
          </GlassCard>
        )}
      </section>

      {/* Quick strip */}
      <div className="flex flex-wrap gap-2 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <span className="text-xs font-semibold uppercase tracking-wide text-white/40">Quick actions</span>
        <div className="flex w-full flex-wrap gap-2">
          {typeof onOpenReminders === "function" ? (
            <button
              type="button"
              onClick={onOpenReminders}
              className="inline-flex items-center gap-2 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-sm font-semibold text-amber-100 hover:bg-amber-500/20"
            >
              <Bell className="h-4 w-4" aria-hidden />
              Smart reminders
            </button>
          ) : null}
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-3 py-2 text-sm text-white/85 hover:bg-white/[0.06]"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh analysis
          </button>
          <button
            type="button"
            onClick={handleScheduleReminders}
            disabled={scheduling}
            className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-3 py-2 text-sm text-white/85 hover:bg-white/[0.06]"
          >
            <Bell className="h-4 w-4" />
            Schedule reminders
          </button>
          <span className="flex items-center gap-1 text-sm text-white/45">
            <ArrowRight className="h-4 w-4" aria-hidden />
            Scroll down for devices & subscription list
          </span>
        </div>
      </div>

      <SubscriptionDetailModal
        open={Boolean(detailRow)}
        row={detailRow}
        userId={userId}
        onClose={() => setDetailRow(null)}
        onRefresh={refreshAll}
      />
    </div>
  );
}

function StatTile({ label, value, hint, ring, icon }) {
  return (
    <div
      className={`rounded-2xl border p-4 ring-1 ${accentRing[ring] || accentRing.cyan}`}
    >
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-[11px] font-semibold uppercase tracking-wide text-white/50">{label}</p>
      </div>
      <p className="mt-2 font-heading text-2xl font-semibold text-white">{value}</p>
      {hint ? <p className="mt-1 text-xs text-white/50">{hint}</p> : null}
    </div>
  );
}
