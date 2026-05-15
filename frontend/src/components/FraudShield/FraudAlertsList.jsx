import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldAlert, ShieldCheck, ShieldOff, AlertTriangle,
  ExternalLink, Phone, CheckCircle2, Flag, Lock,
  Clock, IndianRupee, Loader2,
} from "lucide-react";
import { getFraudShieldAlerts, postFraudShieldAlertAction } from "../../services/api";
import { useToast } from "../common/Toast";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";

const fmt = (n) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(n || 0));

const patternTitle = (p) =>
  p ? p.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Fraud Alert";

const SEVERITY = {
  CRITICAL: {
    label: "CRITICAL",
    border: "border-l-red-500",
    badge: "bg-red-500/20 text-red-400 border border-red-500/40",
    glow: "shadow-[0_0_24px_-8px_rgba(239,68,68,0.35)]",
    dot: "bg-red-500",
    icon: ShieldOff,
    iconColor: "text-red-400",
    pulse: true,
  },
  HIGH: {
    label: "HIGH",
    border: "border-l-orange-500",
    badge: "bg-orange-500/20 text-orange-400 border border-orange-500/40",
    glow: "shadow-[0_0_24px_-8px_rgba(249,115,22,0.30)]",
    dot: "bg-orange-500",
    icon: AlertTriangle,
    iconColor: "text-orange-400",
    pulse: true,
  },
  MEDIUM: {
    label: "MEDIUM",
    border: "border-l-yellow-500",
    badge: "bg-yellow-500/20 text-yellow-400 border border-yellow-500/40",
    glow: "shadow-[0_0_20px_-10px_rgba(234,179,8,0.25)]",
    dot: "bg-yellow-500",
    icon: AlertTriangle,
    iconColor: "text-yellow-400",
    pulse: false,
  },
  LOW: {
    label: "LOW",
    border: "border-l-slate-500",
    badge: "bg-slate-500/20 text-slate-400 border border-slate-500/40",
    glow: "",
    dot: "bg-slate-500",
    icon: ShieldAlert,
    iconColor: "text-slate-400",
    pulse: false,
  },
};

const severityFromScore = (s) => {
  if (s >= 85) return SEVERITY.CRITICAL;
  if (s >= 60) return SEVERITY.HIGH;
  if (s >= 30) return SEVERITY.MEDIUM;
  return SEVERITY.LOW;
};

