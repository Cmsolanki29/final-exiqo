import React from "react";

const SEGMENT_META = [
  { key: "flights_inr", label: "Flights", color: "#22D3EE" },
  { key: "hotels_inr", label: "Hotels", color: "#A78BFA" },
  { key: "food_inr", label: "Food", color: "#F59E0B" },
  { key: "local_transport_inr", label: "Transport", color: "#10B981" },
  { key: "activities_inr", label: "Activities", color: "#EC4899" },
  { key: "buffer_inr", label: "Safety buffer", color: "#64748B" },
];

const inr = (n) =>
  typeof n === "number"
    ? `₹${Math.round(n).toLocaleString("en-IN")}`
    : "—";

export default function BudgetBreakdown({ breakdown, total }) {
  const safeBreakdown = breakdown || {};
  const segments = SEGMENT_META.map((s) => ({
    ...s,
    value: Number(safeBreakdown[s.key] || 0),
  }));
  const computedTotal = total || segments.reduce((acc, s) => acc + s.value, 0);

  if (!computedTotal) return null;

  return (
    <div className="mt-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4">
      <div className="mb-3 flex items-end justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500">
          Cost breakdown
        </span>
        <span className="font-heading text-lg font-semibold tabular-nums text-white">
          {inr(computedTotal)}
        </span>
      </div>

      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
        {segments.map((s) => {
          const pct = (s.value / computedTotal) * 100;
          if (pct <= 0) return null;
          return (
            <div
              key={s.key}
              style={{ width: `${pct}%`, background: s.color }}
              title={`${s.label} · ${inr(s.value)}`}
            />
          );
        })}
      </div>

      <ul className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-300 sm:grid-cols-3">
        {segments.map((s) =>
          s.value > 0 ? (
            <li key={s.key} className="flex items-center gap-2">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="truncate">
                {s.label} <span className="text-white/70 tabular-nums">{inr(s.value)}</span>
              </span>
            </li>
          ) : null
        )}
      </ul>
    </div>
  );
}
