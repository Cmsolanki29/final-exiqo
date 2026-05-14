import React, { useMemo, useState } from "react";
import { Bell, Brain, Settings } from "lucide-react";
import { GlassCard } from "../components/intro/GlassCard";
import AddAppButton from "../components/Subscriptions/AddAppButton";
import { appById } from "../constants/subscriptionApps";
import { clearSubscriptionFlow, getSubscriptionFlowState } from "../utils/subscriptionFlowStorage";
import { useToast } from "../components/common/Toast";

/**
 * Intelligence hub — two engines + connected apps (after connect flow).
 * @param {object} props
 * @param {number} props.ownerId
 * @param {() => void} props.onOpenAI
 * @param {() => void} props.onOpenReminders
 * @param {() => void} props.onDisconnected — cleared linked apps (back to connect screen)
 */
export default function SubscriptionHub({ ownerId, onOpenAI, onOpenReminders, onDisconnected }) {
  const { showToast } = useToast();
  const [tick, setTick] = useState(0);
  const state = useMemo(() => {
    void tick;
    return getSubscriptionFlowState(ownerId);
  }, [ownerId, tick]);

  const connected = state.apps || [];
  const connectedMeta = connected.map((id) => appById(id)).filter(Boolean);

  const bump = () => setTick((t) => t + 1);

  const handleManage = () => {
    showToast("All monitoring permissions are active for this workspace.", "info");
  };

  const handleDisconnect = () => {
    clearSubscriptionFlow(ownerId);
    showToast("Disconnected subscription apps. You can reconnect anytime.", "info");
    onDisconnected();
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8 pb-16">
      <header className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-violet-300/90">Subscriptions</p>
        <h1 className="font-heading text-3xl font-bold text-white sm:text-4xl">Subscription intelligence hub</h1>
        <p className="max-w-2xl text-sm text-exiqo-glow/70 sm:text-base">
          Device usage plus bank debits → verdicts, substitution insights, and a renewal engine with accountability. Pick an
          engine below — they stay separate by design.
        </p>
      </header>

      <GlassCard padding="md" surface="panel" className="border-white/10">
        <div className="flex flex-col gap-4 border-b border-white/10 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-heading text-lg font-semibold text-white">Connected applications</h2>
            <p className="text-xs text-exiqo-glow/60">
              {connected.length} app{connected.length === 1 ? "" : "s"} linked for intelligent tracking (demo: stored on
              this device).
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <AddAppButton ownerId={ownerId} connectedIds={connected} onAppsUpdated={bump} />
            <button
              type="button"
              onClick={handleManage}
              className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.06] px-4 py-2 text-sm font-medium text-exiqo-glow/90 transition hover:bg-white/10"
            >
              <Settings className="h-4 w-4" aria-hidden />
              Manage permissions
            </button>
            <button
              type="button"
              onClick={handleDisconnect}
              className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-sm font-medium text-rose-200 transition hover:bg-rose-500/20"
            >
              Disconnect all
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-4 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6">
          {connectedMeta.map((app) => (
            <div
              key={app.id}
              className="flex flex-col items-center rounded-xl border border-violet-500/20 bg-violet-500/5 px-2 py-3 text-center"
            >
              <span className="text-2xl" aria-hidden>
                {app.emoji}
              </span>
              <p className="mt-1 line-clamp-2 text-[11px] font-semibold text-white">{app.label}</p>
              <span className="mt-1 flex items-center gap-1 text-[10px] font-medium text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Connected
              </span>
            </div>
          ))}
        </div>

        {connected.length === 0 ? (
          <p className="pt-4 text-sm text-amber-200/90">
            No apps in local link state — use <strong>Add apps</strong> or disconnect cleared your session.
          </p>
        ) : null}
      </GlassCard>

      <div className="grid gap-6 md:grid-cols-2">
        <GlassCard
          padding="md"
          surface="panel"
          className="group cursor-pointer border-violet-500/25 transition hover:border-violet-400/40 hover:shadow-lg hover:shadow-violet-900/20"
          onClick={onOpenAI}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onOpenAI();
            }
          }}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600">
            <Brain className="h-6 w-6 text-white" aria-hidden />
          </div>
          <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.2em] text-violet-300/90">Feature A</p>
          <h3 className="mt-1 font-heading text-xl font-bold text-white">AI analysis engine</h3>
          <p className="mt-2 text-sm text-exiqo-glow/70">
            Usage intelligence, value leakage, substitution detection, verdict buckets, and savings rollups — refreshed from
            live data.
          </p>
          <ul className="mt-4 space-y-1.5 text-xs text-exiqo-glow/80">
            <li className="flex gap-2">
              <span className="text-violet-400">●</span> Behavioural verdicts (thriving / declining / dormant)
            </li>
            <li className="flex gap-2">
              <span className="text-violet-400">●</span> Category migrations & insights feed
            </li>
            <li className="flex gap-2">
              <span className="text-violet-400">●</span> Savings dashboard & substitution signals
            </li>
          </ul>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-semibold text-violet-200 group-hover:text-white">Open AI analysis →</span>
            <div onClick={(e) => e.stopPropagation()} className="flex shrink-0">
              <AddAppButton ownerId={ownerId} connectedIds={connected} variant="small" onAppsUpdated={bump} />
            </div>
          </div>
        </GlassCard>

        <GlassCard
          padding="md"
          surface="panel"
          className="group cursor-pointer border-amber-500/25 transition hover:border-amber-400/40 hover:shadow-lg hover:shadow-amber-900/20"
          onClick={onOpenReminders}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onOpenReminders();
            }
          }}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-rose-600">
            <Bell className="h-6 w-6 text-white" aria-hidden />
          </div>
          <p className="mt-3 text-[10px] font-bold uppercase tracking-[0.2em] text-amber-300/90">Feature B</p>
          <h3 className="mt-1 font-heading text-xl font-bold text-white">Smart reminder engine</h3>
          <p className="mt-2 text-sm text-exiqo-glow/70">
            Billing reminders, T−10 / T−3 / T−1 alerts, escalation, snooze with mandatory reasons, and cancellation
            assistance.
          </p>
          <ul className="mt-4 space-y-1.5 text-xs text-exiqo-glow/80">
            <li className="flex gap-2">
              <span className="text-amber-400">●</span> Renewal queue & pending actions
            </li>
            <li className="flex gap-2">
              <span className="text-amber-400">●</span> Accountability on “remind me later”
            </li>
            <li className="flex gap-2">
              <span className="text-amber-400">●</span> Escalation when renewals are ignored
            </li>
          </ul>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-semibold text-amber-200 group-hover:text-white">Open smart reminders →</span>
            <div onClick={(e) => e.stopPropagation()} className="flex shrink-0">
              <AddAppButton ownerId={ownerId} connectedIds={connected} variant="small" onAppsUpdated={bump} />
            </div>
          </div>
        </GlassCard>
      </div>

      <p className="text-center text-xs text-exiqo-glow/50">
        Demo mode: linked apps are stored in your browser for this workspace user ({ownerId}). Production would sync to
        your account on the server.
      </p>
    </div>
  );
}
