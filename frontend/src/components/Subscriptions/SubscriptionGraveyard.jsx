import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bell,
  ChevronDown,
  ChevronUp,
  Cpu,
  Info,
  RefreshCw,
  Shield,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getSubscriptionIntelligenceHub,
  getSubscriptionRecommendation,
  getSubscriptionRemindersPending,
  patchSubscriptionInsightRead,
  postSubscriptionDeviceLink,
  postSubscriptionReminderAction,
  postSubscriptionResetDemo,
  postSubscriptionSimulateNextDay,
} from "../../services/api";
import { useToast } from "../common/Toast";
import { ErrorCard } from "../common/ErrorCard";
import { PageHeader } from "../Dashboard/shared/PageHeader";
import { inr } from "../../lib/format";

const DEMO_MODE =
  process.env.REACT_APP_DEMO_MODE === "true" || process.env.REACT_APP_DEMO_MODE === "1";

const EMPTY_LIST = [];

// SIMULATED: production version uses Android UsageStatsManager via companion mobile SDK
const DEMO_APPS = [
  { id: "com.netflix.mediaclient", label: "Netflix" },
  { id: "com.spotify.music", label: "Spotify" },
  { id: "com.google.android.youtube", label: "YouTube Premium" },
  { id: "com.linkedin.android", label: "LinkedIn" },
  { id: "in.startv.hotstar", label: "Hotstar" },
  { id: "in.amazon.mShop.android.shopping", label: "Prime / Amazon" },
  { id: "com.openai.chatgpt", label: "ChatGPT" },
  { id: "com.notion.android", label: "Notion" },
  { id: "com.canva.editor", label: "Canva Pro" },
  { id: "com.adobe.reader", label: "Adobe Acrobat" },
  { id: "com.gaana", label: "Gaana" },
  { id: "com.apple.android.music", label: "Apple Music" },
];

const VERDICT_STYLES = {
  thriving: { bg: "bg-emerald-500/15", ring: "ring-emerald-500/35", text: "text-emerald-200", dot: "bg-emerald-400" },
  declining: { bg: "bg-amber-500/15", ring: "ring-amber-500/35", text: "text-amber-100", dot: "bg-amber-400" },
  dormant: { bg: "bg-orange-500/15", ring: "ring-orange-500/35", text: "text-orange-100", dot: "bg-orange-400" },
  dead: { bg: "bg-rose-500/15", ring: "ring-rose-500/35", text: "text-rose-100", dot: "bg-rose-400" },
  upgrade: { bg: "bg-purple-500/15", ring: "ring-purple-500/40", text: "text-purple-100", dot: "bg-purple-400" },
};

function VerdictBadge({ verdict }) {
  const v = (verdict || "").toLowerCase();
  const s = VERDICT_STYLES[v] || VERDICT_STYLES.declining;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ring-1 ${s.bg} ${s.ring} ${s.text}`}
    >
      <span className={`relative flex h-2 w-2`}>
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${s.dot}`} />
        <span className={`relative h-2 w-2 rounded-full ${s.dot}`} />
      </span>
      {v || "—"}
    </span>
  );
}

function WasteLedgerHero({ amount, loading }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (loading) return;
    const target = Math.round(Number(amount) || 0);
    setN(0);
    const start = performance.now();
    const dur = 900;
    let id;
    const tick = (now) => {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - (1 - p) ** 3;
      setN(Math.round(target * eased));
      if (p < 1) id = window.requestAnimationFrame(tick);
    };
    id = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(id);
  }, [amount, loading]);
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-violet-600/25 via-[#0a0a22]/80 to-blue-900/20 p-6 shadow-[0_0_50px_-20px_rgba(124,58,237,0.45)] backdrop-blur-xl sm:p-8"
    >
      <div className="pointer-events-none absolute inset-0 opacity-30 bg-[radial-gradient(circle_at_20%_20%,rgba(124,58,237,0.4),transparent_45%)]" />
      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-violet-200/80">Waste ledger</p>
      <p className="mt-2 text-3xl font-bold tabular-nums tracking-tight text-white sm:text-4xl">
        You&apos;ve saved {inr(n)} this year with SmartSpend
      </p>
      <p className="mt-2 max-w-xl text-sm text-exiqo-glow/65">
        Aggregated from verdict-classified monthly waste × 12 — same numbers your bank feed can&apos;t see without device context.
      </p>
    </motion.div>
  );
}

