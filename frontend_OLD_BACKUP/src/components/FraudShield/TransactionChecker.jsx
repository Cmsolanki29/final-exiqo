import React, { useState } from "react";
import { postFraudShieldAlertAction, postFraudShieldCheckTransaction } from "../../services/api";
import { useToast } from "../common/Toast";
import { SkeletonCard } from "../common/SkeletonCard";

// ── Three-model comparison panel ──────────────────────────────────────────
function DecisionBadge({ decision }) {
  if (decision === "ALLOW") return <span className="text-green-600 font-bold">ALLOW ✅</span>;
  if (decision === "FLAG")  return <span className="text-amber-600 font-bold">FLAG ⚠️</span>;
  if (decision === "BLOCK") return <span className="text-red-600 font-bold">BLOCK 🛑</span>;
  return <span className="text-gray-400">{decision}</span>;
}

function ModelCol({ title, decision, score, reason, tier, tierLabel, conflict, conflictNote }) {
  const borderColor = decision === "ALLOW" ? "#22c55e" : decision === "BLOCK" ? "#ef4444" : "#f59e0b";
  return (
    <div
      className="flex-1 min-w-0 rounded-xl border p-3 space-y-1.5"
      style={{ borderColor: `${borderColor}40`, background: `${borderColor}08` }}
    >
      <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{title}</p>
      <div className="text-base"><DecisionBadge decision={decision} /></div>
      {score != null && (
        <p className="text-xs text-gray-500">Score: <span className="font-mono font-semibold text-gray-700">{Number(score).toFixed(2)}</span></p>
      )}
      {tierLabel && <p className="text-xs text-gray-500">{tierLabel}</p>}
      {reason && <p className="text-[11px] text-gray-400 leading-snug">{reason}</p>}
      {conflict && conflictNote && (
        <p className="text-[10px] text-amber-600 font-semibold mt-1 bg-amber-50 px-1.5 py-0.5 rounded">
          ⚡ {conflictNote}
        </p>
      )}
    </div>
  );
}

function ModelComparisonPanel({ comparison }) {
  if (!comparison) return null;
  const { xgboost, gnn, orchestrator } = comparison;
  const hasConflict = orchestrator?.conflict;
  return (
    <div className="mt-4 space-y-2">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
        AI Model Comparison
      </p>
      {hasConflict && (
        <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          <span className="text-amber-600 text-sm font-semibold">
            ⚡ CONFLICT — Orchestrator adjudicated
          </span>
        </div>
      )}
      <div className="flex gap-2 flex-wrap">
        <ModelCol
          title="XGBoost"
          decision={xgboost?.decision}
          score={xgboost?.score}
          reason={xgboost?.reason}
        />
        <ModelCol
          title="GNN"
          decision={gnn?.decision}
          score={gnn?.score}
          reason={gnn?.reason}
          conflict={hasConflict}
          conflictNote={orchestrator?.conflict_note}
        />
        <ModelCol
          title="Orchestrator Final"
          decision={orchestrator?.decision}
          tierLabel={orchestrator?.tier_label}
          reason={orchestrator?.reason}
        />
      </div>
    </div>
  );
}

const nowTime = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

const patternLabel = (p) => {
  if (!p) return "—";
  return p.replace(/_/g, " ");
};

