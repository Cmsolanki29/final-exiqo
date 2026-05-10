/**
 * TrustScoreGauge — animated semi-circular gauge for a 0-1000 trust score.
 * Falls back gracefully if score is unavailable.
 */

import React from "react";
import { motion } from "framer-motion";
import { trustScoreBand } from "../../utils/risk/trustScoreBand";

const RADIUS = 80;
const STROKE = 14;
const CIRCUMFERENCE = Math.PI * RADIUS; // half-circle

function ArcPath({ score }) {
  const pct   = Math.min(Math.max(score / 1000, 0), 1);
  const dash  = pct * CIRCUMFERENCE;
  const band  = trustScoreBand(score);
  const cx = 100, cy = 100;

  return (
    <svg width="200" height="110" viewBox="0 0 200 110" className="overflow-visible">
      {/* Track */}
      <path
        d={`M ${cx - RADIUS},${cy} A ${RADIUS},${RADIUS} 0 0 1 ${cx + RADIUS},${cy}`}
        fill="none"
        stroke="#f3f4f6"
        strokeWidth={STROKE}
        strokeLinecap="round"
      />
      {/* Colored arc */}
      <motion.path
        d={`M ${cx - RADIUS},${cy} A ${RADIUS},${RADIUS} 0 0 1 ${cx + RADIUS},${cy}`}
        fill="none"
        stroke={band.color}
        strokeWidth={STROKE}
        strokeLinecap="round"
        strokeDasharray={CIRCUMFERENCE}
        initial={{ strokeDashoffset: CIRCUMFERENCE }}
        animate={{ strokeDashoffset: CIRCUMFERENCE - dash }}
        transition={{ duration: 1.2, ease: "easeOut" }}
      />
      {/* Score text */}
      <text
        x={cx}
        y={cy - 8}
        textAnchor="middle"
        fontSize="28"
        fontWeight="700"
        fill={band.color}
      >
        {score}
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" fontSize="11" fill="#9ca3af">
        / 1000
      </text>
    </svg>
  );
}

export function TrustScoreGauge({ score = null }) {
  const band = score != null ? trustScoreBand(score) : null;

  return (
    <div className="flex flex-col items-center gap-2">
      {score != null ? (
        <>
          <ArcPath score={score} />
          <div className="text-center -mt-2">
            <span
              className="text-sm font-bold px-3 py-1 rounded-full"
              style={{ background: band.bg, color: band.color }}
            >
              {band.grade} — {band.label}
            </span>
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center gap-3 py-6">
          <div className="w-40 h-20 rounded-t-full bg-gray-100 animate-pulse" />
          <span className="text-xs text-gray-400">Trust score coming soon</span>
        </div>
      )}
    </div>
  );
}
