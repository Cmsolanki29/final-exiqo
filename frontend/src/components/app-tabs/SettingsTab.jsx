import React from "react";
import { Lock, Settings } from "lucide-react";
import { GlassCard } from "../intro/GlassCard";
import UploadStatement from "../Upload/UploadStatement";

export default function SettingsTab({ onOpenAdmin, userId }) {
  return (
    <div className="space-y-6 pb-10">
      {/* Upload Statement */}
      {userId ? (
        <UploadStatement userId={userId} />
      ) : (
        <GlassCard padding="lg" className="mx-auto max-w-lg border-dashed border-white/15">
          <p className="text-sm text-white/50">Select a user to upload statements.</p>
        </GlassCard>
      )}

      {/* Admin / engine diagnostics */}
      {typeof onOpenAdmin === "function" && (
        <GlassCard padding="lg" className="mx-auto max-w-lg border-dashed border-white/15">
          <div className="flex items-start gap-3">
            <Settings className="mt-0.5 h-6 w-6 text-exiqo-glow shrink-0" aria-hidden />
            <div className="min-w-0 flex-1">
              <h2 className="font-heading text-lg font-semibold text-white">Engine Diagnostics</h2>
              <p className="mt-2 text-sm text-exiqo-glow/70">
                ML ops consoles (AI performance, GNN, DNN shadow, orchestrator) are not listed in the workspace
                sidebar. Unlock with your admin passphrase.
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
          </div>
        </GlassCard>
      )}
    </div>
  );
}
