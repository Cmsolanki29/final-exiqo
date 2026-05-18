import React, { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Terminal } from "lucide-react";
import { getEnrichedReviewQueue, triggerInvestigation } from "../../services/riskApi";

/**
 * Runs a real Phase 9 investigation (POST …/investigations/{id}/run).
 * Uses the first pending review-queue item for this user — same source as the Investigations tab.
 */
export default function InvestigationConsole({ userId }) {
  const [running, setRunning] = useState(false);
  const [lines, setLines] = useState([]);
  const [targetLabel, setTargetLabel] = useState("Next pending review item");

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    getEnrichedReviewQueue("pending", 5, userId)
      .then((res) => {
        if (cancelled) return;
        const items = res?.items ?? (Array.isArray(res) ? res : []);
        const pick = items.find((it) => {
          const id = it.transaction_id ?? it.id;
          return id != null && String(id) !== "";
        });
        if (pick) {
          const tid = pick.transaction_id ?? pick.id;
          setTargetLabel(`Txn #${tid} · ${pick.merchant || "Unknown merchant"}`);
        } else {
          setTargetLabel("No queued items");
        }
      })
      .catch(() => {
        if (!cancelled) setTargetLabel("Queue unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const run = useCallback(async () => {
    if (!userId) {
      setLines(["Sign in to run an investigation."]);
      return;
    }
    setRunning(true);
    setLines([]);
    try {
      const res = await getEnrichedReviewQueue("pending", 8, userId);
      const items = res?.items ?? (Array.isArray(res) ? res : []);
      const pick = items.find((it) => {
        const id = it.transaction_id ?? it.id;
        return id != null && String(id) !== "";
      });
      if (!pick) {
        setLines(["No pending review-queue transactions for this account in the current dashboard view."]);
        setRunning(false);
        return;
      }
      const txnId = pick.transaction_id ?? pick.id;
      setTargetLabel(`Txn #${txnId} · ${pick.merchant || "Unknown merchant"}`);
      setLines([`Calling investigation agent for transaction #${txnId}…`]);
      const data = await triggerInvestigation(txnId, userId, "manual");
      const reasoning = data?.reasoning || data?.agent_reasoning || data?.summary || "";
      const action = data?.recommended_action || data?.verdict || "";
      const chunks = reasoning ? reasoning.split(/\n+/).map((s) => s.trim()).filter(Boolean) : [];
      const nextLines = [
        `Calling investigation agent for transaction #${txnId}…`,
        ...chunks.slice(0, 20),
        action ? `Recommended action: ${action}` : null,
        Number.isFinite(data?.cost_usd) ? `Reported API cost: $${Number(data.cost_usd).toFixed(4)}` : null,
      ].filter(Boolean);
      setLines(nextLines);
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || "Investigation failed";
      setLines((prev) => [...prev, `Error: ${msg}`]);
    } finally {
      setRunning(false);
    }
  }, [userId]);

  return (
    <div className="mb-6 rounded-2xl border border-violet-500/25 bg-gradient-to-br from-violet-500/10 to-slate-900/40 p-5 shadow-[0_0_40px_-12px_rgba(124,58,237,0.45)]">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          <div className="mt-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.06]">
            <Terminal className="h-5 w-5 text-violet-200" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-gray-500">Phase 9 · Live console</p>
            <h3 className="mt-1 text-lg font-bold tracking-tight text-white">Investigation stream</h3>
            <p className="mt-1 max-w-xl text-xs leading-relaxed text-gray-400">
              Uses{" "}
              <code className="rounded bg-black/30 px-1 text-[10px]">POST /risk/investigations/{"{txn}"}/run</code> on the first
              pending queue row — same backend as Investigations below.
            </p>
          </div>
        </div>
        <button
          type="button"
          disabled={running}
          onClick={run}
          className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-500/30 transition hover:brightness-110 disabled:opacity-50"
        >
          <Sparkles className="h-4 w-4" aria-hidden />
          {running ? "Running…" : "Run investigation"}
        </button>
      </div>
      <div className="rounded-xl border border-white/10 bg-black/35 p-4 font-mono text-[11px] leading-relaxed text-emerald-100/90">
        <p className="mb-2 text-gray-400">Target: {targetLabel}</p>
        {lines.length === 0 && !running ? (
          <p className="text-gray-500">Press Run investigation to execute the agent on the first pending queue item.</p>
        ) : (
          <ul className="space-y-1.5">
            <AnimatePresence initial={false}>
              {lines.map((line, idx) => (
                <motion.li
                  key={`${idx}-${line.slice(0, 32)}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                  className="text-emerald-100/95"
                >
                  {line}
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
        {running ? <p className="mt-3 animate-pulse text-amber-200/85">Calling backend…</p> : null}
      </div>
    </div>
  );
}
