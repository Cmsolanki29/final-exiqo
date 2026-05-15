import React from "react";
import { ArrowLeft } from "lucide-react";
import SubscriptionIntelligence from "./SubscriptionIntelligence";

/**
 * Feature A — dedicated surface for verdicts, migrations, insights (hub handles connect / add apps).
 * @param {() => void} props.onBack
 * @param {() => void} props.onOpenReminders
 */
export default function AIAnalysisEngine({ onBack, onOpenReminders }) {
  return (
    <div className="mx-auto max-w-6xl space-y-8 pb-16">
      <nav className="text-xs text-gray-500" aria-label="Breadcrumb">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            className="font-medium text-cyan-200/90 underline-offset-2 hover:text-cyan-100 hover:underline"
          >
            Intelligence hub
          </button>
          <span aria-hidden className="text-white/25">
            /
          </span>
          <span className="text-white/70">AI subscription intelligence</span>
        </div>
      </nav>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Back to hub
        </button>
        <p className="text-xs text-gray-500">Live data from subscription-intelligence APIs</p>
      </div>

      <SubscriptionIntelligence onOpenReminders={onOpenReminders} />
    </div>
  );
}
