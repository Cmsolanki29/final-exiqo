import React from "react";
import { Sparkles } from "lucide-react";

const DEFAULT_PROMPTS = [
  "Plan a Kashmir trip for 5 days",
  "Cheapest Goa weekend this month",
  "International trip under ₹50,000",
  "Best place to visit in December",
  "Mujhe Ladakh trip plan karni hai",
];

export default function SuggestedPrompts({ onSelect, prompts, disabled }) {
  const list = Array.isArray(prompts) && prompts.length > 0 ? prompts : DEFAULT_PROMPTS;
  return (
    <div className="flex flex-wrap gap-2">
      {list.map((p) => (
        <button
          key={p}
          type="button"
          disabled={disabled}
          onClick={() => onSelect?.(p)}
          className="group inline-flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/[0.08] px-3 py-1.5 text-xs text-violet-100 transition-colors hover:border-violet-500/60 hover:bg-violet-500/[0.15] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Sparkles className="h-3 w-3 text-violet-300" aria-hidden />
          <span className="truncate max-w-[260px]">{p}</span>
        </button>
      ))}
    </div>
  );
}
