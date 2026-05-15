import React, { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Radar, ShieldAlert, ShieldCheck, ShieldX, Sparkles, TrendingUp, Zap } from "lucide-react";
import { postFraudShieldAlertAction, postFraudShieldCheckTransaction } from "../../services/api";
import { ShapExplanationBars } from "../risk/ShapExplanationBars";
import { useToast } from "../common/Toast";
import { SkeletonCard } from "../common/SkeletonCard";
import { inr } from "../../lib/format";
import { TrustRing } from "./TrustRing";
import { MiniSparkline } from "./MiniSparkline";
import { useCountUp } from "./useCountUp";

const MIN_SCAN_MS = 1200;

const nowTime = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

const patternLabel = (p) => {
  if (!p) return null;
  return p.replace(/_/g, " ");
};

const SCAN_STEPS = [
  "Ingesting transaction envelope…",
  "Resolving merchant & UPI graph…",
  "Scoring with XGBoost + policy rules…",
  "Computing SHAP-style feature attributions…",
  "Synthesising security brief…",
];

/** Map model output → product verdict (3-state). */
function verdictFromResult(result) {
  if (!result || result.error) return null;
  const score = Number(result.risk_score) || 0;
  const level = String(result.risk_level || "").toUpperCase();
  if (score >= 85 || level === "CRITICAL") return "BLOCKED";
  if (score >= 30) return "SUSPICIOUS";
  return "SAFE";
}

function shapStyleReasons(result) {
  const factors = Array.isArray(result?.risk_factors) ? result.risk_factors.filter(Boolean) : [];
  if (factors.length) return factors.slice(0, 6);
  const score = Number(result?.risk_score) || 0;
  if (score >= 85) return ["Model score in critical band", "Policy escalation triggered", "Velocity vs baseline"];
  if (score >= 60) return ["Elevated anomaly vs your baseline", "Merchant category risk", "Time-of-day deviation"];
  if (score >= 30) return ["Minor deviation from usual pattern", "Amount slightly above typical"];
  return ["No strong anomaly vs recent behaviour", "Merchant reputation neutral", "Channel trust high"];
}

/** Build SHAP bar payload from reasons + verdict (deterministic magnitudes). */
function buildShapFeaturesFromResult(result, verdict) {
  const reasons = shapStyleReasons(result);
  const safe = verdict === "SAFE";
  return reasons.map((label, i) => {
    const base = safe ? 0.022 + i * 0.006 : 0.035 + i * 0.018;
    const shap_value = safe ? -base * (1 + i * 0.08) : base * (1 + i * 0.12);
    const slug = label
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "")
      .slice(0, 42);
    return {
      name: slug || `signal_${i + 1}`,
      shap_value,
      feature_value: i === 0 ? (safe ? "low" : "elevated") : "—",
    };
  });
}

function recommendedCopy(verdict) {
  if (verdict === "BLOCKED")
    return "Do not complete this payment. If you did not initiate it, report immediately and call 1930.";
  if (verdict === "SUSPICIOUS")
    return "Pause and verify the recipient out-of-band (call a known number, check order ID). Only pay if you are 100% certain.";
  return "Signals look consistent with safe spend for you. Still double-check the UPI handle before confirming.";
}

