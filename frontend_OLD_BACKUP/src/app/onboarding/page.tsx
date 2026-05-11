/**
 * Onboarding steps:
 * 1) Enter mobile number
 * 2) Send OTP
 * 3) Verify OTP
 * 4) Link bank
 */
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { AnimatedShield } from "../../components/Auth/AnimatedShield";
import { BankCard } from "../../components/onboarding/BankCard";
import { useAuth } from "../../context/AuthContext";
import { onboardingGetBanks, onboardingLinkBank, otpSend, otpVerify } from "../../services/api";

type Bank = { id: string; name: string; logo: string };

export default function OnboardingPage() {
  const reduce = useReducedMotion();
  const { user, reloadUser } = useAuth();
  const [mobile, setMobile] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpVerified, setOtpVerified] = useState(false);
  const [demoOtp, setDemoOtp] = useState("");
  const [banks, setBanks] = useState<Bank[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [selectedBank, setSelectedBank] = useState("");

  const step = useMemo(() => {
    if (!otpSent) return 1;
    if (!otpVerified) return 2;
    if (!selectedBank) return 3;
    return 4;
  }, [otpSent, otpVerified, selectedBank]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await onboardingGetBanks();
        if (cancelled) return;
        setBanks((data?.banks || []) as Bank[]);
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load banks");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const sendOtp = async () => {
    setError("");
    setStatus("");
    if (!/^\d{10,15}$/.test(mobile.trim())) {
      setError("Enter a valid mobile number (10-15 digits)");
      return;
    }
    setBusy(true);
    try {
      const data = await otpSend({ mobile_number: mobile.trim() });
      setOtpSent(true);
      setDemoOtp(String(data.otp_code || ""));
      setStatus("OTP sent successfully");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to send OTP");
    } finally {
      setBusy(false);
    }
  };

  const verifyOtp = async () => {
    setError("");
    setStatus("");
    if (!/^\d{6}$/.test(otp.trim())) {
      setError("Enter a valid 6-digit OTP");
      return;
    }
    setBusy(true);
    try {
      await otpVerify({ mobile_number: mobile.trim(), otp_code: otp.trim() });
      setOtpVerified(true);
      setStatus("OTP verified. Now select your bank.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "OTP verification failed");
    } finally {
      setBusy(false);
    }
  };

  const linkBank = async (bank: Bank) => {
    if (!user?.id) {
      setError("Session missing. Please sign in again.");
      return;
    }
    if (!otpVerified) {
      setError("Verify OTP before selecting bank");
      return;
    }
    setError("");
    setBusy(true);
    setSelectedBank(bank.name);
    setStatus(`Linking ${bank.name} and importing transactions...`);
    try {
      await onboardingLinkBank({
        user_id: user.id,
        bank_name: bank.name,
        mobile_number: mobile.trim(),
      });
      await reloadUser();
      setStatus("Successfully linked bank and completed onboarding.");
    } catch (e: unknown) {
      setSelectedBank("");
      setError(e instanceof Error ? e.message : "Bank linking failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0F172A] text-slate-100">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-[420px] w-[420px] rounded-full bg-violet-600/20 blur-[120px]" />
        <div className="absolute -right-20 bottom-0 h-[380px] w-[380px] rounded-full bg-cyan-500/15 blur-[100px]" />
      </div>

      <motion.main
        className="relative z-[1] mx-auto max-w-[1100px] px-4 pb-16 pt-8 md:px-8 md:pt-12"
        initial={reduce ? undefined : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
      >
        <div className="mb-8 text-center">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-400/90">Step {step} of 4</p>
          <div className="mx-auto mt-4 flex max-w-[min(280px,86vw)] justify-center">
            <AnimatedShield />
          </div>
          <h1 className="mt-6 text-3xl font-bold text-white md:text-4xl">Complete onboarding</h1>
          <p className="mt-2 text-slate-400">Verify mobile, then link your bank securely.</p>
        </div>

        <div className="mx-auto max-w-2xl rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-400">
            Mobile Number
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              className="w-full rounded-xl border border-white/10 bg-[#111827]/70 px-4 py-3 text-white outline-none transition focus:border-violet-500/70 focus:ring-2 focus:ring-cyan-500/30"
              placeholder="e.g. 9876543210"
              value={mobile}
              onChange={(e) => setMobile(e.target.value.replace(/[^\d]/g, ""))}
              maxLength={15}
              disabled={otpVerified || busy}
            />
            <button
              type="button"
              onClick={() => void sendOtp()}
              disabled={busy || otpVerified}
              className="rounded-xl bg-gradient-to-r from-violet-600 via-fuchsia-600 to-pink-600 px-5 py-3 font-semibold text-white disabled:opacity-50"
            >
              {otpSent ? "Resend OTP" : "Send OTP"}
            </button>
          </div>

          {otpSent ? (
            <div className="mt-4">
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-400">OTP</label>
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  className="w-full rounded-xl border border-white/10 bg-[#111827]/70 px-4 py-3 text-white outline-none transition focus:border-violet-500/70 focus:ring-2 focus:ring-cyan-500/30"
                  placeholder="Enter 6-digit OTP"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/[^\d]/g, "").slice(0, 6))}
                  maxLength={6}
                  disabled={otpVerified || busy}
                />
                <button
                  type="button"
                  onClick={() => void verifyOtp()}
                  disabled={busy || otpVerified}
                  className="rounded-xl border border-cyan-400/50 px-5 py-3 font-semibold text-cyan-200 disabled:opacity-50"
                >
                  {otpVerified ? "Verified" : "Verify OTP"}
                </button>
              </div>
              {!!demoOtp && !otpVerified ? (
                <p className="mt-2 text-xs text-amber-300">Demo OTP: {demoOtp}</p>
              ) : null}
            </div>
          ) : null}

          {error ? <p className="mt-4 text-sm text-red-300">{error}</p> : null}
          {status ? <p className="mt-3 text-sm text-emerald-300">{status}</p> : null}
        </div>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {banks.map((bank, index) => (
            <div key={bank.id} className={otpVerified ? "" : "pointer-events-none opacity-50"}>
              <BankCard id={bank.id} name={bank.name} logo={bank.logo} index={index} onSelect={() => void linkBank(bank)} />
            </div>
          ))}
        </div>
      </motion.main>
    </div>
  );
}
