import React, { useMemo } from "react";

function pin(city) {
  const l = (city || "").toLowerCase();
  if (l.includes("mumbai")) return { cx: 22, cy: 58, label: "Mumbai" };
  if (l.includes("pune")) return { cx: 28, cy: 62, label: "Pune" };
  if (l.includes("bangalore") || l.includes("bengaluru")) return { cx: 38, cy: 72, label: "Bengaluru" };
  if (l.includes("delhi")) return { cx: 35, cy: 38, label: "Delhi" };
  if (l.includes("singapore")) return { cx: 88, cy: 78, label: "Singapore", off: true };
  return { cx: 48 + (city?.length || 0) % 20, cy: 52, label: city || "?" };
}

/** Mini map + legend for behaviour locations (same visual language as Device Trust). */
export function LocationPatternMap({ locations = [], embedded = true }) {
  const pins = useMemo(() => {
    const seen = new Set();
    return (locations || [])
      .filter((loc) => {
        const k = loc.city;
        if (!k || seen.has(k)) return false;
        seen.add(k);
        return true;
      })
      .map((loc) => ({ ...pin(loc.city), count: loc.count, risk: loc.risk, city: loc.city }));
  }, [locations]);

  if (pins.length === 0) {
    return (
      <div
        className={
          embedded
            ? "rounded-2xl border border-white/10 bg-white/[0.03] p-4"
            : "rounded-2xl border border-gray-100 bg-white p-4 shadow-sm"
        }
      >
        <p className={embedded ? "mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-500" : "mb-2 text-[10px] font-semibold uppercase text-gray-500"}>
          Your geography pattern
        </p>
        <p className={embedded ? "text-xs leading-relaxed text-gray-500" : "text-xs leading-relaxed text-gray-600"}>
          No city fingerprints on your transactions yet. When your data includes a location field, we map it here.
        </p>
      </div>
    );
  }

  return (
    <div
      className={
        embedded
          ? "rounded-2xl border border-white/10 bg-white/[0.03] p-4"
          : "rounded-2xl border border-gray-100 bg-white p-4 shadow-sm"
      }
    >
      <p className={embedded ? "mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-500" : "mb-2 text-[10px] font-semibold uppercase text-gray-500"}>
        Your geography pattern
      </p>
      <svg viewBox="0 0 100 100" className="mx-auto h-36 w-full max-w-[240px]" aria-hidden>
        <defs>
          <linearGradient id="locMapFill" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(124,58,237,0.35)" />
            <stop offset="100%" stopColor="rgba(37,99,235,0.18)" />
          </linearGradient>
        </defs>
        <path
          fill="url(#locMapFill)"
          stroke={embedded ? "rgba(255,255,255,0.12)" : "#e5e7eb"}
          strokeWidth="0.35"
          d="M18 28 L42 22 L58 18 L72 26 L80 40 L78 58 L70 72 L52 82 L32 78 L20 62 Z"
        />
        {pins.map((p) => (
          <g key={p.city}>
            <circle
              cx={p.cx}
              cy={p.cy}
              r={p.off ? 2.8 : 3.2}
              fill={p.risk === "high" ? "#f87171" : p.risk === "medium" ? "#fbbf24" : "#22d3ee"}
              stroke="rgba(0,0,0,0.25)"
              strokeWidth="0.3"
            />
          </g>
        ))}
      </svg>
      <ul className="mt-2 flex flex-wrap gap-2">
        {pins.map((p) => (
          <li
            key={p.city}
            className={
              embedded
                ? "rounded-full border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[10px] text-gray-400"
                : "rounded-full border border-gray-100 bg-gray-50 px-2 py-0.5 text-[10px] text-gray-600"
            }
          >
            {p.label} · {p.count} sessions
          </li>
        ))}
      </ul>
    </div>
  );
}