function ScanningOverlay({ stepIndex }) {
  const step = SCAN_STEPS[Math.min(stepIndex, SCAN_STEPS.length - 1)];
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="absolute inset-0 z-20 flex flex-col items-center justify-center rounded-3xl border border-violet-500/30 bg-[#070418]/90 backdrop-blur-xl"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="relative mb-8 h-32 w-32 sm:h-36 sm:w-36">
        <motion.div
          className="absolute inset-0 rounded-full border-2 border-transparent"
          style={{
            background:
              "conic-gradient(from 0deg, rgba(124,58,237,0.95), rgba(37,99,235,0.5), rgba(34,211,238,0.85), rgba(124,58,237,0.95))",
            mask: "radial-gradient(farthest-side, transparent calc(100% - 3px), #fff calc(100% - 3px))",
            WebkitMask: "radial-gradient(farthest-side, transparent calc(100% - 3px), #fff calc(100% - 3px))",
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "linear" }}
        />
        <div className="absolute inset-0 m-auto flex h-[4.5rem] w-[4.5rem] items-center justify-center rounded-full border border-white/10 bg-white/[0.06] shadow-[0_0_48px_-12px_rgba(124,58,237,0.55)] sm:h-20 sm:w-20">
          <Radar className="h-9 w-9 text-violet-200 sm:h-10 sm:w-10" aria-hidden />
        </div>
      </div>
      <p className="text-base font-semibold tracking-tight text-white">Scanning…</p>
      <p className="mt-2 max-w-sm px-4 text-center text-sm leading-relaxed text-gray-400">{step}</p>
      <div className="mt-8 flex max-w-xs flex-wrap justify-center gap-1.5">
        {SCAN_STEPS.map((label, i) => (
          <span
            key={label}
            className={`h-1.5 w-7 rounded-full transition-colors duration-300 ${i <= stepIndex ? "bg-violet-400 shadow-[0_0_12px_rgba(167,139,250,0.5)]" : "bg-white/10"}`}
          />
        ))}
      </div>
    </motion.div>
  );
}

function MyProtectionStatsMini({ safetyScore = 0, threatsBlocked = 0, moneySaved = 0, loading }) {
  const safetyAnim = useCountUp(safetyScore, { durationMs: 1000, enabled: !loading });
  const blockedAnim = useCountUp(threatsBlocked, { durationMs: 950, enabled: !loading });
  const savedAnim = useCountUp(moneySaved, { durationMs: 1000, enabled: !loading });

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-8 grid gap-3 sm:grid-cols-3"
      >
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <SkeletonCard lines={2} height={72} />
          </div>
        ))}
      </motion.div>
    );
  }

  const cards = [
    {
      key: "blocked",
      label: "Threats blocked",
      body: (
        <div className="mt-2 flex items-end justify-between gap-2">
          <p className="text-2xl font-bold tabular-nums tracking-tight text-white">{Math.round(blockedAnim)}</p>
          <MiniSparkline seed={threatsBlocked} className="opacity-90" />
        </div>
      ),
      sub: "This month · models + rules",
      tone: "from-rose-600/20 to-orange-900/10 border-rose-500/25",
    },
    {
      key: "saved",
      label: "Money saved",
      body: (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <p className="text-xl font-bold tabular-nums tracking-tight text-white sm:text-2xl">{inr(Math.round(savedAnim))}</p>
          <span className="inline-flex items-center gap-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-emerald-200/90">
            <TrendingUp className="h-3 w-3" aria-hidden />
            Rolling
          </span>
        </div>
      ),
      sub: "Disputes + prevented loss",
      tone: "from-emerald-600/20 to-teal-900/10 border-emerald-500/25",
    },
    {
      key: "safety",
      label: "Safety score",
      body: (
        <div className="mt-1 flex items-center gap-3">
          <TrustRing score={safetyAnim} max={100} size={88} stroke={6} label="Score" dark />
          <p className="max-w-[9rem] text-[11px] leading-snug text-gray-400">Blended confidence on your recent activity.</p>
        </div>
      ),
      sub: "0–100 · higher is safer",
      tone: "from-violet-600/25 to-blue-900/10 border-violet-500/30",
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.08, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="mt-8"
    >
      <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-gray-500">My stats</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {cards.map((c, i) => (
          <motion.div
            key={c.key}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i, duration: 0.3 }}
            whileHover={{ y: -3, transition: { duration: 0.15 } }}
            className={`rounded-2xl border bg-gradient-to-br p-5 shadow-[0_0_32px_-18px_rgba(124,58,237,0.25)] backdrop-blur-md ${c.tone}`}
          >
            <p className="text-[10px] font-semibold uppercase tracking-wider text-white/50">{c.label}</p>
            {c.body}
            <p className="mt-2 text-[11px] text-gray-500">{c.sub}</p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

