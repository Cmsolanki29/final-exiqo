import React, { useState } from "react";
import { postFraudShieldAlertAction, postFraudShieldCheckTransaction } from "../../services/api";
import { useToast } from "../common/Toast";
import { SkeletonCard } from "../common/SkeletonCard";

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
