/**
 * DeviceTrust — Phase 6 (Graph Intelligence / Device fingerprint) deep-dive.
 * Shows: device list with trust scores, risk flags, new device alerts.
 * Gracefully degrades when endpoint is unavailable.
 */

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft, Smartphone, Monitor, Tablet, Wifi, AlertTriangle,
  ShieldCheck, ShieldOff, Clock, Fingerprint,
} from "lucide-react";
import { RiskStatePlaceholder } from "../../components/risk/RiskStatePlaceholder";
import { fmtRelativeTime } from "../../utils/risk/formatters";
import { getDevices } from "../../services/riskApi";

// ── Demo data shown when endpoint is unavailable ───────────────────────────
const DEMO_DEVICES = [
  {
    id: "d1",
    name: "iPhone 15 Pro",
    type: "mobile",
    os: "iOS 17.4",
    browser: "Safari",
    trust_score: 0.96,
    status: "trusted",
    last_seen: new Date(Date.now() - 3600_000),
    first_seen: new Date(Date.now() - 90 * 86400_000),
    location: "Mumbai, IN",
    risk_flags: [],
  },
  {
    id: "d2",
    name: "MacBook Pro",
    type: "desktop",
    os: "macOS 14.4",
    browser: "Chrome 123",
    trust_score: 0.88,
    status: "trusted",
    last_seen: new Date(Date.now() - 86400_000),
    first_seen: new Date(Date.now() - 180 * 86400_000),
    location: "Mumbai, IN",
    risk_flags: [],
  },
  {
    id: "d3",
    name: "Samsung Galaxy S23",
    type: "mobile",
    os: "Android 14",
    browser: "Chrome Mobile",
    trust_score: 0.61,
    status: "review",
    last_seen: new Date(Date.now() - 7 * 86400_000),
    first_seen: new Date(Date.now() - 14 * 86400_000),
    location: "Bangalore, IN",
    risk_flags: ["new_location", "infrequent_use"],
  },
  {
    id: "d4",
    name: "Unknown Device",
    type: "desktop",
    os: "Windows 11",
    browser: "Firefox 124",
    trust_score: 0.22,
    status: "alert",
    last_seen: new Date(Date.now() - 8 * 86400_000),
    first_seen: new Date(Date.now() - 8 * 86400_000),
    location: "Singapore, SG",
    risk_flags: ["new_location", "new_device", "unusual_hour"],
  },
];

// ── Helpers ────────────────────────────────────────────────────────────────

function DeviceIcon({ type }) {
  const cls = "w-full h-full";
  if (type === "mobile")  return <Smartphone className={cls} />;
  if (type === "tablet")  return <Tablet className={cls} />;
  return <Monitor className={cls} />;
}

const STATUS_META = {
  trusted: { color: "#10b981", bg: "#ecfdf5", border: "#6ee7b7", icon: ShieldCheck, label: "Trusted" },
  review:  { color: "#f59e0b", bg: "#fffbeb", border: "#fcd34d", icon: AlertTriangle, label: "Review" },
  alert:   { color: "#ef4444", bg: "#fef2f2", border: "#fca5a5", icon: ShieldOff,     label: "Alert"  },
};

const FLAG_LABELS = {
  new_location:    "New location",
  new_device:      "First seen",
  unusual_hour:    "Unusual hour",
  infrequent_use:  "Infrequent",
  high_velocity:   "High velocity",
  vpn_detected:    "VPN detected",
};

function TrustBar({ score }) {
  const pct   = Math.round(score * 100);
  const color = score >= 0.8 ? "#10b981" : score >= 0.5 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-semibold w-8 text-right" style={{ color }}>
        {pct}
      </span>
    </div>
  );
}

