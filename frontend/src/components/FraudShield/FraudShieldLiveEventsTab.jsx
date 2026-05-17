import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Pause, Play, Radio } from "lucide-react";
import LiveEventRow from "./LiveEventRow";
import { MiniSparkline } from "./MiniSparkline";
import { getFraudShieldLiveEvents } from "../../services/riskApi";
import { RiskStatePlaceholder } from "../risk/RiskStatePlaceholder";

function eventsPerMinute(list, windowMs = 60_000) {
  const now = Date.now();
  return list.filter((e) => {
    const t = e.ts instanceof Date ? e.ts.getTime() : new Date(e.ts).getTime();
    return now - t < windowMs;
  }).length;
}

function mapEvent(raw) {
  return {
    id: raw.id || `evt-${raw.transaction_id}`,
    ts: raw.ts ? new Date(raw.ts) : new Date(),
    merchant: raw.merchant || "Transaction",
    amount: Number(raw.amount || 0),
    status: raw.status || "REVIEW",
    score: Number(raw.score || 0),
  };
}

export default function FraudShieldLiveEventsTab({ userId }) {
  const [paused, setPaused] = useState(false);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [epmHistory, setEpmHistory] = useState([0]);

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError("");
    try {
      const res = await getFraudShieldLiveEvents(userId, 24);
      setEvents((res?.events || []).map(mapEvent));
    } catch (e) {
      setError(e.message || "Could not load live events");
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
    const onMode = () => load();
    window.addEventListener("dashboardModeChanged", onMode);
    return () => window.removeEventListener("dashboardModeChanged", onMode);
  }, [load]);

  useEffect(() => {
    if (paused) return undefined;
    const id = window.setInterval(load, 15000);
    return () => clearInterval(id);
  }, [paused, load]);

  useEffect(() => {
    const tick = () => setEpmHistory((h) => [...h.slice(-47), eventsPerMinute(events)]);
    tick();
    const id = window.setInterval(tick, 2000);
    return () => clearInterval(id);
  }, [events]);

  const epm = useMemo(() => eventsPerMinute(events), [events]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <span className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-300">
            <Radio className="h-5 w-5" aria-hidden />
            <span className="absolute -right-0.5 -top-0.5 h-2 w-2 animate-pulse rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
          </span>
          <div>
            <p className="text-sm font-semibold text-white">Live protection stream</p>
            <p className="text-xs text-gray-400">Real transactions from your current dashboard view.</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2">
            <div className="text-center">
              <p className="text-[10px] uppercase tracking-wider text-gray-500">Events / min</p>
              <p className="text-lg font-bold tabular-nums text-white">{epm}</p>
            </div>
            <MiniSparkline values={epmHistory} className="opacity-90" />
          </div>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.06] px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
          >
            {paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
            {paused ? "Resume" : "Pause refresh"}
          </button>
        </div>
      </div>

      {loading ? <RiskStatePlaceholder loading /> : null}
      {!loading && error ? (
        <p className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{error}</p>
      ) : null}
      {!loading && !error && events.length === 0 ? (
        <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-8 text-center text-sm text-gray-400">
          No scored transactions in your current view yet. Upload a statement or switch dashboard mode.
        </p>
      ) : null}

      <ul className="space-y-2.5">
        <AnimatePresence initial={false}>
          {events.map((e) => (
            <LiveEventRow key={e.id} event={e} />
          ))}
        </AnimatePresence>
      </ul>
    </div>
  );
}