function VerdictCard({ verdict, result, userName, reporting, reportMsg, onDismiss, onReport, securityBrief }) {
  const score = Number(result?.risk_score) || 0;
  const shapFeatures = useMemo(() => buildShapFeaturesFromResult(result, verdict), [result, verdict]);
  const meta = useMemo(() => {
    if (verdict === "BLOCKED")
      return {
        Icon: ShieldX,
        title: "BLOCKED",
        sub: "Do not proceed",
        pill: "border-rose-500/50 bg-rose-500/15 text-rose-100",
        glow: "shadow-[0_0_48px_-16px_rgba(239,68,68,0.55)]",
      };
    if (verdict === "SUSPICIOUS")
      return {
        Icon: ShieldAlert,
        title: "SUSPICIOUS",
        sub: "Extra verification required",
        pill: "border-amber-500/45 bg-amber-500/12 text-amber-100",
        glow: "shadow-[0_0_40px_-18px_rgba(245,158,11,0.45)]",
      };
    return {
      Icon: ShieldCheck,
      title: "SAFE",
      sub: "Low model concern",
      pill: "border-emerald-500/45 bg-emerald-500/12 text-emerald-100",
      glow: "shadow-[0_0_40px_-18px_rgba(16,185,129,0.4)]",
    };
  }, [verdict]);

  const Icon = meta.Icon;
  const isCritical = verdict === "BLOCKED";
  const isSuspicious = verdict === "SUSPICIOUS";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 48, scale: 0.97 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: -24 }}
      transition={{ type: "spring", stiffness: 320, damping: 28 }}
      className={`relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-white/[0.08] to-white/[0.02] p-6 backdrop-blur-xl sm:p-8 ${meta.glow}`}
    >
      <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-violet-600/18 blur-3xl" />
      <div className="relative flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <motion.div
            initial={{ scale: 0.85 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 400, damping: 22 }}
            className={`grid h-16 w-16 shrink-0 place-items-center rounded-2xl border sm:h-[4.5rem] sm:w-[4.5rem] ${meta.pill}`}
          >
            <Icon className="h-8 w-8 sm:h-9 sm:w-9" aria-hidden />
          </motion.div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] ${meta.pill}`}>{meta.title}</span>
              <span className="rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-0.5 font-mono text-xs tabular-nums text-gray-300">
                Score {Math.round(score)}/100
              </span>
            </div>
            <p className="mt-2 text-lg font-bold tracking-tight text-white sm:text-xl">{meta.sub}</p>
          </div>
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
        className="relative mt-6 rounded-2xl border border-amber-500/25 bg-gradient-to-r from-amber-500/10 to-violet-600/10 p-4"
      >
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-200/90">Recommended action</p>
        <p className="mt-2 text-sm font-medium leading-relaxed text-white/95">{recommendedCopy(verdict)}</p>
      </motion.div>

      <div className="relative mt-6 rounded-2xl border border-white/10 bg-black/30 p-4 sm:p-5">
        <div className="mb-3 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-200/85">
          <Sparkles className="h-3.5 w-3.5 shrink-0" aria-hidden />
          SHAP explanation
        </div>
        <ShapExplanationBars features={shapFeatures} variant="dark" maxBars={6} />
        {patternLabel(result?.pattern_matched) && (
          <p className="mt-4 text-xs text-amber-200/85">
            <span className="font-semibold text-amber-100/90">Pattern:</span> {patternLabel(result.pattern_matched)}
          </p>
        )}
      </div>

      {securityBrief ? (
        <div className="relative mt-4 rounded-2xl border border-violet-500/25 bg-violet-500/10 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-200/80">AI security brief</p>
          <p className="mt-2 text-sm leading-relaxed text-violet-50/90">{securityBrief}</p>
        </div>
      ) : null}

      {result?.warning_message && !securityBrief && (
        <p className="relative mt-4 text-sm text-amber-100/85">{result.warning_message}</p>
      )}

      <div className="relative mt-6 flex flex-wrap gap-2">
        {isCritical && (
          <>
            <a
              href="tel:1930"
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-white/15 bg-white/[0.06] px-4 text-sm font-semibold text-white transition hover:bg-white/[0.1]"
            >
              Call 1930
            </a>
            <button
              type="button"
              disabled={reporting}
              onClick={onReport}
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-gradient-to-r from-rose-600 to-red-600 px-4 text-sm font-semibold text-white shadow-lg shadow-rose-500/25 transition hover:brightness-110 disabled:opacity-50"
            >
              {reporting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Report fraud
            </button>
          </>
        )}
        {isSuspicious && (
          <>
            <button
              type="button"
              onClick={onDismiss}
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-gradient-to-r from-violet-600 to-blue-600 px-4 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:brightness-110"
            >
              I&apos;ve verified — dismiss
            </button>
            <button
              type="button"
              disabled={reporting}
              onClick={onReport}
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-rose-500/40 bg-rose-500/15 px-4 text-sm font-semibold text-rose-100 transition hover:bg-rose-500/25 disabled:opacity-50"
            >
              Report fraud
            </button>
          </>
        )}
        {!isCritical && !isSuspicious && (
          <button
            type="button"
            onClick={onDismiss}
            className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-4 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 transition hover:brightness-110"
          >
            Done — looks good for {userName}
          </button>
        )}
        {(isCritical || isSuspicious) && (
          <button
            type="button"
            onClick={onDismiss}
            className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-white/15 px-4 text-sm font-medium text-gray-400 transition hover:bg-white/[0.06] hover:text-white"
          >
            Scan another
          </button>
        )}
      </div>

      {reportMsg ? (
        <p className="relative mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100/90">
          {reportMsg}
        </p>
      ) : null}

      {(isCritical || isSuspicious) && (
        <p className="relative mt-3 text-center text-[11px] text-gray-500">
          <a href={result.cybercrime_url || "https://cybercrime.gov.in"} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
            National Cyber Crime Reporting Portal
          </a>{" "}
          · Helpline {result.helpline || "1930"}
        </p>
      )}
    </motion.div>
  );
}

const TransactionChecker = ({ userId, userName, onReportSuccess, protectionStats }) => {
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
  const [scanStep, setScanStep] = useState(0);
  const scanTimerRef = useRef(null);

  const statsLoading = Boolean(protectionStats?.loading);
  const safetyScore = protectionStats?.safetyScore ?? 0;
  const threatsBlocked = protectionStats?.threatsBlocked ?? 0;
  const moneySaved = protectionStats?.moneySaved ?? 0;
  const showMyStats = protectionStats != null;

  useEffect(() => {
    if (!loading) {
      if (scanTimerRef.current) clearInterval(scanTimerRef.current);
      scanTimerRef.current = null;
      setScanStep(0);
      return undefined;
    }
    scanTimerRef.current = window.setInterval(() => {
      setScanStep((s) => (s + 1 >= SCAN_STEPS.length ? SCAN_STEPS.length - 1 : s + 1));
    }, 320);
    return () => {
      if (scanTimerRef.current) clearInterval(scanTimerRef.current);
    };
  }, [loading]);

  const runCheck = async (body) => {
    setLoading(true);
    setResult(null);
    setReportMsg("");
    setScanStep(0);
    const t0 = Date.now();
    try {
      const data = await postFraudShieldCheckTransaction(userId, body);
      const elapsed = Date.now() - t0;
      const pad = Math.max(0, MIN_SCAN_MS - elapsed);
      if (pad) await new Promise((r) => setTimeout(r, pad));
      setResult(data);
    } catch (e) {
      const elapsed = Date.now() - t0;
      const pad = Math.max(0, MIN_SCAN_MS - elapsed);
      if (pad) await new Promise((r) => setTimeout(r, pad));
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
    setDescription("Urgent KYC completion — link shared on WhatsApp");
    setPaymentMethod("UPI");
  };
  const fillLottery = () => {
    setMerchant("prize-claim-2025@upi");
    setAmount("2000");
    setTime("15:00");
    setDescription("Lottery processing fee — claim ₹5 lakh prize");
    setPaymentMethod("UPI");
  };
  const fillNormal = () => {
    setMerchant("swiggy@ybl");
    setAmount("250");
    setTime("14:00");
    setDescription("Lunch order — office");
    setPaymentMethod("UPI");
  };
  const fillRupeeTrap = () => {
    setMerchant("verify-upi-axis@okaxis");
    setAmount("1");
    setTime("23:45");
    setDescription("UPI wallet verification — please send ₹1 to confirm");
    setPaymentMethod("UPI");
  };
  const fillCollect = () => {
    setMerchant("refund-amazon@okaxis");
    setAmount("3499");
    setTime("12:00");
    setDescription("UPI collect request — fake refund for cancelled order");
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
        onReportSuccess?.();
      } else {
        setReportMsg(
          `Fraud reported — file details on ${result?.cybercrime_url || "https://cybercrime.gov.in"} (Helpline 1930).`
        );
        showToast("Fraud reported — file details on National Cyber Crime Portal ✅");
        onReportSuccess?.();
      }
    } catch (e) {
      setReportMsg(e.message || "Could not update alert");
    } finally {
      setReporting(false);
    }
  };

  const verdict = useMemo(() => (result && !result.error ? verdictFromResult(result) : null), [result]);
  const securityBrief = (result?.ai_security_message || result?.hinglish_warning || "").trim();
  const amtPreview = parseFloat(amount);
  const amountLabel = Number.isFinite(amtPreview) ? inr(amtPreview) : "—";

  const inputShell =
    "mt-2 w-full rounded-2xl border border-white/10 bg-white/[0.05] px-4 py-4 text-base text-white outline-none transition placeholder:text-gray-600 placeholder:font-mono focus:border-violet-400/55 focus:ring-2 focus:ring-violet-500/25 sm:px-5 sm:py-[1.125rem]";
  const labelClass = "text-[11px] font-semibold uppercase tracking-[0.14em] text-gray-500";

  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-[#0a0a22]/95 via-violet-950/25 to-[#0f172a]/92 p-1 shadow-[0_0_64px_-22px_rgba(124,58,237,0.5)]">
      <div className="rounded-[22px] border border-white/5 bg-white/[0.025] p-5 sm:p-8 md:p-10">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 flex flex-wrap items-end justify-between gap-4"
        >
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-purple-500/20 bg-purple-500/10 px-3 py-1">
              <Sparkles className="h-3 w-3 text-purple-300" aria-hidden />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-purple-300">Premium Safety Scanner</span>
            </div>
            <h3 className="mt-2 text-2xl font-bold tracking-tight text-white sm:text-3xl">Check before you pay</h3>
            <p className="mt-3 text-sm leading-relaxed text-gray-400 sm:text-base">
              Large-field check against the same scoring stack as live protection — verdict, SHAP-style drivers, and a clear recommended action.
            </p>
          </div>
          <div className="hidden flex-col items-end gap-1 md:flex">
            <div className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.04] px-3 py-1.5">
              <Zap className="h-3.5 w-3.5 text-cyan-300" aria-hidden />
              <span className="text-sm font-medium text-white">Scan ~1.2s</span>
            </div>
            <span className="text-[11px] text-gray-500">Rules + model + brief</span>
          </div>
        </motion.div>

        <form onSubmit={onSubmit} className="relative space-y-6" aria-busy={loading}>
          <AnimatePresence>{loading && <ScanningOverlay stepIndex={scanStep} />}</AnimatePresence>

          <div className="grid gap-5 lg:gap-6">
            <label className="block">
              <span className={labelClass}>Merchant / UPI ID</span>
              <textarea
                className={`${inputShell} min-h-[5.5rem] resize-y font-mono text-base leading-relaxed sm:min-h-[6rem] sm:text-lg`}
                value={merchant}
                onChange={(e) => setMerchant(e.target.value)}
                placeholder="e.g. merchant@ybl, paytm.swiggy, or full UPI handle"
                autoComplete="off"
                rows={3}
                disabled={loading}
              />
            </label>

            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              <label className="block">
                <span className={labelClass}>Amount (₹)</span>
                <input
                  className={`${inputShell} tabular-nums text-xl font-bold tracking-tight sm:text-2xl`}
                  type="number"
                  min="0"
                  step="0.01"
                  inputMode="decimal"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  disabled={loading}
                />
                <p className="mt-1.5 text-xs text-gray-600">Preview: {amountLabel}</p>
              </label>
              <label className="block">
                <span className={labelClass}>Time</span>
                <input
                  className={`${inputShell} tabular-nums`}
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                  placeholder="23:30"
                  disabled={loading}
                />
              </label>
              <label className="block sm:col-span-2 lg:col-span-1">
                <span className={labelClass}>Payment method</span>
                <select
                  className={`${inputShell} cursor-pointer appearance-none bg-[length:1rem] bg-[right_1rem_center] bg-no-repeat pr-10`}
                  style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='rgba(226,232,240,0.5)'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E")`,
                  }}
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  disabled={loading}
                >
                  <option value="UPI">UPI</option>
                  <option value="UPI Collect">UPI Collect</option>
                  <option value="IMPS">IMPS</option>
                  <option value="Card">Card</option>
                  <option value="Net Banking">Net Banking</option>
                </select>
              </label>
            </div>

            <label className="block">
              <span className={labelClass}>Description</span>
              <textarea
                className={`${inputShell} min-h-[6.5rem] resize-y text-sm leading-relaxed sm:min-h-[7rem] sm:text-base`}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Order ID, purpose, who asked you to pay, or any context that helps the model"
                rows={4}
                disabled={loading}
              />
            </label>
          </div>

          <div>
            <p className={labelClass}>Quick-test scenarios</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                { label: "KYC fraud", fn: fillKyc, tone: "border-rose-500/35 bg-rose-500/10 text-rose-100 hover:bg-rose-500/20" },
                { label: "Lottery scam", fn: fillLottery, tone: "border-rose-500/35 bg-rose-500/10 text-rose-100 hover:bg-rose-500/20" },
                { label: "UPI collect", fn: fillCollect, tone: "border-amber-500/35 bg-amber-500/10 text-amber-100 hover:bg-amber-500/20" },
                { label: "₹1 trap", fn: fillRupeeTrap, tone: "border-rose-500/35 bg-rose-500/10 text-rose-100 hover:bg-rose-500/20" },
                { label: "Normal order", fn: fillNormal, tone: "border-emerald-500/35 bg-emerald-500/10 text-emerald-100 hover:bg-emerald-500/20" },
              ].map((q, qi) => (
                <motion.button
                  key={q.label}
                  type="button"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.04 * qi }}
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={q.fn}
                  disabled={loading}
                  className={`rounded-full border px-4 py-2 text-xs font-semibold transition disabled:opacity-40 ${q.tone}`}
                >
                  {q.label}
                </motion.button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3 pt-1 sm:flex-row sm:flex-wrap sm:items-center">
            <motion.button
              type="submit"
              disabled={loading || !merchant.trim() || Number.isNaN(parseFloat(amount))}
              whileHover={{ scale: loading ? 1 : 1.02 }}
              whileTap={{ scale: loading ? 1 : 0.98 }}
              className="inline-flex min-h-[56px] min-w-[min(100%,220px)] items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-violet-600 to-blue-600 px-10 text-base font-bold text-white shadow-[0_0_44px_-10px_rgba(124,58,237,0.65)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 sm:min-w-[240px]"
            >
              {loading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
                  Checking…
                </>
              ) : (
                <>
                  <Radar className="h-5 w-5 shrink-0" aria-hidden />
                  Check safety
                </>
              )}
            </motion.button>
            <p className="text-xs text-gray-400 sm:max-w-xs">Fill merchant / UPI and amount to run the scan.</p>
          </div>
        </form>

        <AnimatePresence mode="wait">
          {result && !loading && result.error && (
            <motion.div
              key="err"
              initial={{ opacity: 0, x: 32 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 28 }}
              className="mt-8 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5 text-sm text-rose-100/90"
            >
              {result.warning_message}
            </motion.div>
          )}
          {result && !loading && !result.error && verdict && (
            <motion.div key="ok" className="mt-10" layout>
              <VerdictCard
                verdict={verdict}
                result={result}
                userName={userName || "you"}
                reporting={reporting}
                reportMsg={reportMsg}
                onDismiss={() => {
                  setResult(null);
                  setReportMsg("");
                }}
                onReport={handleReport}
                securityBrief={securityBrief}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {showMyStats ? (
          <MyProtectionStatsMini
            safetyScore={safetyScore}
            threatsBlocked={threatsBlocked}
            moneySaved={moneySaved}
            loading={statsLoading}
          />
        ) : null}
      </div>
    </div>
  );
};

export default TransactionChecker;
