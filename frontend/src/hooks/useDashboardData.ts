/**
 * useDashboardData — fetches GET /api/dashboard/{userId} (the backend's
 * one-shot dashboard aggregate) and exposes the slim fields the page header
 * needs:
 *   - user        : { id, name, email, monthly_income, ... }
 *   - lastSynced  : Date | null   (MAX across bank_connections.last_synced)
 *   - lastLogin   : Date | null   (users.last_login fallback)
 *   - fraudPending: number        (count of PENDING fraud_alerts for the user)
 *
 * The dashboard's per-card data still flows through useSmartSpend(); this hook
 * only adds the live-freshness signals that drive the greeting + status pill.
 *
 * No new dependencies — plain useEffect + axios (already used app-wide).
 */
import { useCallback, useEffect, useState } from "react";
import { getDashboardSummary } from "../services/api";

export type DashboardUser = {
  id: number;
  name: string;
  email: string;
  monthly_income?: number;
  savings_goal?: number;
  risk_tolerance?: string;
};

export type DashboardData = {
  user: DashboardUser | null;
  lastSynced: Date | null;
  lastLogin: Date | null;
  fraudPending: number;
  unreadAlerts: number;
  raw: unknown;
};

export type UseDashboardDataResult = DashboardData & {
  loading: boolean;
  error: string;
  refetch: () => Promise<void>;
};

const EMPTY: DashboardData = {
  user: null,
  lastSynced: null,
  lastLogin: null,
  fraudPending: 0,
  unreadAlerts: 0,
  raw: null,
};

function toDate(value: unknown): Date | null {
  if (!value) return null;
  if (value instanceof Date) return value;
  if (typeof value !== "string" && typeof value !== "number") return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function useDashboardData(userId: number | null | undefined): UseDashboardDataResult {
  const [state, setState] = useState<{ data: DashboardData; loading: boolean; error: string }>({
    data: EMPTY,
    loading: Boolean(userId),
    error: "",
  });

  const load = useCallback(async () => {
    if (!userId) {
      setState({ data: EMPTY, loading: false, error: "" });
      return;
    }
    setState((s) => ({ ...s, loading: true, error: "" }));
    try {
      const res = (await getDashboardSummary(userId)) as Record<string, unknown> | null;
      const userRaw = (res?.user || null) as DashboardUser | null;
      setState({
        data: {
          user: userRaw,
          lastSynced: toDate(res?.last_synced),
          lastLogin: toDate(res?.last_login),
          fraudPending: Number(res?.fraud_pending_count ?? 0),
          unreadAlerts: Number(res?.unread_alerts ?? 0),
          raw: res ?? null,
        },
        loading: false,
        error: "",
      });
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : typeof err === "string"
            ? err
            : "Could not load dashboard";
      setState({ data: EMPTY, loading: false, error: msg });
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state.data, loading: state.loading, error: state.error, refetch: load };
}

export default useDashboardData;
