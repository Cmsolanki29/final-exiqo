/**
 * BehaviorProfile — Phase 2 (Feature Store) deep-dive.
 * Shows: risk score, login patterns, location analysis,
 * anomaly detection, and recent activity timeline.
 * Gracefully degrades when endpoint is unavailable.
 */

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft, Activity, MapPin, Clock, AlertTriangle,
  ShieldCheck, User, Globe,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { getBehaviorProfile } from "../../services/riskApi";
import { RiskStatePlaceholder } from "../../components/risk/RiskStatePlaceholder";
import { fmtRelativeTime } from "../../utils/risk/formatters";
import { riskTheme } from "../../utils/risk/riskTheme";

// ── Demo data shown when endpoint is not yet available ────────────────────
const DEMO = {
  risk_score: 0.12,
  risk_action: "allow",
  login_patterns: [
    { hour: "00", count: 0 }, { hour: "01", count: 0 }, { hour: "02", count: 0 },
    { hour: "03", count: 0 }, { hour: "04", count: 0 }, { hour: "05", count: 1 },
    { hour: "06", count: 3 }, { hour: "07", count: 8 }, { hour: "08", count: 14 },
    { hour: "09", count: 22 }, { hour: "10", count: 18 }, { hour: "11", count: 15 },
    { hour: "12", count: 12 }, { hour: "13", count: 16 }, { hour: "14", count: 20 },
    { hour: "15", count: 19 }, { hour: "16", count: 17 }, { hour: "17", count: 14 },
    { hour: "18", count: 10 }, { hour: "19", count: 8 }, { hour: "20", count: 5 },
    { hour: "21", count: 3 }, { hour: "22", count: 1 }, { hour: "23", count: 0 },
  ],
  locations: [
    { city: "Mumbai",    country: "IN", count: 142, risk: "low",    last_seen: new Date(Date.now() - 3600_000) },
    { city: "Pune",      country: "IN", count: 28,  risk: "low",    last_seen: new Date(Date.now() - 86400_000) },
    { city: "Bangalore", country: "IN", count: 4,   risk: "medium", last_seen: new Date(Date.now() - 259200_000) },
    { city: "Singapore", country: "SG", count: 1,   risk: "high",   last_seen: new Date(Date.now() - 604800_000) },
  ],
  anomalies: [
    { id: 1, type: "unusual_hour",    description: "Login at 3:47 AM",            severity: "medium", ts: new Date(Date.now() - 172800_000) },
    { id: 2, type: "new_location",    description: "Transaction from Singapore",   severity: "high",   ts: new Date(Date.now() - 604800_000) },
    { id: 3, type: "velocity_spike",  description: "4 transactions in 2 minutes",  severity: "medium", ts: new Date(Date.now() - 864000_000) },
  ],
  recent_activity: [
    { id: 1, action: "Login",              channel: "Mobile App",  ts: new Date(Date.now() - 3600_000),   ok: true },
    { id: 2, action: "Transaction ₹1,200", channel: "UPI",         ts: new Date(Date.now() - 7200_000),   ok: true },
    { id: 3, action: "OTP Verified",       channel: "SMS",         ts: new Date(Date.now() - 7500_000),   ok: true },
    { id: 4, action: "Transaction ₹450",   channel: "Card",        ts: new Date(Date.now() - 86400_000),  ok: true },
    { id: 5, action: "Password Change",    channel: "Web",         ts: new Date(Date.now() - 172800_000), ok: true },
    { id: 6, action: "Login",              channel: "New device",  ts: new Date(Date.now() - 172900_000), ok: false },
    { id: 7, action: "Transaction ₹8,500", channel: "NEFT",        ts: new Date(Date.now() - 259200_000), ok: true },
    { id: 8, action: "Login",              channel: "Mobile App",  ts: new Date(Date.now() - 345600_000), ok: true },
  ],
};

// ── Sub-components ─────────────────────────────────────────────────────────

