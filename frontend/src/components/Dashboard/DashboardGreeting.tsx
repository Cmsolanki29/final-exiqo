/**
 * DashboardGreeting — minimal, single-line header.
 *
 *   Good morning, Vikram Singh
 *   Friday, May 15 · 🟢 Last synced 4 minutes ago
 *
 * That's it.  No gradient on the name, no status pill, no decorative icons —
 * the greeting and name share the same size / weight / colour and read as one
 * sentence.  All four greetings come from a single helper:
 *
 *   05:00 – 11:59 → "Good morning"
 *   12:00 – 16:59 → "Good afternoon"
 *   17:00 – 20:59 → "Good evening"
 *   21:00 – 04:59 → "Good night"
 *
 * Data sources (unchanged):
 *   • name / email   — useAuth().user        (GET /api/auth/me)
 *   • lastSync       — props from parent     (MAX(bank_connections.last_synced))
 *   • lastLogin      — props from parent     (users.last_login fallback)
 */
import React, { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { useAuth } from "../../context/AuthContext";

/** The four greetings allowed on the dashboard. Nothing else ships here. */
function getGreeting(d: Date): string {
  const hour = d.getHours();
  if (hour >= 5  && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  if (hour >= 17 && hour < 21) return "Good evening";
  return "Good night";
}

/**
 * Full DB name first, then email-prefix (capitalised), then "there".
 * Returns the FULL name (e.g. "Vikram Singh") so the greeting reads the way
 * Mercury / Ramp / Stripe address users.
 */
function resolveDisplayName(name?: string | null, email?: string | null): string {
  const trimmedName = (name || "").trim();
  if (trimmedName) return trimmedName;

  const local = (email || "").trim().split("@")[0];
  if (local) return local.charAt(0).toUpperCase() + local.slice(1);

  return "there";
}

/** "Friday, May 15" — en-US ordering. */
function formatLongDate(d: Date): string {
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

/** Pure JS relative-time formatter. */
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

/**
 * Props are kept backward-compatible with Dashboard.tsx: the older fields
 * (monthSpend, monthIncome, fraudPending, savedYtd) are accepted but ignored
 * here, since the simplified greeting doesn't render the status pill anymore.
 */
export type DashboardGreetingProps = {
  /** Real DB-backed timestamp from MAX(bank_connections.last_synced). */
  lastSync: Date | null;
  /** Backend last_login fallback when no bank is linked. */
  lastLogin?: Date | null;
  /** True while either auth or dashboard data is still loading. */
  loading?: boolean;
  /** @deprecated  retained only so the parent doesn't break. */
  monthSpend?: number;
  /** @deprecated */
  monthIncome?: number;
  /** @deprecated */
  fraudPending?: number;
  /** @deprecated */
  savedYtd?: number;
};

export default function DashboardGreeting({
  lastSync,
  lastLogin = null,
  loading = false,
}: DashboardGreetingProps) {
  const reduce = useReducedMotion();
  const { user, loading: authLoading } = useAuth();
  const [now, setNow] = useState(() => new Date());

  // Refresh once a minute so the relative-time string stays accurate and the
  // greeting flips at the boundary (e.g. evening → night at 21:00).
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  // Compact skeleton matching the new single-line layout.
  const isLoading = loading || authLoading || !user;
  if (isLoading) {
    return (
      <header aria-busy="true" className="mb-8 space-y-2">
        <div className="h-8 w-72 rounded-md bg-white/[0.05] animate-pulse" />
        <div className="h-3.5 w-56 rounded-md bg-white/[0.04] animate-pulse" />
      </header>
    );
  }

  const greeting    = getGreeting(now);
  const displayName = resolveDisplayName(user?.name, user?.email);

  // Real bank-sync timestamp first; fall back to last_login; never show fake.
  const syncTimestamp = lastSync ?? lastLogin ?? null;
  const syncLabel     = syncTimestamp
    ? `Last synced ${formatRelative(syncTimestamp)}`
    : "No bank linked yet";

  return (
    <motion.header
      initial={reduce ? { opacity: 1 } : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="mb-8"
    >
      {/* Greeting + name on ONE line, identical styling */}
      <h1 className="text-3xl font-semibold tracking-tight text-white">
        {greeting}, {displayName}
      </h1>

      {/* Metadata row */}
      <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-gray-500">
        <span>{formatLongDate(now)}</span>
        <span aria-hidden className="h-1 w-1 rounded-full bg-gray-600" />
        <span className="flex items-center gap-1.5">
          {syncTimestamp && (
            <span
              aria-hidden
              className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"
            />
          )}
          <span title={syncTimestamp ? syncTimestamp.toLocaleString("en-US") : undefined}>
            {syncLabel}
          </span>
        </span>
      </p>
    </motion.header>
  );
}
