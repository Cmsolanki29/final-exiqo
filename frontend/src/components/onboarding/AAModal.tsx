import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";

export type BankOption = { id: string; name: string; logo: string };

const LOADING_STEPS = [
  (label: string) => `Connecting to ${label}…`,
  () => "Authenticating your account…",
  () => "Fetching 6 months of transactions…",
  () => "Analyzing your spending patterns…",
  () => "Almost done…",
];

export interface AAModalProps {
  open: boolean;
  bank: BankOption | null;
  onClose: () => void;
  /** Any 6-digit OTP accepted; mock AA — returns import payload from API */
  onSubmit: (otp: string) => Promise<{ transactions_imported: number }>;
  onSuccessComplete: () => void | Promise<void>;
}

export function AAModal({ open, bank, onClose, onSubmit, onSuccessComplete }: AAModalProps) {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState<"otp" | "loading" | "success">("otp");
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [error, setError] = useState("");
  const [importCount, setImportCount] = useState(0);
  const [loadingIdx, setLoadingIdx] = useState(0);
  const inputsRef = useRef<Array<HTMLInputElement | null>>([]);

  const reset = useCallback(() => {
    setPhase("otp");
    setDigits(["", "", "", "", "", ""]);
    setError("");
    setImportCount(0);
    setLoadingIdx(0);
  }, []);

  useEffect(() => {
    if (!open) reset();
  }, [open, reset]);

  useEffect(() => {
    if (phase !== "loading" || !bank) return;
    const id = window.setInterval(() => {
      setLoadingIdx((i) => Math.min(i + 1, LOADING_STEPS.length - 1));
    }, 1400);
    return () => window.clearInterval(id);
  }, [phase, bank]);

  useEffect(() => {
    if (open && phase === "otp") {
      window.requestAnimationFrame(() => inputsRef.current[0]?.focus());
    }
  }, [open, phase]);

  const otp = digits.join("");

  const setDigit = (i: number, v: string) => {
    const ch = v.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[i] = ch;
    setDigits(next);
    if (ch && i < 5) inputsRef.current[i + 1]?.focus();
  };

  const onKeyDown = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      inputsRef.current[i - 1]?.focus();
    }
  };

  const onPaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const t = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    const arr = t.split("");
    const next = ["", "", "", "", "", ""];
    for (let j = 0; j < 6; j += 1) next[j] = arr[j] || "";
    setDigits(next);
    const last = Math.min(arr.length, 5);
    inputsRef.current[last]?.focus();
  };

  const handleVerify = async () => {
    if (otp.length !== 6) {
      setError("Enter the 6-digit OTP");
      return;
    }
    setError("");
    setLoadingIdx(0);
    setPhase("loading");
    try {
      const res = await onSubmit(otp);
      setImportCount(Number(res.transactions_imported) || 0);
      setPhase("success");
      window.setTimeout(() => {
        void Promise.resolve(onSuccessComplete());
      }, 2000);
    } catch (err: unknown) {
      setPhase("otp");
      setError(err instanceof Error ? err.message : "Connection failed");
    }
  };

  if (!bank) return null;

  const stepFn = LOADING_STEPS[loadingIdx];
  const loadingLabel = stepFn(bank.name);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="aa-modal-title"
          className="fixed inset-0 z-[100] flex items-end justify-center p-4 sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
        >
          <motion.div
            role="presentation"
            aria-hidden
            className="absolute inset-0 bg-[#070B1A]/80 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={phase === "loading" ? undefined : onClose}
          />
          <motion.div
            className="relative z-[1] w-full max-w-lg overflow-hidden rounded-3xl border border-white/[0.08] bg-[#111827]/95 shadow-[0_40px_120px_rgba(0,0,0,0.55)] backdrop-blur-2xl"
            initial={reduce ? undefined : { y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={reduce ? undefined : { y: 24, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
          >
            <div className="border-b border-white/[0.06] px-6 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-400/90">
                    RBI framework · Demo
                  </p>
                  <h2 id="aa-modal-title" className="mt-1 text-xl font-bold text-white">
                    Account Aggregator
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    Consent-based financial data sharing (mock screen for SmartSpend).
                  </p>
                </div>
                {phase !== "loading" && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="rounded-lg px-2 py-1 text-sm text-slate-400 transition hover:bg-white/5 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400/60"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            <div className="px-6 py-6">
              <div className="mb-6 flex items-center gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.04] p-4">
                <span className="text-3xl" aria-hidden>
                  {bank.logo}
                </span>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Selected institution</p>
                  <p className="text-lg font-semibold text-white">{bank.name}</p>
                </div>
              </div>

              {phase === "otp" && (
                <div>
                  <p className="mb-3 text-sm text-slate-300">Enter OTP sent to your registered mobile (demo: any 6 digits)</p>
                  <div className="flex justify-center gap-2 sm:gap-3" onPaste={onPaste}>
                    {digits.map((d, i) => (
                      <input
                        key={i}
                        ref={(el) => {
                          inputsRef.current[i] = el;
                        }}
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        maxLength={1}
                        value={d}
                        onChange={(e) => setDigit(i, e.target.value)}
                        onKeyDown={(e) => onKeyDown(i, e)}
                        aria-label={`Digit ${i + 1}`}
                        className="h-12 w-10 rounded-xl border border-slate-600/60 bg-[#0F172A]/80 text-center text-lg font-semibold text-white shadow-inner outline-none transition focus:border-violet-500 focus:ring-2 focus:ring-cyan-500/30 sm:h-14 sm:w-12 sm:text-xl"
                      />
                    ))}
                  </div>
                  {error ? (
                    <p className="mt-3 text-center text-sm text-red-400" role="alert">
                      {error}
                    </p>
                  ) : null}
                  <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
                    <button
                      type="button"
                      onClick={onClose}
                      className="rounded-xl border border-slate-600/60 px-5 py-3 text-sm font-semibold text-slate-200 transition hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400/60"
                    >
                      Cancel
                    </button>
                    <motion.button
                      type="button"
                      onClick={() => void handleVerify()}
                      whileHover={reduce ? undefined : { y: -1 }}
                      whileTap={reduce ? undefined : { scale: 0.98 }}
                      className="rounded-xl bg-gradient-to-r from-violet-600 via-fuchsia-600 to-pink-600 px-5 py-3 text-sm font-semibold text-white shadow-[0_12px_40px_rgba(139,92,246,0.35)] transition hover:shadow-[0_16px_48px_rgba(236,72,153,0.35)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fuchsia-400/80"
                    >
                      Verify &amp; Connect
                    </motion.button>
                  </div>
                </div>
              )}

              {phase === "loading" && (
                <div className="flex flex-col items-center py-10 text-center">
                  <motion.div
                    className="mb-6 h-12 w-12 rounded-full border-2 border-violet-500/30 border-t-cyan-400"
                    animate={reduce ? undefined : { rotate: 360 }}
                    transition={reduce ? undefined : { repeat: Infinity, duration: 0.9, ease: "linear" }}
                    aria-hidden
                  />
                  <p className="text-lg font-medium text-white">Fetching your transactions…</p>
                  <p className="mt-2 max-w-sm text-sm text-slate-400">{loadingLabel}</p>
                </div>
              )}

              {phase === "success" && (
                <motion.div
                  className="flex flex-col items-center py-8 text-center"
                  initial={reduce ? undefined : { opacity: 0, scale: 0.94 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.35 }}
                >
                  <motion.div
                    className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20 text-3xl text-emerald-400"
                    initial={reduce ? undefined : { scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 400, damping: 18 }}
                    aria-hidden
                  >
                    ✓
                  </motion.div>
                  <p className="text-xl font-bold text-white">Successfully connected!</p>
                  <p className="mt-2 text-lg text-emerald-300/90">
                    ✅ {importCount} transactions imported
                  </p>
                  <p className="mt-3 text-sm text-slate-500">Taking you to your dashboard…</p>
                </motion.div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
