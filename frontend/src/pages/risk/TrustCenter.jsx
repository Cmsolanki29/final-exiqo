/**
 * TrustCenter — Phase 1-8 showpiece page.
 * Explains all 8 phases, shows trust score gauge, live engine status,
 * and links to deep-dive sub-pages.
 */

import React from "react";
import { motion } from "framer-motion";
import {
  ShieldCheck, ShieldOff, Zap, ArrowRight, BarChart2, Bell,
  User, Fingerprint, TrendingUp, DollarSign,
} from "lucide-react";
import { TrustScoreGauge } from "../../components/risk/TrustScoreGauge";
import { PhaseCard } from "../../components/risk/PhaseCard";
import { RiskLiveTicker } from "../../components/risk/RiskLiveTicker";
import { useRisk } from "../../contexts/RiskContext";
import { PHASES } from "../../utils/risk/phaseConfig";
import { fmtRelativeTime, fmtCurrency } from "../../utils/risk/formatters";

function EngineStatusBanner({ healthy, lastCheckedAt }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-medium ${
        healthy
          ? "bg-green-50 border-green-200 text-green-700"
          : "bg-gray-50 border-gray-200 text-gray-500"
      }`}
    >
      {healthy ? <ShieldCheck size={18} /> : <ShieldOff size={18} />}
      <span>
        {healthy
          ? "8-Phase Fraud Engine is active and protecting your account"
          : "Risk engine is currently offline — basic protection still active"}
      </span>
      {lastCheckedAt && (
        <span className="ml-auto text-xs opacity-60">
          checked {fmtRelativeTime(lastCheckedAt)}
        </span>
      )}
    </motion.div>
  );
}

function QuickActionCard({ icon: Icon, title, subtitle, color, bg, onClick }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileHover={{ scale: 1.02, y: -2 }}
      whileTap={{ scale: 0.98 }}
      className="flex items-center gap-3 p-4 rounded-2xl border border-gray-100 bg-white shadow-sm hover:shadow-md transition-shadow text-left w-full"
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: bg }}
      >
        <Icon size={20} style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900">{title}</p>
        <p className="text-xs text-gray-400 truncate">{subtitle}</p>
      </div>
      <ArrowRight size={16} className="text-gray-300 shrink-0" />
    </motion.button>
  );
}

const TrustCenter = ({ userId, onNavigate }) => {
  const { healthy, dbConnected, mlReady, version, lastCheckedAt } = useRisk();

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-8">
      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between"
      >
        <div>
          <h2 className="text-2xl font-bold text-white">Trust Center</h2>
          <p className="text-exiqo-glow/60 text-sm mt-1">
            8-phase AI fraud protection — built by Chirag Solanki
          </p>
        </div>
        {version && (
          <span className="text-xs text-exiqo-glow/40 bg-white/5 px-2 py-1 rounded-lg border border-white/10">
            v{version}
          </span>
        )}
      </motion.div>

      {/* Engine status banner */}
      <EngineStatusBanner healthy={healthy} lastCheckedAt={lastCheckedAt} />

      {/* Hero stats — "What we protected this month" */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="rounded-2xl border border-white/10 bg-gradient-to-br from-exiqo-purple/15 via-exiqo-dark/40 to-exiqo-pink/10 p-5 backdrop-blur-sm"
      >
        <p className="text-xs uppercase tracking-wider text-exiqo-glow/60 font-semibold mb-3">
          Protection Summary · This Month
        </p>
        <div className="grid grid-cols-3 gap-3">
          <div className="text-center">
            <div className="flex items-center justify-center gap-1.5 mb-1">
              <ShieldCheck size={14} className="text-green-400" />
              <p className="text-xs text-exiqo-glow/60 uppercase tracking-wide">Threats Blocked</p>
            </div>
            <p className="text-3xl font-bold text-green-400">12</p>
            <p className="text-[10px] text-exiqo-glow/40 mt-0.5">↑ 3 vs last month</p>
          </div>
          <div className="text-center border-x border-white/10">
            <div className="flex items-center justify-center gap-1.5 mb-1">
              <DollarSign size={14} className="text-yellow-400" />
              <p className="text-xs text-exiqo-glow/60 uppercase tracking-wide">Money Saved</p>
            </div>
            <p className="text-3xl font-bold text-yellow-400">{fmtCurrency(48500)}</p>
            <p className="text-[10px] text-exiqo-glow/40 mt-0.5">across 7 fraud attempts</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1.5 mb-1">
              <TrendingUp size={14} className="text-pink-400" />
              <p className="text-xs text-exiqo-glow/60 uppercase tracking-wide">Detection Rate</p>
            </div>
            <p className="text-3xl font-bold text-pink-400">94.7%</p>
            <p className="text-[10px] text-exiqo-glow/40 mt-0.5">XGBoost v3.4.1</p>
          </div>
        </div>
      </motion.div>

      {/* Trust score + engine health side-by-side */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Trust Score Gauge */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col items-center">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Financial Trust Score</h3>
          <TrustScoreGauge score={742} />
          <p className="text-xs text-gray-400 text-center mt-2">
            Based on spending patterns, repayment history, and fraud signals
          </p>
        </div>

        {/* Engine health checklist */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-3">
          <h3 className="text-sm font-semibold text-gray-700">Engine Status</h3>
          {[
            { label: "API Gateway",      ok: true },
            { label: "Database Pool",    ok: dbConnected },
            { label: "ML Models",        ok: mlReady },
            { label: "Redis Event Bus",  ok: healthy },
            { label: "SHAP Explainer",   ok: mlReady },
            { label: "Feedback Queue",   ok: healthy },
          ].map(({ label, ok }) => (
            <div key={label} className="flex items-center gap-2 text-sm">
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${ok ? "bg-green-400" : "bg-gray-300"}`}
              />
              <span className={ok ? "text-gray-700" : "text-gray-400"}>{label}</span>
              <span className={`ml-auto text-xs font-medium ${ok ? "text-green-600" : "text-gray-400"}`}>
                {ok ? "Online" : "Offline"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Live ticker */}
      <div className="bg-white/5 border border-white/10 rounded-2xl p-4">
        <p className="text-xs text-exiqo-glow/40 mb-2 uppercase tracking-wider">
          Live Transaction Feed
        </p>
        <RiskLiveTicker />
      </div>

      {/* Quick actions */}
      <div>
        <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider opacity-60">
          Deep-dive analysis
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <QuickActionCard
            icon={BarChart2}
            title="AI Performance"
            subtitle="Model accuracy, drift, shadow tests"
            color="#6366f1"
            bg="#eef2ff"
            onClick={() => onNavigate?.("ai-performance")}
          />
          <QuickActionCard
            icon={Bell}
            title="Alerts Center"
            subtitle="Review queue · fraud reports"
            color="#f97316"
            bg="#fff7ed"
            onClick={() => onNavigate?.("alerts-center")}
          />
          <QuickActionCard
            icon={User}
            title="Behavior Profile"
            subtitle="Login patterns · locations · anomalies · Phase 2"
            color="#8b5cf6"
            bg="#f5f3ff"
            onClick={() => onNavigate?.("behavior-profile")}
          />
          <QuickActionCard
            icon={Fingerprint}
            title="Device Trust"
            subtitle="Device fingerprinting · fraud ring detection · Phase 6"
            color="#ec4899"
            bg="#fdf2f8"
            onClick={() => onNavigate?.("device-trust")}
          />
          <QuickActionCard
            icon={Zap}
            title="Real-time Events"
            subtitle="Live event bus stats · Phase 1"
            color="#3b82f6"
            bg="#eff6ff"
            onClick={() => onNavigate?.("fraud")}
          />
          <QuickActionCard
            icon={ShieldCheck}
            title="Fraud Shield"
            subtitle="Anomaly detector · full analysis"
            color="#10b981"
            bg="#ecfdf5"
            onClick={() => onNavigate?.("fraud")}
          />
        </div>
      </div>

      {/* Phase cards */}
      <div>
        <h3 className="text-sm font-semibold text-white mb-3 uppercase tracking-wider opacity-60">
          The 8 Phases
        </h3>
        <div className="space-y-2">
          {PHASES.map((phase, i) => (
            <PhaseCard key={phase.id} phase={phase} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
};

export default TrustCenter;
