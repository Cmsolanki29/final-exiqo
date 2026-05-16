/**
 * DashboardGreeting — Two-line personal header with dynamic status pill.
 *
 * Layout:
 *   Line 1: "Good morning,"   → text-2xl font-light text-gray-400
 *   Line 2: "Vikram"          → text-4xl font-bold gradient (white → purple-300)
 *   Status pill: right-aligned, changes based on financial state
 *   Metadata row: date · live-dot · last synced
 *
 * Time logic:
 *   05:00 – 11:59 → "Good morning"
 *   12:00 – 16:59 → "Good afternoon"
 *   17:00 – 20:59 → "Good evening"
 *   21:00 – 04:59 → "Working late"
 */
import React, { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { useAuth } from "../../context/AuthContext";

function getGreeting(d: Date): string {
  const hour = d.getHours();
  if (hour >= 5  && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  if (hour >= 17 && hour < 21) return "Good evening";
  return "Working late";
}

/** Returns first name only for warmth (e.g. "Vikram Singh" → "Vikram"). */
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

export type DashboardGreetingProps = {
  /** Real DB-backed timestamp from MAX(bank_connections.last_synced). */
  lastSync: Date | null;
  /** Backend last_login fallback when no bank is linked. */
  lastLogin?: Date | null;
  /** True while either auth or dashboard data is still loading. */
  loading?: boolean;
  /** Current month's total spend — drives status pill. */
  monthSpend?: number;
  /** Current month's total income — drives status pill. */
  monthIncome?: number;
  /** FraudShield pending alert count — drives status pill priority. */
  fraudPending?: number;
  /** Year-to-date savings — drives status pill. */
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

  // Refresh once a minute so greeting and relative-time stay accurate.
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const isLoading = loading || authLoading || !user;
  if (isLoading) {
    return (
      <header aria-busy="true" className="mb-8 space-y-2">
        <div className="h-7 w-44 rounded-md bg-white/[0.05] animate-pulse" />
        <div className="h-11 w-56 rounded-md bg-white/[0.06] animate-pulse" />
        <div className="mt-3 h-3.5 w-52 rounded-md bg-white/[0.04] animate-pulse" />
      </header>
    );
  }

  const greeting   = getGreeting(now);
  const firstName  = getFirstName(user?.name, user?.email);
  const status     = getStatusConfig(monthSpend, monthIncome, fraudPending, savedYtd);
  const syncStamp  = lastSync ?? lastLogin ?? null;
  const syncLabel  = syncStamp
    ? `Last synced ${formatRelative(syncStamp)}`
    : "No bank linked yet";

  return (
    <motion.header
      initial={reduce ? { opacity: 1 } : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="mb-8"
    >
      {/* Name + status pill row */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          {/* Line 1 — salutation */}
          <p className="text-2xl font-light leading-tight text-gray-400">
            {greeting},
          </p>
          {/* Line 2 — first name with gradient */}
          <h1 className="mt-0.5 bg-gradient-to-r from-white via-purple-100 to-purple-300 bg-clip-text text-4xl font-bold tracking-tight text-transparent leading-tight">
            {firstName}
          </h1>
        </div>

        {/* Dynamic status pill */}
        <span
          className={[
            "mt-1 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium",
            status.bg,
            status.text,
            status.border,
          ].join(" ")}
        >
          <span aria-hidden>{status.emoji}</span>
          {status.label}
        </span>
      </div>

      {/* Metadata row */}
      <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-500">
        <span>{formatLongDate(now)}</span>
        <span aria-hidden className="h-1 w-1 rounded-full bg-gray-600" />
        <span className="flex items-center gap-1.5">
          {syncStamp && (
            <span
              aria-hidden
              className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"
            />
          )}
          <span
            title={syncStamp ? syncStamp.toLocaleString("en-US") : undefined}
          >
            {syncLabel}
          </span>
        </span>
      </p>
    </motion.header>
  );
}