export default function SubscriptionGraveyard({ userId }) {
  const { showToast } = useToast();
  const [hub, setHub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectStep, setConnectStep] = useState(0);
  const [perm, setPerm] = useState({ usage_access: true, notifications: true, session_duration: true });
  const [selectedApps, setSelectedApps] = useState(() => new Set(DEMO_APPS.map((a) => a.id)));
  const [expanded, setExpanded] = useState(null);
  const [recoById, setRecoById] = useState({});
  const [recoLoading, setRecoLoading] = useState(false);
  const [banner, setBanner] = useState(null);
  const [snoozeModal, setSnoozeModal] = useState({ open: false, id: null });
  const [snoozeReason, setSnoozeReason] = useState("");

  const loadHub = useCallback(async (opts = {}) => {
    const silent = !!opts.silent;
    if (!silent) {
      setLoading(true);
      setError("");
    }
    try {
      const data = await getSubscriptionIntelligenceHub(userId);
      setHub(data);
    } catch (e) {
      if (!silent) {
        setError(e.message || "Failed to load subscription intelligence");
        setHub(null);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [userId]);

  const pollReminders = useCallback(async () => {
    try {
      const r = await getSubscriptionRemindersPending(userId);
      const first = (r.reminders || [])[0];
      setBanner(first || null);
    } catch {
      /* ignore */
    }
  }, [userId]);

  useEffect(() => {
    loadHub();
  }, [loadHub]);

  useEffect(() => {
    pollReminders();
    const id = window.setInterval(pollReminders, 60000);
    return () => clearInterval(id);
  }, [pollReminders]);

  const subs = useMemo(() => {
    const list = hub?.subscriptions;
    if (!Array.isArray(list) || list.length === 0) return EMPTY_LIST;
    return list;
  }, [hub]);

  const substitutions = useMemo(() => {
    const list = hub?.substitutions;
    if (!Array.isArray(list) || list.length === 0) return EMPTY_LIST;
    return list;
  }, [hub]);

  const connectedApps = useMemo(() => {
    const list = hub?.connected_apps;
    if (!Array.isArray(list) || list.length === 0) return EMPTY_LIST;
    return list;
  }, [hub]);

  const intelligenceInsights = useMemo(() => {
    const list = hub?.intelligence_insights;
    if (!Array.isArray(list) || list.length === 0) return EMPTY_LIST;
    return list;
  }, [hub]);

  /** Collapse chips that share the same display label (legacy rows / similar package tails). */
  const connectedAppsDisplay = useMemo(() => {
    const groups = new Map();
    for (const a of connectedApps) {
      const lab = (a.display_label || a.app_package || "App").trim() || "App";
      const key = lab.toLowerCase();
      if (!groups.has(key)) {
        groups.set(key, {
          app_package: a.app_package,
          display_label: lab,
          pkgs: [a.app_package].filter(Boolean),
        });
      } else {
        const g = groups.get(key);
        if (a.app_package && !g.pkgs.includes(a.app_package)) g.pkgs.push(a.app_package);
      }
    }
    return Array.from(groups.values()).map((g) => ({
      key: g.pkgs.join("|"),
      display_label: g.pkgs.length > 1 ? `${g.display_label} (${g.pkgs.length})` : g.display_label,
      title: g.pkgs.length > 1 ? g.pkgs.join("\n") : g.pkgs[0] || "",
    }));
  }, [connectedApps]);

  const deviceLinked = !!hub?.device_linked;
  const discoveryMsg = hub?.discovery?.message || "";

  const toggleApp = (id) => {
    setSelectedApps((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  const runDeviceConnect = async () => {
    setConnecting(true);
    setConnectStep(0);
    const steps = ["Scanning installed apps…", "Reading 30-day usage history…", "Building behavioral baseline…", "Done."];
    const iv = window.setInterval(() => {
      setConnectStep((s) => Math.min(s + 1, steps.length - 1));
    }, 650);
    const t0 = Date.now();
    try {
      await postSubscriptionDeviceLink(userId, {
        device_type: "simulated",
        permissions: perm,
        apps_linked: Array.from(selectedApps),
      });
      const pad = Math.max(0, 2500 - (Date.now() - t0));
      if (pad) await new Promise((r) => setTimeout(r, pad));
      showToast("Device intelligence connected — Digital Wellbeing-style signals are now live.");
      setModal(false);
      await loadHub();
      await pollReminders();
    } catch (e) {
      showToast(e.message || "Connect failed");
    } finally {
      clearInterval(iv);
      setConnecting(false);
      setConnectStep(0);
    }
  };

  const loadReco = async (subId) => {
    if (!subId || recoById[subId]) return;
    setRecoLoading(true);
    try {
      const r = await getSubscriptionRecommendation(userId, subId);
      setRecoById((m) => ({ ...m, [subId]: r.paragraph || "" }));
    } catch {
      setRecoById((m) => ({ ...m, [subId]: "Recommendation unavailable right now." }));
    } finally {
      setRecoLoading(false);
    }
  };

  const onExpand = (sid) => {
    setExpanded((e) => (e === sid ? null : sid));
    if (sid && expanded !== sid) loadReco(sid);
  };

  const reminderAction = async (id, action, accountabilityReason) => {
    try {
      let payload;
      if (action === "remind_later") {
        const r = (accountabilityReason || "").trim();
        payload = r.length > 0 ? { action, accountability_reason: r } : { action: "remind_later" };
      } else {
        payload = { action };
      }
      await postSubscriptionReminderAction(userId, id, payload);
      showToast("Updated");
      setBanner(null);
      await pollReminders();
      await loadHub({ silent: true });
    } catch (e) {
      showToast(e.message || "Action failed");
    }
  };

  const submitSnooze = async () => {
    const text = snoozeReason.trim();
    if (text.length < 10) {
      showToast("Escalation snooze needs at least 10 characters explaining why you are keeping this subscription.");
      return;
    }
    if (!snoozeModal.id) return;
    await reminderAction(snoozeModal.id, "remind_later", text);
    setSnoozeModal({ open: false, id: null });
    setSnoozeReason("");
  };

  const dismissInsight = async (insightId) => {
    try {
      await patchSubscriptionInsightRead(userId, insightId);
      await loadHub({ silent: true });
    } catch (e) {
      showToast(e.message || "Could not update insight");
    }
  };

  const simulateDay = async () => {
    try {
      await postSubscriptionSimulateNextDay(userId);
      await pollReminders();
      showToast("Demo clock advanced 24h");
    } catch (e) {
      showToast(e.message || "Simulate failed");
    }
  };

  const resetDemo = async () => {
    try {
      await postSubscriptionResetDemo(userId);
      showToast("Demo reset — link device again to replay.");
      await loadHub();
      await pollReminders();
    } catch (e) {
      showToast(e.message || "Reset failed");
    }
  };

  const chartData = useMemo(() => {
    const s = subs.find((x) => x.subscription_id === expanded);
    const series = s?.usage_series || [];
    return series.map((p) => ({ d: p.d?.slice(5) || "", m: p.m }));
  }, [expanded, subs]);

  if (loading && !hub) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 pb-8">
        <div className="h-40 animate-pulse rounded-3xl bg-white/[0.04]" />
        <div className="h-32 animate-pulse rounded-2xl bg-white/[0.04]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-5xl">
        <ErrorCard message={error} onRetry={loadHub} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-10">
      <PageHeader
        eyebrow="SUBSCRIPTIONS"
        title="Subscription Intelligence"
        subtitle="Device usage + bank debits → verdicts, substitution insights, and a renewal engine: tier-1 snooze is one tap; after escalation, “Remind later” asks for a short reason (same as Digital Wellbeing / Screen Time, tuned for spend)."
        accentHex="#a855f7"
        rightSlot={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => loadHub()}
              className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.06] px-3 py-2 text-xs font-semibold text-white hover:bg-white/10"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </button>
            {DEMO_MODE ? (
              <>
                <button
                  type="button"
                  onClick={simulateDay}
                  className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs font-semibold text-cyan-100"
                >
                  ⏭ Simulate next day
                </button>
                <button
                  type="button"
                  onClick={resetDemo}
                  className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-100"
                >
                  🔄 Reset demo
                </button>
              </>
            ) : null}
          </div>
        }
      />

      <WasteLedgerHero amount={hub?.waste_ledger_yearly_saved_inr} loading={loading} />

      {discoveryMsg ? (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-exiqo-glow/80 backdrop-blur-md"
        >
          <span className="font-semibold text-white">Discovery.</span> {discoveryMsg}
        </motion.p>
      ) : null}

      {hub?.reminder_escalation_active ? (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-rose-500/35 bg-rose-500/10 px-4 py-3 text-sm text-rose-50 backdrop-blur-md"
        >
          <span className="font-semibold">Escalated accountability.</span> Renewal reminders now follow the denser T-15 → T-1 cadence after you kept subscriptions through a full billing cycle without cancelling.
        </motion.div>
      ) : null}

      {banner ? (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-3 rounded-2xl border border-amber-500/35 bg-amber-500/10 p-4 backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex items-start gap-3">
            <Bell className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
            <div>
              <p className="text-sm font-semibold text-white">Renewal reminder — {banner.merchant}</p>
              <p className="text-xs text-exiqo-glow/65">
                {banner.reminder_type} · {inr(banner.monthly_cost)}/mo
              </p>
              <p className="mt-2 text-[11px] text-amber-200/80">
                {Number(banner.reminder_escalation_tier ?? 1) >= 2
                  ? "“Remind later” opens an accountability prompt — required on escalation tier 2+."
                  : "Tier 1 cycle: “Remind later” snoozes ~24h without a written reason."}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => reminderAction(banner.id, "cancel_now")}
              className="rounded-xl bg-rose-600 px-3 py-2 text-xs font-bold text-white"
            >
              Cancel now
            </button>
            <button
              type="button"
              onClick={() => {
                const tier = Number(banner.reminder_escalation_tier ?? 1);
                if (tier >= 2) {
                  setSnoozeReason("");
                  setSnoozeModal({ open: true, id: banner.id });
                } else {
                  void reminderAction(banner.id, "remind_later", "");
                }
              }}
              className="rounded-xl border border-white/20 px-3 py-2 text-xs font-semibold text-white"
            >
              Remind later
            </button>
            <button
              type="button"
              onClick={() => reminderAction(banner.id, "keep")}
              className="rounded-xl border border-emerald-500/30 bg-emerald-500/15 px-3 py-2 text-xs font-semibold text-emerald-100"
            >
              Keep subscription
            </button>
          </div>
        </motion.div>
      ) : null}

      {!deviceLinked ? (
        <div className="flex flex-col gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-xs text-exiqo-glow/75 sm:flex-row sm:items-center sm:justify-between">
          <p>
            No device link on this account yet. Use <span className="font-semibold text-white">Connect</span> in the intelligence hub first — this list stays in sync with the same backend seed.
          </p>
          {DEMO_MODE ? (
            <button
              type="button"
              onClick={() => setModal(true)}
              className="shrink-0 rounded-lg border border-violet-500/35 bg-violet-500/15 px-3 py-1.5 text-[11px] font-semibold text-violet-100 hover:bg-violet-500/25"
            >
              Open simulator
            </button>
          ) : null}
        </div>
      ) : (
        <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
          <span className="font-semibold">Device intelligence active.</span> Aggregated signals only — see privacy callout in the modal anytime.
        </div>
      )}

      {deviceLinked ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-bold uppercase tracking-wider text-exiqo-glow/50">Connected applications</h3>
            <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-violet-200">
              Live sync
            </span>
          </div>
          <p className="mt-1 text-xs text-exiqo-glow/55">
            Normalized from your last device link. Re-open Connect to add or remove packages — revoked apps stay in the database for audit, but drop off this list.
          </p>
          {connectedAppsDisplay.length > 0 ? (
            <ul className="mt-4 flex flex-wrap gap-2">
              {connectedAppsDisplay.map((a) => (
                <li
                  key={a.key}
                  title={a.title || undefined}
                  className="rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1 text-xs font-medium text-violet-100"
                >
                  {a.display_label}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 rounded-xl border border-white/10 bg-black/20 px-3 py-3 text-xs text-exiqo-glow/65">
              No packages synced yet. Press <span className="font-semibold text-white">Refresh</span> after linking, or reconnect from the device modal.
            </p>
          )}
        </div>
      ) : null}

      {deviceLinked ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-bold uppercase tracking-wider text-exiqo-glow/50">AI intelligence feed</h3>
            <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-cyan-100">
              Deduped
            </span>
          </div>
          <p className="text-xs text-exiqo-glow/55">
            Behavioral alerts (not billing pings). Persisted in your workspace — mark read when you have acted on them.
          </p>
          {intelligenceInsights.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {intelligenceInsights.map((ins) => (
                <div
                  key={ins.id}
                  className={`rounded-2xl border p-4 backdrop-blur-xl ${
                    ins.read_at ? "border-white/5 bg-white/[0.02] opacity-70" : "border-cyan-500/25 bg-cyan-500/5"
                  }`}
                >
                  <p className="text-xs font-bold uppercase tracking-wide text-cyan-200/90">
                    {(ins.insight_type === "verdict"
                      ? "Verdict"
                      : ins.insight_type === "substitution"
                        ? "Substitution"
                        : ins.insight_type) || "Insight"}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-white">{ins.title}</p>
                  <p className="mt-2 text-xs leading-relaxed text-exiqo-glow/70">{ins.body}</p>
                  {!ins.read_at ? (
                    <button
                      type="button"
                      onClick={() => dismissInsight(ins.id)}
                      className="mt-3 text-[11px] font-semibold text-cyan-200 underline-offset-2 hover:underline"
                    >
                      Mark read
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-4 text-xs text-exiqo-glow/70">
              <p>
                No behavioral feed cards yet. Use <span className="font-semibold text-white">Refresh hub data</span>{" "}
                below — declining, dormant, and dead verdicts sync into this feed; substitution alerts appear when migration
                signals fire.
              </p>
              <button
                type="button"
                className="mt-3 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-[11px] font-semibold text-cyan-100 hover:bg-cyan-500/20"
                onClick={() => loadHub({ silent: true })}
              >
                Refresh hub data
              </button>
            </div>
          )}
        </div>
      ) : null}

      {substitutions.length ? (
        <div>
          <h3 className="mb-3 text-sm font-bold uppercase tracking-wider text-exiqo-glow/50">Cross-platform substitution</h3>
          <div className="grid gap-4 md:grid-cols-2">
            {substitutions.map((ins, i) => (
              <motion.div
                key={`${ins.subscription_id}-${i}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                whileHover={{ y: -2 }}
                className="rounded-2xl border border-cyan-500/25 bg-white/[0.03] p-5 backdrop-blur-xl"
              >
                <div className="flex items-center gap-2 text-cyan-200">
                  <Zap className="h-4 w-4" />
                  <span className="text-xs font-bold uppercase tracking-wide">Paired insight</span>
                </div>
                <p className="mt-2 text-sm font-semibold text-white">{ins.headline}</p>
                <p className="mt-2 text-xs leading-relaxed text-exiqo-glow/70">{ins.body}</p>
              </motion.div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="space-y-3">
        <h3 className="text-sm font-bold uppercase tracking-wider text-exiqo-glow/50">Your subscriptions</h3>
        <AnimatePresence>
          {subs.map((s, i) => (
            <motion.article
              key={s.merchant}
              layout
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.05, 0.35) }}
              className="overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03] shadow-[0_0_32px_-22px_rgba(124,58,237,0.35)] backdrop-blur-xl"
            >
              <button
                type="button"
                onClick={() => s.subscription_id && onExpand(s.subscription_id)}
                className="flex w-full items-start justify-between gap-3 p-5 text-left sm:items-center"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Cpu className="h-4 w-4 shrink-0 text-violet-300" />
                    <span className="font-bold text-white">{s.merchant}</span>
                    {s.current_verdict ? <VerdictBadge verdict={s.current_verdict} /> : null}
                  </div>
                  <p className="mt-1 text-xs text-exiqo-glow/55 tabular-nums">
                    {inr(s.monthly_cost || s.amount)} / mo · {s.linked_app_package ? "Linked app" : "No app link"}
                  </p>
                  {s.verdict_reason ? <p className="mt-2 text-xs text-exiqo-glow/70">{s.verdict_reason}</p> : null}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {s.verdict_confidence != null ? (
                    <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] tabular-nums text-exiqo-glow/60">
                      {s.verdict_confidence}% conf
                    </span>
                  ) : null}
                  {s.subscription_id ? expanded === s.subscription_id ? <ChevronUp className="h-5 w-5 text-exiqo-glow" /> : <ChevronDown className="h-5 w-5 text-exiqo-glow" /> : null}
                </div>
              </button>
              <AnimatePresence>
                {expanded === s.subscription_id && s.subscription_id ? (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="border-t border-white/[0.06] bg-black/20 px-5 pb-5"
                  >
                    <div className="mt-4 h-44 w-full">
                      {chartData.length ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={chartData}>
                            <XAxis dataKey="d" tick={{ fill: "rgba(226,232,240,0.45)", fontSize: 10 }} axisLine={false} tickLine={false} />
                            <YAxis tick={{ fill: "rgba(226,232,240,0.45)", fontSize: 10 }} axisLine={false} tickLine={false} width={32} />
                            <Tooltip
                              contentStyle={{ background: "#0f0f24", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}
                              labelStyle={{ color: "#e2e8f0" }}
                            />
                            <Line type="monotone" dataKey="m" stroke="#7c3aed" strokeWidth={2} dot={false} name="Minutes" />
                          </LineChart>
                        </ResponsiveContainer>
                      ) : (
                        <p className="text-xs text-exiqo-glow/50">No usage series yet — reset demo or link device.</p>
                      )}
                    </div>
                    <div className="mt-4 rounded-xl border border-violet-500/20 bg-violet-500/10 p-4">
                      <div className="flex items-center gap-2 text-violet-200">
                        <Sparkles className="h-4 w-4" />
                        <span className="text-xs font-bold uppercase">Advisor note</span>
                      </div>
                      <p className="mt-2 text-sm leading-relaxed text-exiqo-glow/80">
                        {recoLoading && !recoById[s.subscription_id] ? "Loading…" : recoById[s.subscription_id] || "—"}
                      </p>
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </motion.article>
          ))}
        </AnimatePresence>
      </div>

      {hub?.legacy?.ai_advice ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 text-sm text-exiqo-glow/75">{hub.legacy.ai_advice}</div>
      ) : null}

      <AnimatePresence>
        {modal ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4 backdrop-blur-md"
            onClick={() => !connecting && setModal(false)}
            role="presentation"
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-3xl border border-white/10 bg-[#0b0b22] p-6 shadow-2xl"
            >
              <div className="mb-4 flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-lg font-bold text-white">Connect SmartSpend Device Intelligence</h3>
                  <p className="mt-1 text-xs text-exiqo-glow/65">
                    We infer subscription value from your usage patterns — like Digital Wellbeing, but for your wallet.
                  </p>
                </div>
                <button type="button" className="rounded-lg p-1 text-exiqo-glow/50 hover:text-white" onClick={() => !connecting && setModal(false)} aria-label="Close">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-exiqo-glow/45">Apps to correlate</p>
              <div className="mb-4 grid max-h-48 grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-2">
                {DEMO_APPS.map((a) => (
                  <label key={a.id} className="flex cursor-pointer items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-white">
                    <input type="checkbox" checked={selectedApps.has(a.id)} onChange={() => toggleApp(a.id)} className="rounded border-white/30" />
                    {a.label}
                  </label>
                ))}
              </div>
              <div className="mb-4 space-y-2 rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                {[
                  { k: "usage_access", label: "Usage Access", hint: "see app open/close events" },
                  { k: "notifications", label: "Notification Metadata", hint: "count, not content" },
                  { k: "session_duration", label: "Session Duration", hint: "how long, not what you watched" },
                ].map((p) => (
                  <label key={p.k} className="flex items-start gap-2 text-xs text-exiqo-glow/80">
                    <input
                      type="checkbox"
                      checked={!!perm[p.k]}
                      onChange={(e) => setPerm((x) => ({ ...x, [p.k]: e.target.checked }))}
                      className="mt-0.5 rounded border-white/30"
                    />
                    <span>
                      <span className="font-semibold text-white">{p.label}</span> — {p.hint}{" "}
                      <Info className="inline h-3 w-3 text-exiqo-glow/40" aria-hidden />
                    </span>
                  </label>
                ))}
              </div>
              <p className="mb-4 flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100/90">
                <Shield className="h-4 w-4 shrink-0" />
                Data stays on your device. Only aggregated signals leave.
              </p>
              {connecting ? (
                <div className="space-y-3">
                  <div className="h-2 overflow-hidden rounded-full bg-white/10">
                    <motion.div
                      className="h-full bg-gradient-to-r from-violet-500 to-cyan-400"
                      initial={{ width: "5%" }}
                      animate={{ width: "100%" }}
                      transition={{ duration: 2.4, ease: "easeInOut" }}
                    />
                  </div>
                  <p className="text-center text-xs text-exiqo-glow/70">
                    {["Scanning installed apps…", "Reading 30-day usage history…", "Building behavioral baseline…", "Done."][connectStep]}
                  </p>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={runDeviceConnect}
                  className="w-full rounded-2xl bg-gradient-to-r from-violet-600 to-blue-600 py-3 text-sm font-bold text-white shadow-lg shadow-violet-500/25"
                >
                  Grant Access &amp; Connect
                </button>
              )}
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {snoozeModal.open ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[125] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"
            onClick={() => setSnoozeModal({ open: false, id: null })}
            role="presentation"
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-3xl border border-white/10 bg-[#0b0b22] p-6 shadow-2xl"
            >
              <div className="mb-3 flex items-start justify-between gap-2">
                <h3 className="text-lg font-bold text-white">Escalation accountability</h3>
                <button
                  type="button"
                  className="rounded-lg p-1 text-exiqo-glow/50 hover:text-white"
                  onClick={() => setSnoozeModal({ open: false, id: null })}
                  aria-label="Close"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <p className="text-sm text-exiqo-glow/75">
                This subscription is on renewal escalation tier 2+. Why are you keeping it despite low usage? We log
                this with your snooze so SmartSpend can tune future nudges.
              </p>
              <textarea
                value={snoozeReason}
                onChange={(e) => setSnoozeReason(e.target.value)}
                rows={4}
                className="mt-4 w-full resize-none rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-exiqo-glow/40 focus:border-violet-500/50 focus:outline-none"
                placeholder="Be specific (min 10 characters)…"
              />
              <div className="mt-4 flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setSnoozeModal({ open: false, id: null })}
                  className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold text-exiqo-glow"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={submitSnooze}
                  className="rounded-xl bg-gradient-to-r from-violet-600 to-blue-600 px-4 py-2 text-xs font-bold text-white"
                >
                  Snooze 24h
                </button>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
