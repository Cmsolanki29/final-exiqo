import React from "react";
import { Lock, Settings } from "lucide-react";
import { GlassCard } from "../intro/GlassCard";

export default function SettingsTab({ onOpenAdmin }) {
  return (
    <GlassCard padding="lg" className="mx-auto mt-4 max-w-lg border border-violet-500/20">
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/15 border border-violet-500/25">
          <Settings className="h-5 w-5 text-violet-400" aria-hidden />
        </div>

        <div className="min-w-0 flex-1">
          {/* Heading — white for strong hierarchy */}
          <h2 className="font-heading text-lg font-semibold text-white">
            Settings
          </h2>

          {/* Body text — slate-300 for WCAG AA contrast on dark background */}
          <p className="mt-2 text-sm leading-relaxed text-slate-300">
            Account preferences, data export, and notifications will land here.
            Use the{" "}
            <span className="font-medium text-violet-400">month switcher</span>
            {" "}in the top bar for now.
          </p>

          {/* COMING SOON badge — visible with purple tint */}
          <span className="mt-3 inline-flex items-center rounded-full border border-violet-500/40 bg-violet-500/15 px-3 py-1 text-[11px] font-bold uppercase tracking-widest text-violet-300">
            Coming Soon
          </span>

          {/* Internal tools section */}
          {typeof onOpenAdmin === "function" && (
            <div className="mt-6 border-t border-white/10 pt-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Internal Tools
              </p>
              <p className="mt-2 text-sm leading-relaxed text-slate-300">
                ML ops consoles (AI performance, GNN, DNN shadow, orchestrator) are
                not listed in the workspace sidebar. Unlock with your{" "}
                <span className="font-medium text-violet-400">admin passphrase</span>.
              </p>
              <button
                type="button"
                onClick={() => onOpenAdmin()}
                className="mt-4 inline-flex items-center gap-2 rounded-xl border border-violet-500/40 bg-violet-500/15 px-4 py-2.5 text-sm font-semibold text-violet-100 shadow-[0_0_20px_-8px_rgba(124,58,237,0.4)] transition-all duration-200 hover:bg-violet-500/25 hover:border-violet-400/60 hover:shadow-[0_0_28px_-6px_rgba(124,58,237,0.55)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
              >
                <Lock className="h-4 w-4 shrink-0" aria-hidden />
                Unlock engine diagnostics
              </button>
            </div>
          )}
        </div>
      </div>
    </GlassCard>
  );
}