const TransactionChecker = ({ userId, userName, onReportSuccess }) => {
  const { showToast } = useToast();
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [time, setTime] = useState(nowTime());
  const [description, setDescription] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("UPI");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [reportMsg, setReportMsg] = useState("");
  const [reporting, setReporting] = useState(false);

  const runCheck = async (body) => {
    setLoading(true);
    setResult(null);
    setReportMsg("");
    try {
      const data = await postFraudShieldCheckTransaction(userId, body);
      setResult(data);
    } catch (e) {
      setResult({
        error: true,
        warning_message: e.message || "Check failed",
        risk_score: 0,
        risk_level: "LOW",
      });
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    const amt = parseFloat(amount);
    if (!merchant.trim() || Number.isNaN(amt)) return;
    runCheck({
      merchant: merchant.trim(),
      amount: amt,
      transaction_time: time || undefined,
      description: description.trim() || undefined,
      payment_method: paymentMethod,
    });
  };

  const fillKyc = () => {
    setMerchant("sbi-kyc-update@ybl");
    setAmount("15000");
    setTime("23:30");
    setDescription("");
    setPaymentMethod("UPI");
  };

  const fillLottery = () => {
    setMerchant("prize-claim-2025@upi");
    setAmount("2000");
    setTime("15:00");
    setDescription("Lottery processing fee");
    setPaymentMethod("UPI");
  };

  const fillNormal = () => {
    setMerchant("swiggy@ybl");
    setAmount("250");
    setTime("14:00");
    setDescription("Lunch order");
    setPaymentMethod("UPI");
  };

  const fillRupeeTrap = () => {
    setMerchant("verify-upi-axis@okaxis");
    setAmount("1");
    setTime("23:45");
    setDescription("UPI verify");
    setPaymentMethod("UPI");
  };

  const fillCollect = () => {
    setMerchant("refund-amazon@okaxis");
    setAmount("3499");
    setTime("12:00");
    setDescription("UPI collect request — refund");
    setPaymentMethod("UPI Collect");
  };

  const handleReport = async () => {
    setReporting(true);
    setReportMsg("");
    try {
      if (result?.alert_id) {
        const res = await postFraudShieldAlertAction(userId, result.alert_id, "REPORTED");
        setReportMsg(res.message || "Fraud reported successfully!");
        showToast("Fraud reported — follow up on National Cyber Crime Portal ✅");
        if (onReportSuccess) onReportSuccess();
      } else {
        setReportMsg(
          `Fraud reported — file details on ${result?.cybercrime_url || "https://cybercrime.gov.in"} (Helpline 1930).`
        );
        showToast("Fraud reported — file details on National Cyber Crime Portal ✅");
      }
    } catch (e) {
      setReportMsg(e.message || "Could not update alert");
    } finally {
      setReporting(false);
    }
  };

  const score = result?.risk_score ?? 0;
  const level = result?.risk_level || "LOW";
  const isCritical = score >= 85 || level === "CRITICAL";
  const isHigh = !isCritical && score >= 60;
  const isMedium = !isCritical && !isHigh && score >= 30;
  const isLow = score < 30;
  const securityBrief = (result?.ai_security_message || result?.hinglish_warning || "").trim();

  return (
    <div className="fraud-checker glass-card">
      <div className="fraud-checker-head">
        <h3>🔍 Real-Time Transaction Safety Checker</h3>
        <p className="muted">Check before you send — takes about 2 seconds</p>
      </div>

      <form className="fraud-checker-form" onSubmit={onSubmit}>
        <label className="fraud-field">
          <span>Merchant / UPI ID</span>
          <input
            value={merchant}
            onChange={(e) => setMerchant(e.target.value)}
            placeholder="e.g. merchant@upi"
            autoComplete="off"
          />
        </label>
        <label className="fraud-field">
          <span>Amount (₹)</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0"
          />
        </label>
        <label className="fraud-field">
          <span>Time (HH:MM)</span>
          <input value={time} onChange={(e) => setTime(e.target.value)} placeholder="23:30" />
        </label>
        <label className="fraud-field">
          <span>Payment method</span>
          <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
            <option value="UPI">UPI</option>
            <option value="UPI Collect">UPI Collect</option>
            <option value="IMPS">IMPS</option>
          </select>
        </label>
        <label className="fraud-field fraud-field-wide">
          <span>Description (optional)</span>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Note / remark"
          />
        </label>

        <div className="fraud-quick-tests">
          <span className="muted small">Quick test:</span>
          <button type="button" className="btn-fraud-test danger" onClick={fillKyc}>
            🔴 Test KYC Fraud
          </button>
          <button type="button" className="btn-fraud-test danger" onClick={fillLottery}>
            🔴 Test Lottery
          </button>
          <button type="button" className="btn-fraud-test warn" onClick={fillCollect}>
            🔴 Test UPI Collect
          </button>
          <button type="button" className="btn-fraud-test ok" onClick={fillNormal}>
            🟡 Test Normal
          </button>
          <button type="button" className="btn-fraud-test danger" onClick={fillRupeeTrap}>
            🔴 Test ₹1 Trap
          </button>
        </div>

        <div className="fraud-checker-actions">
          <button type="submit" className="btn-primary fraud-check-btn" disabled={loading}>
            {loading ? "🤖 AI analyzing transaction…" : "🔍 Check Safety"}
          </button>
        </div>
      </form>

      {loading && (
        <div className="fraud-ai-loading glass-card feature-card">
          <p>🤖 Analyzing transaction…</p>
          <p className="muted small" style={{ marginBottom: 12 }}>
            Running an 8-factor risk model and generating an AI security brief
          </p>
          <SkeletonCard lines={3} height={88} />
        </div>
      )}

      {result && !loading && !result.error && (
        <div
          className={`fraud-result glass-card ${
            isCritical ? "critical" : isHigh ? "high" : isMedium ? "medium" : "safe"
          }`}
        >
          {isCritical && (
            <>
              <h4 className="fraud-result-title">🚨 CRITICAL RISK — {score}/100</h4>
              <div className="fraud-result-divider" />
              <p className="fraud-do-not">❌ DO NOT PROCEED</p>
              {result.pattern_matched && (
                <p>
                  <strong>Pattern detected:</strong> {patternLabel(result.pattern_matched)}
                </p>
              )}
              <div className="fraud-factors">
                <strong>⚠️ Risk factors</strong>
                <ul>
                  {(result.risk_factors || []).map((f, i) => (
                    <li key={i}>🔴 {f}</li>
                  ))}
                </ul>
              </div>
              {securityBrief && (
                <div className="fraud-ai-brief">
                  <strong>🤖 AI security brief</strong>
                  <blockquote>{securityBrief}</blockquote>
                </div>
              )}
              <div className="fraud-result-actions">
                <button type="button" className="btn-outline" onClick={() => setResult(null)}>
                  ❌ Cancel Transaction
                </button>
                <a className="btn-outline" href="tel:1930">
                  📞 Helpline 1930
                </a>
                <button
                  type="button"
                  className="btn-danger"
                  disabled={reporting}
                  onClick={handleReport}
                >
                  🚨 Report Fraud
                </button>
                <button type="button" className="btn-muted" onClick={() => setResult(null)}>
                  ✅ I know it&apos;s safe
                </button>
              </div>
            </>
          )}

          {isHigh && (
            <>
              <h4 className="fraud-result-title">⚠️ HIGH RISK — {score}/100</h4>
              <p>{result.warning_message}</p>
              {result.pattern_matched && (
                <p>
                  <strong>Pattern:</strong> {patternLabel(result.pattern_matched)}
                </p>
              )}
              <ul className="fraud-factors-list">
                {(result.risk_factors || []).slice(0, 8).map((f, i) => (
                  <li key={i}>🔴 {f}</li>
                ))}
              </ul>
              {securityBrief && <blockquote className="fraud-ai-brief-block">{securityBrief}</blockquote>}
              <div className="fraud-result-actions">
                <button type="button" className="btn-primary" onClick={() => setResult(null)}>
                  Verified, Proceed
                </button>
                <button type="button" className="btn-outline" onClick={() => setResult(null)}>
                  Cancel
                </button>
                <button type="button" className="btn-danger" disabled={reporting} onClick={handleReport}>
                  🚨 Report Fraud
                </button>
              </div>
            </>
          )}

          {isMedium && (
            <>
              <h4 className="fraud-result-title">⚠️ CAUTION — {score}/100</h4>
              <p>Proceed carefully — verify recipient.</p>
              {securityBrief && <blockquote className="fraud-ai-brief-block">{securityBrief}</blockquote>}
              <div className="fraud-result-actions">
                <button type="button" className="btn-primary" onClick={() => setResult(null)}>
                  Verified, Proceed
                </button>
                <button type="button" className="btn-outline" onClick={() => setResult(null)}>
                  Cancel
                </button>
              </div>
            </>
          )}

          {isLow && (
            <>
              <h4 className="fraud-result-title">✅ SAFE — Risk Score: {score}/100</h4>
              <p>This transaction looks normal for {userName}.</p>
              <button type="button" className="btn-primary" onClick={() => setResult(null)}>
                Proceed Safely →
              </button>
            </>
          )}

          {/* SHAP-style feature contributions */}
          {Array.isArray(result.feature_scores) && result.feature_scores.filter(f => f.score > 0).length > 0 && (
            <div style={{ marginTop: 12, padding: "10px 14px", background: "rgba(255,255,255,0.03)", borderRadius: 10, border: "1px solid rgba(255,255,255,0.08)" }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
                Feature Contributions (XGBoost)
              </p>
              {result.feature_scores.filter(f => f.score > 0).map((f, i) => {
                const pct = Math.round(f.score * 100);
                const barColor = f.impact === "high" ? "#ef4444" : f.impact === "medium" ? "#f59e0b" : "#22c55e";
                return (
                  <div key={i} style={{ marginBottom: 6 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 2 }}>
                      <span style={{ color: "rgba(255,255,255,0.7)" }}>{f.feature}</span>
                      <span style={{ color: barColor, fontWeight: 600 }}>+{f.score.toFixed(2)}</span>
                    </div>
                    <div style={{ height: 4, borderRadius: 4, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${Math.min(pct * 5, 100)}%`, background: barColor, borderRadius: 4, transition: "width 0.5s ease" }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <ModelComparisonPanel comparison={result.model_comparison} />

          {reportMsg && <p className="fraud-report-ok">{reportMsg}</p>}
          {(isCritical || isHigh) && (
            <p className="muted small fraud-links">
              <a href={result.cybercrime_url || "https://cybercrime.gov.in"} target="_blank" rel="noreferrer">
                National Cyber Crime Reporting Portal
              </a>{" "}
              · Helpline {result.helpline || "1930"}
            </p>
          )}
        </div>
      )}

      {result?.error && (
        <div className="error-card fraud-result">
          <p>{result.warning_message}</p>
        </div>
      )}
    </div>
  );
};

export default TransactionChecker;
