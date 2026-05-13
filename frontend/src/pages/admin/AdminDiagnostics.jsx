import React, { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, Lock, Shield } from "lucide-react";
import { SkeletonCard } from "../../components/common/SkeletonCard";

const AIPerformance = lazy(() => import("../risk/AIPerformance"));
const GNNTrainingPanel = lazy(() => import("../risk/GNNTrainingPanel"));
const DNNShadowReport = lazy(() => import("../risk/DNNShadowReport"));
const OrchestratorDashboard = lazy(() => import("../risk/OrchestratorDashboard"));

const STORAGE_KEY = "ss_admin_diag_ok";
const EXPECTED =
  process.env.REACT_APP_ADMIN_UNLOCK ||
  process.env.REACT_APP_ADMIN_TOKEN ||
  "dev-admin-secret";

const TABS = [
  { id: "ai", label: "AI performance" },
  { id: "gnn", label: "GNN training" },
  { id: "dnn", label: "DNN shadow" },
  { id: "orch", label: "Orchestrator" },
];

const fallback = (
  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
    <SkeletonCard lines={4} height={120} />
  </div>
);

export default function AdminDiagnostics({ onExit }) {
  const [unlocked, setUnlocked] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [tab, setTab] = useState("ai");

  useEffect(() => {
    try {
      setUnlocked(window.sessionStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      setUnlocked(false);
    }
  }, []);

  const tryUnlock = useCallback(
    (e) => {
      e?.preventDefault?.();
      setError("");
      if (password.trim() === String(EXPECTED)) {
        try {
          window.sessionStorage.setItem(STORAGE_KEY, "1");
        } catch {
          /* ignore */
        }
        setUnlocked(true);
        setPassword("");
        return;
      }
      setError("Incorrect passphrase. Use the same value as REACT_APP_ADMIN_TOKEN (or REACT_APP_ADMIN_UNLOCK) in your env.");
    },
    [password]
  );

  const lock = useCallback(() => {
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setUnlocked(false);
    setPassword("");
  }, []);

  if (!unlocked) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto mt-6 max-w-md rounded-3xl border border-white/10 bg-white/[0.04] p-8 shadow-[0_0_50px_-20px_rgba(124,58,237,0.45)] backdrop-blur-xl"
      >
        <div className="mb-6 flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/25 text-violet-200">
            <Lock className="h-6 w-6" aria-hidden />
          </span>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">Engine diagnostics</h1>
            <p className="text-xs text-exiqo-glow/60">Internal ML consoles — not part of the banking workspace.</p>
          </div>
        </div>
        <form onSubmit={tryUnlock} className="space-y-4">
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-exiqo-glow/50" htmlFor="admin-pass">
            Passphrase
          </label>
          <input
            id="admin-pass"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(ev) => setPassword(ev.target.value)}
            className="w-full rounded-xl border border-white/15 bg-black/30 px-4 py-3 text-sm text-white outline-none ring-0 placeholder:text-exiqo-glow/35 focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-400/30"
            placeholder="Admin token"
          />
          {error ? <p className="text-xs text-rose-300/90">{error}</p> : null}
          <div className="flex flex-wrap gap-2 pt-2">
            <button
              type="submit"
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_0_24px_-8px_rgba(124,58,237,0.55)] min-[360px]:flex-none"
            >
              <Shield className="h-4 w-4" aria-hidden />
              Unlock
            </button>
            <button
              type="button"
              onClick={() => onExit?.()}
              className="rounded-xl border border-white/15 px-4 py-2.5 text-sm font-medium text-exiqo-glow/80 hover:bg-white/[0.06] hover:text-white"
            >
              Back
            </button>
          </div>
        </form>
      </motion.div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => onExit?.()}
            className="rounded-xl border border-white/10 p-2 text-exiqo-glow/70 transition hover:bg-white/[0.06] hover:text-white"
            aria-label="Back to settings"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">Engine diagnostics</h1>
            <p className="text-xs text-exiqo-glow/55">Session unlocked on this device only.</p>
          </div>
        </div>
        <button
          type="button"
          onClick={lock}
          className="rounded-xl border border-white/15 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-exiqo-glow/75 hover:bg-white/[0.06] hover:text-white"
        >
          Lock
        </button>
      </div>

      <div className="flex flex-wrap gap-2 rounded-2xl border border-white/10 bg-white/[0.03] p-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40 ${
              tab === t.id
                ? "bg-gradient-to-r from-violet-600 to-blue-600 text-white shadow-[0_0_20px_-8px_rgba(124,58,237,0.5)]"
                : "text-exiqo-glow/75 hover:bg-white/[0.06] hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="rounded-3xl border border-white/[0.08] bg-white/[0.02] p-5 backdrop-blur-xl sm:p-7">
        {tab === "ai" && (
          <Suspense fallback={fallback}>
            <AIPerformance />
          </Suspense>
        )}
        {tab === "gnn" && (
          <Suspense fallback={fallback}>
            <GNNTrainingPanel />
          </Suspense>
        )}
        {tab === "dnn" && (
          <Suspense fallback={fallback}>
            <DNNShadowReport />
          </Suspense>
        )}
        {tab === "orch" && (
          <Suspense fallback={fallback}>
            <OrchestratorDashboard />
          </Suspense>
        )}
      </div>
    </div>
  );
}
