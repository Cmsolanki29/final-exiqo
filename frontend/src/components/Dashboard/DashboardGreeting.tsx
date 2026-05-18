/**
 * DashboardGreeting — Personal header with visible name + contextual welcome lines.
 */
import React, { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Sparkles } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { apiUtils } from "../../services/api";
import { PageHeader } from "./shared/PageHeader";

const GREETING_ACCENT = "#A78BFA";

const BRAND_EASE = [0.22, 1, 0.36, 1] as const;
const SESSION_WELCOME_KEY = "ss_dashboard_welcome_seen";

function getGreeting(d: Date): string {
  const hour = d.getHours();
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  if (hour >= 17 && hour < 21) return "Good evening";
  return "Working late";
}

function getFirstName(name?: string | null, email?: string | null): string {
  const trimmed = (name || "").trim();
  if (trimmed) return trimmed.split(/\s+/)[0];
  const local = (email || "").trim().split("@")[0];
  if (local) return local.charAt(0).toUpperCase() + local.slice(1);
  return "there";
}

function formatLongDate(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function formatRelative(date: Date | null): string {
  if (!date) return "never";
  const sec = Math.floor((Date.now() - date.getTime()) / 1000);
  if (sec < 30) return "just now";
  const mins = Math.floor(sec / 60);
  if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

type WelcomeCopy = {
  headline: string;
  subline: string;
  isFirstVisit: boolean;
};

function buildWelcomeCopy(
  firstName: string,
  isFirstVisit: boolean,
  monthSpend?: number,
  monthIncome?: number,
  fraudPending?: number,
  savedYtd?: number
): WelcomeCopy {
  if (fraudPending && fraudPending > 0) {
    return {
      headline: `${fraudPending} alert${fraudPending > 1 ? "s" : ""} need your attention today.`,
      subline: "FraudShield has flagged activity worth reviewing before your next transfer.",
      isFirstVisit,
    };
  }

  const income = monthIncome || 0;
  const spend = monthSpend || 0;
  const net = income - spend;

  if (isFirstVisit) {
    return {
      headline: `Welcome to your financial command center, ${firstName}.`,
      subline:
        income > 0
          ? `We've loaded your workspace — net flow this month is ${apiUtils.formatINR(net)}.`
          : "Link a bank or upload a statement to unlock live AI insights and alerts.",
      isFirstVisit: true,
    };
  }

  if (income > 0 && spend > income) {
    return {
      headline: "Spending is running ahead of income this month.",
      subline: "A quick review of subscriptions and large debits can help you rebalance.",
      isFirstVisit,
    };
  }

  if (savedYtd && savedYtd > 0) {
    return {
      headline: `You've saved ${apiUtils.formatINR(savedYtd)} so far this year.`,
      subline: "SmartSpend is tracking wins from cancellations, prevention, and smarter spend.",
      isFirstVisit,
    };
  }

  if (income > 0) {
    return {
      headline: "Your money picture looks steady today.",
      subline: `Net flow this month: ${apiUtils.formatINR(net)} — insights and alerts are updated below.`,
      isFirstVisit,
    };
  }

  return {
    headline: "Your dashboard is ready whenever you are.",
    subline: "Connect an account or upload a statement to activate AI-powered insights.",
    isFirstVisit,
  };
}

type StatusConfig = {
  emoji: string;
  label: string;
  bg: string;
  text: string;
  border: string;
};

function getStatusConfig(
  monthSpend?: number,
  monthIncome?: number,
  fraudPending?: number,
  savedYtd?: number
): StatusConfig {
  if (fraudPending && fraudPending > 0) {
    return {
      emoji: "🛡️",
      label: `FraudShield is watching ${fraudPending} signal${fraudPending > 1 ? "s" : ""}`,
      bg: "bg-rose-500/10",
      text: "text-rose-300",
      border: "border-rose-500/20",
    };
  }
  const income = monthIncome || 0;
  const spend = monthSpend || 0;
  if (income > 0 && spend > income) {
    return {
      emoji: "⚠️",
      label: "Watch your spending this week",
      bg: "bg-amber-500/10",
      text: "text-amber-300",
      border: "border-amber-500/20",
    };
  }
  if (savedYtd && savedYtd > 0) {
    return {
      emoji: "✨",
      label: "You're saving more than usual",
      bg: "bg-emerald-500/10",
      text: "text-emerald-300",
      border: "border-emerald-500/20",
    };
  }
  return {
    emoji: "🟢",
    label: "Your money is on track",
    bg: "bg-emerald-500/10",
    text: "text-emerald-300",
    border: "border-emerald-500/20",
  };
}

function navigateTab(tab: string) {
  window.dispatchEvent(new CustomEvent("smartspend:navigate", { detail: { tab } }));
}

export type DashboardGreetingProps = {
  lastSync: Date | null;
  lastLogin?: Date | null;
  loading?: boolean;
  monthSpend?: number;
  monthIncome?: number;
  fraudPending?: number;
  savedYtd?: number;
};

export default function DashboardGreeting({
  lastSync,
  lastLogin = null,
  loading = false,
  monthSpend,
  monthIncome,
  fraudPending,
  savedYtd,
}: DashboardGreetingProps) {
  const reduce = useReducedMotion();
  const { user, loading: authLoading } = useAuth();
  const [now, setNow] = useState(() => new Date());
  const [isFirstVisit, setIsFirstVisit] = useState(false);

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!user?.id) return;
    try {
      const key = `${SESSION_WELCOME_KEY}_${user.id}`;
      const seen = sessionStorage.getItem(key) === "1";
      setIsFirstVisit(!seen);
      if (!seen) sessionStorage.setItem(key, "1");
    } catch {
      setIsFirstVisit(true);
    }
  }, [user?.id]);

  const isLoading = loading || authLoading || !user;

  const firstName = getFirstName(user?.name, user?.email);
  const greeting = getGreeting(now);
  const status = getStatusConfig(monthSpend, monthIncome, fraudPending, savedYtd);
  const syncStamp = lastSync ?? lastLogin ?? null;
  const syncLabel = syncStamp ? `Last synced ${formatRelative(syncStamp)}` : "No bank linked yet";

  const welcome = useMemo(
    () => buildWelcomeCopy(firstName, isFirstVisit, monthSpend, monthIncome, fraudPending, savedYtd),
    [firstName, isFirstVisit, monthSpend, monthIncome, fraudPending, savedYtd]
  );

  const quickActions = useMemo(() => {
    const actions: { label: string; tab: string }[] = [];
    if (fraudPending && fraudPending > 0) {
      actions.push({ label: "Review alerts", tab: "fraud" });
    } else {
      actions.push({ label: "View insights", tab: "insights" });
    }
    actions.push({ label: "Transactions", tab: "transactions" });
    if (!syncStamp) {
      actions.push({ label: "Connect account", tab: "settings" });
    }
    return actions.slice(0, 3);
  }, [fraudPending, syncStamp]);

  if (isLoading) {
    return (
      <header aria-busy="true" className="mb-8 space-y-3">
        <motion.div className="h-1 w-12 rounded-full bg-white/[0.06] animate-pulse" />
        <motion.div className="h-4 w-40 max-w-full rounded-md bg-white/[0.06] animate-pulse" />
        <motion.div className="h-10 w-96 max-w-full rounded-md bg-white/[0.06] animate-pulse" />
        <motion.div className="h-4 w-full max-w-xl rounded-md bg-white/[0.04] animate-pulse" />
      </header>
    );
  }

  return (
    <motion.header
      initial={reduce ? { opacity: 1 } : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: BRAND_EASE }}
      className="mb-8"
    >
      <PageHeader
        title={`${greeting}, ${firstName}`}
        lead={welcome.headline}
        subtitle={welcome.subline}
        accentHex={GREETING_ACCENT}
        titleScale="hero"
        rightSlot={
          <span
            className={[
              "inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold",
              status.bg,
              status.text,
              status.border,
            ].join(" ")}
          >
            <span aria-hidden>{status.emoji}</span>
            {status.label}
          </span>
        }
      />

      <motion.div
        initial={reduce ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12, duration: 0.35, ease: BRAND_EASE }}
      >
        {isFirstVisit ? (
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.35, ease: BRAND_EASE }}
            className="mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold"
            style={{
              background: "rgba(124, 58, 237, 0.15)",
              border: "1px solid rgba(167, 139, 250, 0.25)",
              color: "rgb(196, 181, 253)",
            }}
          >
            <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
            First visit this session — here's your personalized overview
          </motion.div>
        ) : null}

        <motion.div className="flex flex-wrap gap-2">
          {quickActions.map((action) => (
            <button
              key={action.tab}
              type="button"
              onClick={() => navigateTab(action.tab)}
              className="group inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
              style={{
                background: "rgba(255,255,255,0.08)",
                border: "1px solid rgba(255,255,255,0.14)",
              }}
            >
              {action.label}
              <ArrowRight
                className="h-3 w-3 transition group-hover:translate-x-0.5"
                strokeWidth={1.75}
                aria-hidden
              />
            </button>
          ))}
        </motion.div>
      </motion.div>

      <motion.p
        initial={reduce ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.32, duration: 0.35, ease: BRAND_EASE }}
        className="mt-4 flex flex-wrap items-center gap-2 text-xs font-normal"
        style={{ color: "rgba(255,255,255,0.42)" }}
      >
        <span>{formatLongDate(now)}</span>
        <span aria-hidden className="h-1 w-1 rounded-full bg-white/25" />
        <span className="flex items-center gap-1.5">
          {syncStamp ? (
            <span
              aria-hidden
              className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"
            />
          ) : null}
          <span title={syncStamp ? syncStamp.toLocaleString("en-US") : undefined}>{syncLabel}</span>
        </span>
      </motion.p>
    </motion.header>
  );
}
