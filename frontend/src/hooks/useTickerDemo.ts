/**
 * useTickerDemo — Option C: Demo-mode live transaction ticker.
 *
 * Fetches the 20 most recent real transactions from the DB once, then rotates
 * through them every 3.5 s. Gives the "LIVE" feel during judge presentations
 * without needing WebSocket / SSE infrastructure.
 *
 * When real-time infra is wired up, replace the `getTransactions` call with
 * a WebSocket or Supabase Realtime channel and push new items via `setQueue`.
 */
import { useEffect, useRef, useState } from "react";
import { getTransactions } from "../services/api";

export type TickerTransaction = {
  id: string | number;
  amount: number;
  merchant: string;
  /** Normalised to uppercase "CREDIT" | "DEBIT". */
  type: "CREDIT" | "DEBIT";
};

type UseTickerDemoResult = {
  transaction: TickerTransaction | null;
  loading: boolean;
  error: boolean;
};

export function useTickerDemo(
  userId: number | string | null | undefined
): UseTickerDemoResult {
  const [queue, setQueue] = useState<TickerTransaction[]>([]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch recent transactions once per userId ──────────────────────────────
  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(false);

    (getTransactions as Function)(userId, { limit: 20 })
      .then((data: unknown) => {
        if (cancelled) return;

        // API may return the array directly or wrapped in { transactions: [...] } / { data: [...] }
        const rows: Record<string, unknown>[] = Array.isArray(data)
          ? (data as Record<string, unknown>[])
          : ((data as Record<string, unknown[]>)?.transactions as Record<string, unknown>[] | undefined) ??
            ((data as Record<string, unknown[]>)?.data as Record<string, unknown>[] | undefined) ??
            [];

        const mapped: TickerTransaction[] = rows
          .filter((r) => r && r.amount != null && r.merchant)
          .slice(0, 20)
          .map((r, i) => ({
            id: (r.id ?? r.transaction_id ?? i) as string | number,
            amount: Number(r.amount),
            merchant: String(r.merchant),
            // Backend stores "CREDIT" / "DEBIT" (uppercase); handle lowercase gracefully
            type: String(r.type ?? "")
              .toUpperCase()
              .startsWith("C")
              ? "CREDIT"
              : "DEBIT",
          }));

        setQueue(mapped);
        setIndex(0);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [userId]);

  // ── Rotate through the queue every 3.5 s ──────────────────────────────────
  useEffect(() => {
    if (!queue.length) return;

    timerRef.current = setInterval(() => {
      setIndex((i) => (i + 1) % queue.length);
    }, 3500);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [queue]);

  return {
    transaction: queue.length > 0 ? queue[index] : null,
    loading,
    error,
  };
}

export default useTickerDemo;