function AlertCard({ alert: a, onAction, acting }) {
  const sev = severityFromScore(a.risk_score);
  const SevIcon = sev.icon;
  const pending = a.user_action === "PENDING";
  const isActing = acting === a.id;

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ type: "spring", stiffness: 360, damping: 28 }}
      className={`relative flex flex-col rounded-2xl border-l-[3px] border border-white/[0.07] bg-gradient-to-br from-white/[0.05] to-white/[0.02] backdrop-blur-sm p-5 ${sev.border} ${sev.glow} transition-shadow duration-300`}
    >
      {/* Severity header row */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-white/[0.06] shrink-0">
            <SevIcon size={15} className={sev.iconColor} />
            {sev.pulse && (
              <span className={`absolute top-0.5 right-0.5 flex h-2 w-2`}>
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-60 ${sev.dot}`} />
                <span className={`relative inline-flex h-2 w-2 rounded-full ${sev.dot}`} />
              </span>
            )}
          </span>
          <span className={`text-[10px] font-bold tracking-widest uppercase px-2.5 py-1 rounded-full ${sev.badge}`}>
            {sev.label}
          </span>
        </div>
        <span className="flex items-center gap-1 text-[10px] text-white/35 font-mono">
          <Clock size={10} />
          {a.created_at
            ? new Date(a.created_at).toLocaleString("en-IN", {
                day: "2-digit", month: "short", year: "numeric",
                hour: "2-digit", minute: "2-digit",
              })
            : "—"}
        </span>
      </div>

      {/* Pattern name */}
      <h4 className="text-sm font-bold text-white tracking-tight leading-snug mb-1">
        {patternTitle(a.pattern_matched)}
      </h4>

      {/* Amount at risk */}
      <div className="flex items-baseline gap-1.5 mb-3">
        <IndianRupee size={14} className="text-white/50 shrink-0 mb-0.5" />
        <span className="text-2xl font-black tabular-nums tracking-tight text-white">
          {fmt(a.amount_at_risk).replace("₹", "")}
        </span>
        <span className="text-[11px] text-white/40 font-medium ml-1">at risk</span>
        {a.money_saved > 0 && (
          <span className="ml-auto text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 px-2 py-0.5 rounded-full">
            +{fmt(a.money_saved)} saved
          </span>
        )}
      </div>

      {/* Explanation */}
      {a.hinglish_explanation && (
        <p className="text-[12px] leading-relaxed text-white/60 italic bg-white/[0.04] border-l-2 border-white/10 px-3 py-2 rounded-r-lg mb-3">
          {a.hinglish_explanation}
        </p>
      )}

      {/* Status */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[11px] font-medium text-white/40 uppercase tracking-wider">Status</span>
        {pending ? (
          <span className="flex items-center gap-1.5 text-[11px] font-bold text-amber-400">
            <AlertTriangle size={11} />
            PENDING — take action
          </span>
        ) : a.user_action === "BLOCKED" ? (
          <span className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400">
            <ShieldCheck size={11} />
            Blocked by FraudShield
          </span>
        ) : a.user_action === "ALLOWED" ? (
          <span className="flex items-center gap-1.5 text-[11px] font-bold text-sky-400">
            <CheckCircle2 size={11} />
            Marked as Safe
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-[11px] font-bold text-violet-400">
            <Flag size={11} />
            Reported
          </span>
        )}
      </div>

      {/* Action buttons */}
      {pending && (
        <div className="grid grid-cols-3 gap-2 mt-auto">
          <button
            type="button"
            disabled={isActing}
            onClick={() => onAction(a.id, "ALLOWED")}
            className="flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/20 hover:border-emerald-400/50 disabled:opacity-50 transition-all duration-200 group"
          >
            {isActing ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <CheckCircle2 size={14} className="group-hover:scale-110 transition-transform" />
            )}
            <span className="text-[10px] font-semibold leading-none">It was safe</span>
          </button>

          <button
            type="button"
            disabled={isActing}
            onClick={() => onAction(a.id, "REPORTED")}
            className="flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl bg-red-500/15 border border-red-500/35 text-red-400 hover:bg-red-500/25 hover:border-red-400/60 disabled:opacity-50 transition-all duration-200 group shadow-[0_0_16px_-6px_rgba(239,68,68,0.4)]"
          >
            {isActing ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Flag size={14} className="group-hover:scale-110 transition-transform" />
            )}
            <span className="text-[10px] font-semibold leading-none">Report fraud</span>
          </button>

          <button
            type="button"
            disabled={isActing}
            onClick={() => onAction(a.id, "BLOCKED")}
            className="flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl bg-violet-500/15 border border-violet-500/35 text-violet-400 hover:bg-violet-500/25 hover:border-violet-400/60 disabled:opacity-50 transition-all duration-200 group"
          >
            {isActing ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Lock size={14} className="group-hover:scale-110 transition-transform" />
            )}
            <span className="text-[10px] font-semibold leading-none">I blocked it</span>
          </button>
        </div>
      )}
    </motion.article>
  );
}

const FraudAlertsList = ({ userId, onAlertsChanged }) => {
  const { showToast } = useToast();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [acting, setActing] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getFraudShieldAlerts(userId);
      setAlerts(data.alerts || []);
    } catch (e) {
      setError(e.message || "Failed to load alerts");
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [userId]);

  const onAction = async (alertId, action) => {
    setActing(alertId);
    try {
      await postFraudShieldAlertAction(userId, alertId, action);
      await load();
      if (onAlertsChanged) onAlertsChanged();
      if (action === "REPORTED") {
        showToast("Fraud reported — note details on National Cyber Crime Portal ✅", "success");
      }
    } catch (e) {
      setError(e.message || "Action failed");
    } finally {
      setActing(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3 p-1">
        <p className="text-xs text-white/40 mb-3">Loading your fraud alerts…</p>
        <SkeletonCard lines={4} height={160} />
      </div>
    );
  }

  if (error && !alerts.length) {
    return <ErrorCard message={error} onRetry={load} />;
  }

  return (
    <div className="space-y-5">
      {/* Section header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-red-500/15 border border-red-500/30">
            <ShieldAlert size={17} className="text-red-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight leading-none">
              My Fraud Alerts
            </h3>
            <p className="text-[11px] text-white/40 mt-0.5">
              Personal threat feed — FraudShield 12-layer detection
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="https://cybercrime.gov.in"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-[11px] text-violet-400 hover:text-violet-300 transition-colors font-medium"
          >
            <ExternalLink size={11} />
            cybercrime.gov.in
          </a>
          <span className="flex items-center gap-1.5 text-[11px] font-bold text-white/70 bg-white/[0.06] border border-white/10 px-2.5 py-1 rounded-full">
            <Phone size={10} />
            1930
          </span>
        </div>
      </div>

      {/* Alert grid */}
      {!alerts.length ? (
        <div className="flex flex-col items-center gap-3 py-10 rounded-2xl border border-white/[0.06] bg-white/[0.02]">
          <ShieldCheck size={36} className="text-emerald-500/60" />
          <p className="text-sm font-semibold text-white/70">No fraud attempts detected</p>
          <p className="text-xs text-white/35 text-center max-w-xs">
            You're all clear. Run a transaction check anytime for live risk scoring.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <AnimatePresence mode="popLayout">
            {alerts.map((a) => (
              <AlertCard
                key={a.id}
                alert={a}
                onAction={onAction}
                acting={acting}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
};

export default FraudAlertsList;
