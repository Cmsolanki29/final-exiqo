/**
 * RiskChallengeModal — slide-up modal that shows the full SHAP explanation
 * and the "Report as Fraud" action for a selected transaction.
 *
 * Props:
 *   txnId       {string|number|null}  — null = closed
 *   onClose     {() => void}
 *   onReport    {(txnId) => Promise<void>}   optional override
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, BarChart2, ShieldOff, CheckCircle, Loader2, AlertCircle,
} from "lucide-react";
import { ShapExplanationBars } from "./ShapExplanationBars";
import { RiskScoreChip } from "./RiskScoreChip";
import { useExplanation } from "../../hooks/risk/useExplanation";
import { reportFraud } from "../../services/riskApi";
import { fmtCurrency } from "../../utils/risk/formatters";

export function RiskChallengeModal({ txnId, txnMeta = {}, onClose, onReport }) {
  const { data, loading, error } = useExplanation(txnId);
  const [reporting, setReporting]   = useState(false);
  const [reported, setReported]     = useState(false);
  const [reportErr, setReportErr]   = useState(null);

  const isOpen = txnId != null;

  const handleReport = async () => {
    setReporting(true);
    setReportErr(null);
    try {
      if (onReport) {
        await onReport(txnId);
      } else {
        await reportFraud(txnId);
      }
      setReported(true);
    } catch (e) {
      setReportErr(e?.response?.data?.detail || e?.message || "Report failed");
    } finally {
      setReporting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
          />

          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ y: "100%", opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: "100%", opacity: 0 }}
            transition={{ type: "spring", stiffness: 340, damping: 38 }}
            className="fixed bottom-0 left-0 right-0 z-50 mx-auto max-w-xl rounded-t-2xl bg-white shadow-2xl"
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 rounded-full bg-gray-200" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-5 pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <BarChart2 size={18} className="text-indigo-500" />
                <div>
                  <h3 className="font-semibold text-gray-900 text-sm">
                    AI Explanation — Phase 7 SHAP
                  </h3>
                  {txnMeta.merchant && (
                    <p className="text-xs text-gray-400">
                      {txnMeta.merchant}
                      {txnMeta.amount ? ` · ${fmtCurrency(txnMeta.amount)}` : ""}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {data?.risk_action && (
                  <RiskScoreChip
                    txnId={txnId}
                    action={data.risk_action}
                    score={data.predicted_risk_score}
                  />
                )}
                <button
                  type="button"
                  onClick={onClose}
                  className="p-1 rounded-lg hover:bg-gray-100 transition"
                  aria-label="Close"
                >
                  <X size={18} className="text-gray-400" />
                </button>
              </div>
            </div>

            {/* Natural language summary */}
            {data?.natural_language && (
              <div className="mx-5 mt-3 px-3 py-2 rounded-lg bg-indigo-50 text-xs text-indigo-700 leading-relaxed">
                {data.natural_language}
              </div>
            )}

            {/* SHAP bars */}
            <div className="px-5 py-4">
              <ShapExplanationBars
                features={data?.features}
                loading={loading}
                error={error}
              />
            </div>

            {/* Report action */}
            <div className="px-5 pb-5">
              {reported ? (
                <div className="flex items-center gap-2 text-green-600 text-sm font-medium bg-green-50 px-4 py-3 rounded-xl">
                  <CheckCircle size={16} />
                  Reported — our team will review this transaction.
                </div>
              ) : (
                <>
                  {reportErr && (
                    <div className="flex items-center gap-2 text-red-500 text-xs mb-2">
                      <AlertCircle size={13} />
                      {reportErr}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={handleReport}
                    disabled={reporting}
                    className="flex w-full items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold text-white
                               bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700
                               disabled:opacity-60 transition"
                  >
                    {reporting ? (
                      <Loader2 size={15} className="animate-spin" />
                    ) : (
                      <ShieldOff size={15} />
                    )}
                    {reporting ? "Reporting…" : "Report as Fraud (Phase 8 Flywheel)"}
                  </button>
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