function DeviceCard({ device, index }) {
  const meta    = STATUS_META[device.status] || STATUS_META.trusted;
  const StatusIcon = meta.icon;
  const isAlert = device.status === "alert";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.07 }}
      className={`rounded-2xl border p-5 ${
        isAlert
          ? "bg-red-50 border-red-200"
          : "bg-white border-gray-100 shadow-sm"
      }`}
    >
      {/* New device alert banner */}
      {isAlert && (
        <div className="flex items-center gap-1.5 text-xs text-red-600 font-semibold mb-3">
          <AlertTriangle size={13} />
          Unrecognized device — activity flagged for review
        </div>
      )}

      <div className="flex items-start gap-3">
        {/* Device icon */}
        <div
          className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0 p-2.5"
          style={{ background: meta.bg }}
        >
          <div style={{ color: meta.color }}>
            <DeviceIcon type={device.type} />
          </div>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold text-sm text-gray-900">{device.name}</p>
            <span
              className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-medium border"
              style={{ background: meta.bg, color: meta.color, borderColor: meta.border }}
            >
              <StatusIcon size={10} />
              {meta.label}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            {device.os} · {device.browser}
          </p>
          <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
            <Clock size={10} />
            Last seen {fmtRelativeTime(device.last_seen)} · {device.location}
          </p>

          {/* Trust score bar */}
          <div className="mt-3">
            <p className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">Trust Score</p>
            <TrustBar score={device.trust_score} />
          </div>

          {/* Risk flags */}
          {device.risk_flags?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {device.risk_flags.map((flag) => (
                <span
                  key={flag}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-orange-50 text-orange-500 border border-orange-100 font-medium"
                >
                  {FLAG_LABELS[flag] || flag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* First seen */}
        <div className="text-right shrink-0">
          <p className="text-[10px] text-gray-400">First seen</p>
          <p className="text-xs text-gray-500">{fmtRelativeTime(device.first_seen)}</p>
        </div>
      </div>
    </motion.div>
  );
}

// ── Summary stats ──────────────────────────────────────────────────────────

function SummaryStats({ devices }) {
  const trusted = devices.filter((d) => d.status === "trusted").length;
  const alerts  = devices.filter((d) => d.status === "alert").length;
  const avg     = devices.length
    ? devices.reduce((s, d) => s + d.trust_score, 0) / devices.length
    : 0;

  return (
    <div className="grid grid-cols-3 gap-3">
      {[
        { label: "Trusted Devices", value: trusted,           color: "#10b981" },
        { label: "Alerts",          value: alerts,            color: alerts ? "#ef4444" : "#10b981" },
        { label: "Avg Trust Score", value: `${Math.round(avg * 100)}`, color: avg >= 0.8 ? "#10b981" : "#f59e0b" },
      ].map(({ label, value, color }) => (
        <div key={label} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm text-center">
          <p className="text-2xl font-bold" style={{ color }}>{value}</p>
          <p className="text-xs text-gray-400 mt-0.5">{label}</p>
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

const DeviceTrust = ({ userId = 1, onNavigate }) => {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [, setError]          = useState(null);
  const [usingDemo, setUsingDemo] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getDevices(userId)
      .then((res) => {
        if (!cancelled) {
          const devs = res?.devices ?? (Array.isArray(res) ? res : []);
          if (Array.isArray(devs) && devs.length > 0) {
            setDevices(devs);
          } else {
            setDevices(DEMO_DEVICES);
            setUsingDemo(true);
          }
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDevices(DEMO_DEVICES);
          setUsingDemo(true);
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [userId]);

  const alertDevices = devices.filter((d) => d.status === "alert");
  const otherDevices = devices.filter((d) => d.status !== "alert");

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
              <Fingerprint size={22} className="text-pink-400" />
              Device Trust
            </h2>
          </div>
          <p className="text-exiqo-glow/60 text-sm mt-1 ml-8">
            Phase 6 — Graph intelligence · device fingerprinting &amp; fraud ring detection
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
          Showing demo data — connect a bank account and make transactions to see real device data.
        </motion.div>
      )}

      {loading ? (
        <RiskStatePlaceholder loading />
      ) : (
        <>
          {/* Summary stats */}
          <SummaryStats devices={devices} />

          {/* New device alerts — highlighted section */}
          {alertDevices.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider opacity-60 flex items-center gap-2">
                <AlertTriangle size={14} className="text-red-400" />
                New Device Alerts ({alertDevices.length})
              </h3>
              <div className="space-y-3">
                {alertDevices.map((d, i) => (
                  <DeviceCard key={d.id} device={d} index={i} />
                ))}
              </div>
            </div>
          )}

          {/* Trusted / review devices */}
          <div>
            <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider opacity-60 flex items-center gap-2">
              <Wifi size={14} className="text-green-400" />
              Known Devices ({otherDevices.length})
            </h3>
            <div className="space-y-3">
              {otherDevices.map((d, i) => (
                <DeviceCard key={d.id} device={d} index={i} />
              ))}
            </div>
          </div>

          {devices.length === 0 && (
            <RiskStatePlaceholder empty message="No devices registered yet" />
          )}
        </>
      )}
    </div>
  );
};

export default DeviceTrust;