function RiskScoreCard({ score, action }) {
  const theme = riskTheme(action);
  const pct   = Math.round((score ?? 0) * 100);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Behavioral Risk Score</h3>
      <div className="flex items-center gap-5">
        {/* Circular score */}
        <div className="relative w-24 h-24 shrink-0">
          <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
            <circle cx="40" cy="40" r="32" fill="none" stroke="#f3f4f6" strokeWidth="10" />
            <motion.circle
              cx="40" cy="40" r="32"
              fill="none"
              stroke={theme.color}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 32}`}
              initial={{ strokeDashoffset: 2 * Math.PI * 32 }}
              animate={{ strokeDashoffset: 2 * Math.PI * 32 * (1 - (score ?? 0)) }}
              transition={{ duration: 1, ease: "easeOut" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold" style={{ color: theme.color }}>{pct}</span>
            <span className="text-[9px] text-gray-400 -mt-0.5">/ 100</span>
          </div>
        </div>

        <div className="flex-1 space-y-2">
          <span
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold"
            style={{ background: theme.bg, color: theme.color }}
          >
            <ShieldCheck size={14} />
            {theme.label}
          </span>
          <p className="text-xs text-gray-400 leading-relaxed">
            {pct < 30
              ? "Low risk — normal behavioral patterns detected."
              : pct < 60
              ? "Moderate risk — some unusual patterns observed."
              : "Elevated risk — multiple anomalies detected, review recommended."}
          </p>
        </div>
      </div>
    </div>
  );
}

function LoginPatternsChart({ data }) {
  const peak = Math.max(...data.map((d) => d.count));
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-1">Login Patterns — Hourly</h3>
      <p className="text-xs text-gray-400 mb-4">Activity frequency by hour of day</p>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
          <XAxis
            dataKey="hour"
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={false}
            interval={2}
          />
          <YAxis hide />
          <Tooltip
            contentStyle={{ fontSize: 11, borderRadius: 8, border: "1px solid #f3f4f6" }}
            formatter={(v) => [`${v} logins`, "Count"]}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.hour}
                fill={entry.count === peak ? "#7c3aed" : entry.count > peak * 0.5 ? "#a78bfa" : "#e5e7eb"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const RISK_COLOR = { low: "#10b981", medium: "#f59e0b", high: "#ef4444" };
const RISK_BG    = { low: "#ecfdf5", medium: "#fffbeb", high: "#fef2f2" };

function LocationRow({ loc, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className="flex items-center gap-3 py-2.5 border-b border-gray-50 last:border-0"
    >
      <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
        <Globe size={15} className="text-blue-500" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">{loc.city}, {loc.country}</p>
        <p className="text-xs text-gray-400">{loc.count} sessions · last {fmtRelativeTime(loc.last_seen)}</p>
      </div>
      <span
        className="text-[11px] px-2 py-0.5 rounded-full font-medium shrink-0"
        style={{ background: RISK_BG[loc.risk], color: RISK_COLOR[loc.risk] }}
      >
        {loc.risk}
      </span>
    </motion.div>
  );
}

const SEV_META = {
  high:   { color: "#ef4444", bg: "#fef2f2", label: "High" },
  medium: { color: "#f59e0b", bg: "#fffbeb", label: "Medium" },
  low:    { color: "#10b981", bg: "#ecfdf5", label: "Low" },
};

function AnomalyRow({ anomaly, index }) {
  const sev = SEV_META[anomaly.severity] || SEV_META.low;
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0"
    >
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
        style={{ background: sev.bg }}
      >
        <AlertTriangle size={14} style={{ color: sev.color }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">{anomaly.description}</p>
        <p className="text-xs text-gray-400">{fmtRelativeTime(anomaly.ts)}</p>
      </div>
      <span
        className="text-[11px] px-2 py-0.5 rounded-full font-medium shrink-0"
        style={{ background: sev.bg, color: sev.color }}
      >
        {sev.label}
      </span>
    </motion.div>
  );
}

function ActivityRow({ item, index }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.04 }}
      className="flex items-center gap-3 py-2"
    >
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
          item.ok ? "bg-green-50" : "bg-red-50"
        }`}
      >
        {item.ok ? (
          <Activity size={13} className="text-green-500" />
        ) : (
          <AlertTriangle size={13} className="text-red-400" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-medium ${item.ok ? "text-gray-700" : "text-red-600"}`}>
          {item.action}
        </p>
        <p className="text-[10px] text-gray-400">{item.channel}</p>
      </div>
      <span className="text-[10px] text-gray-300 shrink-0">{fmtRelativeTime(item.ts)}</span>
    </motion.div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

const BehaviorProfile = ({ userId = 1, onNavigate }) => {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [, setError]          = useState(null);
  const [usingDemo, setUsingDemo] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getBehaviorProfile(userId)
      .then((res) => {
        if (!cancelled) { setData(res); setLoading(false); }
      })
      .catch(() => {
        if (!cancelled) {
          setData(DEMO);
          setUsingDemo(true);
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [userId]);

  const d = data ?? DEMO;

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-8">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between"
      >
        <div>
          <div className="flex items-center gap-2 mb-1">
            {onNavigate && (
              <button
                type="button"
                onClick={() => onNavigate("trust-center")}
                className="p-1 rounded-lg hover:bg-white/10 transition text-exiqo-glow/50 hover:text-exiqo-glow"
              >
                <ArrowLeft size={16} />
              </button>
            )}
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <User size={22} className="text-purple-400" />
              Behavior Profile
            </h2>
          </div>
          <p className="text-exiqo-glow/60 text-sm mt-1 ml-8">
            Phase 2 — Feature store · 200+ behavioural signals
          </p>
        </div>
      </motion.div>

      {/* Demo data banner */}
      {usingDemo && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 text-xs"
        >
          <AlertTriangle size={14} />
          Showing demo data — behavior-profile endpoint not yet available on this backend.
        </motion.div>
      )}

      {loading ? (
        <RiskStatePlaceholder loading />
      ) : (
        <>
          {/* Risk score */}
          <RiskScoreCard score={d.risk_score} action={d.risk_action} />

          {/* Login patterns chart */}
          {d.login_patterns?.length > 0 && (
            <LoginPatternsChart data={d.login_patterns} />
          )}

          {/* Locations + Anomalies side-by-side on wide */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Location analysis */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-2 mb-3">
                <MapPin size={15} className="text-blue-500" />
                <h3 className="text-sm font-semibold text-gray-700">Location Analysis</h3>
              </div>
              {d.locations?.length ? (
                d.locations.map((loc, i) => <LocationRow key={loc.city} loc={loc} index={i} />)
              ) : (
                <RiskStatePlaceholder empty message="No location data" compact />
              )}
            </div>

            {/* Anomaly detection */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={15} className="text-orange-400" />
                <h3 className="text-sm font-semibold text-gray-700">Detected Anomalies</h3>
              </div>
              {d.anomalies?.length ? (
                d.anomalies.map((a, i) => <AnomalyRow key={a.id} anomaly={a} index={i} />)
              ) : (
                <RiskStatePlaceholder empty message="No anomalies detected" compact />
              )}
            </div>
          </div>

          {/* Recent activity timeline */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-3">
              <Clock size={15} className="text-indigo-500" />
              <h3 className="text-sm font-semibold text-gray-700">Recent Activity Timeline</h3>
            </div>
            <div className="divide-y divide-gray-50">
              {(d.recent_activity ?? []).slice(0, 10).map((item, i) => (
                <ActivityRow key={item.id} item={item} index={i} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default BehaviorProfile;
