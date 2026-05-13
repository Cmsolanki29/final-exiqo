import React from "react";
import { Lock, Settings } from "lucide-react";
import { GlassCard } from "../intro/GlassCard";

export default function SettingsTab({ onOpenAdmin }) {
  return (
    <GlassCard padding="lg" className="mx-auto mt-4 max-w-lg border-dashed border-white/15">
      <div className="flex items-start gap-3">
        <Settings className="mt-0.5 h-6 w-6 text-exiqo-glow" aria-hidden />
        <div className="min-w-0 flex-1">
          <h2 className="font-heading text-lg font-semibold text-white">Settings</h2>
          <p className="mt-2 text-sm text-exiqo-glow/70">
            Account preferences, data export, and notifications will land here. Use the month switcher in the top bar for now.
          </p>
          <p className="mt-3 inline-flex rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-exiqo-glow/80">
            Coming soon
          </p>
          {typeof onOpenAdmin === "function" ? (
            <div className="mt-6 border-t border-white/10 pt-5">
              <p className="text-xs font-medium text-exiqo-glow/55">Internal tools</p>
              <p className="mt-1 text-sm text-exiqo-glow/70">
                ML ops consoles (AI performance, GNN, DNN shadow, orchestrator) are not listed in the workspace sidebar. Unlock with your admin passphrase.
              </p>
              <button
                type="button"
                onClick={() => onOpenAdmin()}
                className="mt-3 inline-flex items-center gap-2 rounded-xl border border-violet-500/40 bg-violet-500/15 px-4 py-2.5 text-sm font-semibold text-violet-100 transition hover:bg-violet-500/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40"
              >
                <Lock className="h-4 w-4 shrink-0" aria-hidden />
                Unlock engine diagnostics
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </GlassCard>
  );
}
