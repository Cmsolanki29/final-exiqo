import React, { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Minus, RefreshCw } from "lucide-react";
import { GlassCard } from "../intro/GlassCard";

// ── Grade palette ──────────────────────────────────────────────────────────
const gradeColor = {
  A: "#22c55e",
  B: "#3b82f6",
  C: "#f59e0b",
  D: "#f97316",
  F: "#ef4444",
};

// Semicircle arc constants (viewBox 0 0 200 130)
// Center: (100,105), Radius: 80
// Arc: M 20 105 A 80 80 0 0 1 180 105
const ARC_PATH = "M 20 105 A 80 80 0 0 1 180 105";
const ARC_LENGTH = 251.3; // π × 80

// ── Trend badge ────────────────────────────────────────────────────────────
function TrendBadge({ trend }) {
  const up = trend === "IMPROVING";
  const down = trend === "DECLINING";
  const Icon = up ? ArrowUpRight : down ? ArrowDownRight : Minus;
  const cls = up
    ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-300"
    : down
    ? "border-rose-500/35 bg-rose-500/10 text-rose-300"
    : "border-white/10 bg-white/[0.06] text-white/60";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${cls}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {trend || "STABLE"}
    </span>
  );
}

// ── Sub-score bar ──────────────────────────────────────────────────────────
function Breakdown({ label, value, max, delayMs }) {
  const v =
    value === null || value === undefined || Number.isNaN(Number(value))
      ? null
      : Number(value);
  const ratio = v == null ? 0 : Math.max(0, Math.min(100, (v / max) * 100));
  const labelRight = v == null ? "—" : `${v}/${max}`;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[11px]">
        <span className="text-white/60">{label}</span>
        <span className="tabular-nums font-semibold text-white/85">{labelRight}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className="h-full rounded-full"
          style={{
            background: "linear-gradient(90deg,#7C3AED,#A855F7,#22D3EE)",
          }}
          initial={{ width: 0 }}
          animate={{ width: `${ratio}%` }}
          transition={{
            duration: 0.9,
            delay: (delayMs || 0) / 1000,
            ease: [0.22, 1, 0.36, 1],
          }}
        />
      </div>
    </div>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────
function GaugeSkeleton() {
  return (
    <div className="space-y-3 py-4">
      <div className="mx-auto h-36 w-56 animate-pulse rounded-full bg-white/[0.06]" />
      <div className="space-y-2.5 pt-2">
        {[1, 2, 3, 4, 5].map((k) => (
          <div key={k} className="h-2 w-full animate-pulse rounded-full bg-white/[0.06]" />
        ))}
      </div>
    </div>
  );
}

// ── Custom SVG gauge ───────────────────────────────────────────────────────
function SvgGauge({ displayScore, score, grade, reduce }) {
  const filled = reduce
    ? (score / 100) * ARC_LENGTH
    : (displayScore / 100) * ARC_LENGTH;
  const gColor = gradeColor[grade] || "#ef4444";

  return (
    <div className="mx-auto" style={{ maxWidth: 260 }}>
      <svg
        viewBox="0 0 200 130"
        width="100%"
        style={{ overflow: "visible" }}
        aria-label={`Financial health score: ${displayScore} out of 100`}
      >
        <defs>
          <linearGradient id="hsg-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#7C3AED" />
            <stop offset="50%" stopColor="#A855F7" />
            <stop offset="100%" stopColor="#06b6d4" />
          </linearGradient>
        </defs>

        {/* Track */}
        <path
          d={ARC_PATH}
          stroke="rgba(255,255,255,0.07)"
          strokeWidth="13"
          fill="none"
          strokeLinecap="round"
        />

        {/* Filled arc — animated via strokeDasharray */}
        <path
          d={ARC_PATH}
          stroke="url(#hsg-grad)"
          strokeWidth="13"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${ARC_LENGTH}`}
          style={{ transition: "stroke-dasharray 1.5s cubic-bezier(0.22,1,0.36,1)" }}
        />

        {/* Score number */}
        <text
          x="100"
          y="90"
          textAnchor="middle"
          fontSize="42"
          fontWeight="800"
          fill="white"
          fontFamily="inherit"
          style={{ letterSpacing: "-2px" }}
        >
          {displayScore}
        </text>

        {/* "out of 100" */}
        <text
          x="100"
          y="110"
          textAnchor="middle"
          fontSize="11"
          fill="rgba(255,255,255,0.42)"
          fontFamily="inherit"
        >
          out of 100
        </text>

        {/* Grade pill */}
        <rect
          x="82"
          y="116"
          width="36"
          height="14"
          rx="7"
          fill={gColor}
          opacity="0.9"
        />
        <text
          x="100"
          y="126.5"
          textAnchor="middle"
          fontSize="8"
          fontWeight="700"
          fill="white"
          fontFamily="inherit"
          letterSpacing="1"
        >
          {grade}
        </text>
      </svg>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
/**
 * @param {{
 *   healthData?: Record<string, unknown>;
 *   narration?: string;
 *   variant?: "default" | "hero";
 *   loading?: boolean;
 *   loadError?: boolean;
 *   onRetry?: () => void;
 * }} props
 */
const HealthScoreGauge = ({
  healthData = {},
  narration,
  variant = "default",
  loading = false,
  loadError = false,
  onRetry,
}) => {
  const reduce = useReducedMotion();
  const rawScore = healthData.score;
  const [displayScore, setDisplayScore] = useState(0);
  const rafRef = useRef(null);

  const grade = healthData.grade || "F";
  const comp = healthData.components || {};
  const trend = healthData.trend || "STABLE";

  const targetScore = loadError || loading ? 0 : Number(rawScore || 0);

  // Animate score from 0 → targetScore using requestAnimationFrame
  useEffect(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    if (loading || loadError || reduce || !targetScore) {
      setDisplayScore(targetScore);
      return;
    }

    setDisplayScore(0);
    const startTime = performance.now();
    const duration = 1500;

    function frame(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out-cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayScore(Math.round(eased * targetScore));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(frame);
      }
    }

    // Small delay so the arc transition is visible
    const tid = setTimeout(() => {
      rafRef.current = requestAnimationFrame(frame);
    }, 120);

    return () => {
      clearTimeout(tid);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [targetScore, loading, loadError, reduce]);

  // ── Sub-scores ─────────────────────────────────────────────────────────
  const breakdowns = [
    { label: "Savings Rate", value: comp.savings_points, max: 30, delay: 0 },
    { label: "Security", value: comp.anomaly_points, max: 20, delay: 200 },
    { label: "Expense Ratio", value: comp.expense_points, max: 25, delay: 400 },
    { label: "Consistency", value: comp.consistency_points, max: 15, delay: 600 },
    { label: "Diversity", value: comp.diversity_points, max: 10, delay: 800 },
  ];

  // ── Error state ─────────────────────────────────────────────────────────
  if (loadError) {
    return (
      <GlassCard padding="md" surface="panel" className="border-white/[0.08]">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-violet-300/70">Financial Health</p>
            <h3 className="font-heading text-base font-semibold text-white">Health Score</h3>
          </div>
        </div>
        <div className="flex flex-col items-center py-8 text-center">
          <div
            className="mb-3 flex items-center justify-center rounded-full"
            style={{ width: 56, height: 56, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)" }}
          >
            <span className="text-2xl font-bold text-rose-400">—</span>
          </div>
          <p className="text-xs text-amber-100/80 max-w-[180px]">Could not load your health score.</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-4 inline-flex items-center gap-2 rounded-xl border border-amber-400/35 bg-amber-500/10 px-4 py-2 text-xs font-semibold text-amber-50 hover:bg-amber-500/20 transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              Try Again
            </button>
          )}
        </div>
        <div className="mt-4 space-y-3 border-t border-white/[0.06] pt-4">
          {breakdowns.map(({ label, max, delay }, i) => (
            <Breakdown key={label} label={label} value={null} max={max} delayMs={i * 200} />
          ))}
        </div>
      </GlassCard>
    );
  }

  // ── Loading state ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <GlassCard padding="md" surface="panel" className="border-white/[0.08]">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-violet-300/70">Financial Health</p>
            <h3 className="font-heading text-base font-semibold text-white">Health Score</h3>
          </div>
          <span className="h-6 w-20 animate-pulse rounded-full bg-white/[0.06]" />
        </div>
        <GaugeSkeleton />
      </GlassCard>
    );
  }

  // ── Hero variant (used on Dashboard hero) ───────────────────────────────
  if (variant === "hero") {
    return (
      <GlassCard padding="md" surface="panel" className="relative overflow-hidden border-white/[0.1]">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="font-heading text-sm font-semibold text-white sm:text-base">Financial health</h3>
          <TrendBadge trend={trend} />
        </div>
        <SvgGauge displayScore={displayScore} score={targetScore} grade={grade} reduce={reduce} />
        {narration && (
          <p className="mt-2 text-center text-sm leading-relaxed text-white/70 line-clamp-4">{narration}</p>
        )}
      </GlassCard>
    );
  }

  // ── Default variant ──────────────────────────────────────────────────────
  return (
    <GlassCard padding="md" surface="panel" className="border-white/[0.08]">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-violet-300/70">Financial Health</p>
          <h3 className="font-heading text-base font-semibold text-white">Health Score</h3>
        </div>
        {/* STABLE / IMPROVING / DECLINING badge */}
        <TrendBadge trend={trend} />
      </div>

      {/* SVG Gauge */}
      <SvgGauge displayScore={displayScore} score={targetScore} grade={grade} reduce={reduce} />

      {/* Sub-score bars */}
      <div className="mt-5 space-y-3 border-t border-white/[0.06] pt-4">
        {breakdowns.map(({ label, value, max, delay }) => (
          <Breakdown key={label} label={label} value={value} max={max} delayMs={delay} />
        ))}
      </div>
    </GlassCard>
  );
};

export default HealthScoreGauge;
