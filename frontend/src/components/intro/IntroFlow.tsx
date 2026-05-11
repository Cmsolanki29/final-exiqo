import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { GetStartedScreen } from "./GetStartedScreen";
import { IntroAuth, type AuthMode } from "./IntroAuth";
import { IntroStory } from "./IntroStory";
import { SplashScreen } from "./SplashScreen";

const BRAND_EASE = [0.22, 1, 0.36, 1] as const;

export const SEEN_INTRO_KEY = "smartspend.seenIntro";

/**
 * Per-tab session key. sessionStorage:
 *   - Survives page refresh → user stays on same step
 *   - Cleared when tab is closed / new tab opens → intro restarts
 */
const SESSION_STEP_KEY = "smartspend.introStep";

export type IntroStep = "splash" | "intro" | "get-started" | "auth";

export type IntroFlowProps = {
  onComplete: () => void;
};

const SHIELD_LAYOUT_ID = "ssShieldMark";

/** Read step from sessionStorage (per-tab, survives refresh). */
function readSessionStep(): IntroStep | null {
  try {
    const v = window.sessionStorage.getItem(SESSION_STEP_KEY);
    if (v === "splash" || v === "intro" || v === "get-started" || v === "auth") {
      return v as IntroStep;
    }
    return null;
  } catch {
    return null;
  }
}

/** Persist current step so refresh lands on same screen. */
function writeSessionStep(step: IntroStep) {
  try {
    window.sessionStorage.setItem(SESSION_STEP_KEY, step);
  } catch { /* ignore */ }
}

function safeWriteFlag() {
  try {
    window.localStorage.setItem(SEEN_INTRO_KEY, "true");
  } catch { /* ignore */ }
}

/**
 * Top-level orchestrator for the intro flow.
 *
 * Behavior:
 *   - New tab / new window  → always starts from "splash" (sessionStorage empty)
 *   - Refresh on same tab   → resumes on same step (sessionStorage survives refresh)
 *   - After sign-in         → App.jsx isAuthenticated=true, IntroFlow unmounts
 */
export function IntroFlow({ onComplete }: IntroFlowProps) {
  const [step, setStep] = useState<IntroStep>(() => {
    // Resume position in THIS tab session if the user already progressed.
    // On a fresh tab sessionStorage is always empty → starts at "splash".
    return readSessionStep() ?? "splash";
  });
  const [authMode, setAuthMode] = useState<AuthMode>("signin");

  const markSeen = useCallback(() => {
    safeWriteFlag();
  }, []);

  const fromSplash = useCallback(() => {
    writeSessionStep("intro");
    setStep("intro");
  }, []);

  const fromIntro = useCallback(() => {
    writeSessionStep("get-started");
    setStep("get-started");
  }, []);

  const skipToAuth = useCallback(
    (mode: AuthMode = "signin") => {
      markSeen();
      writeSessionStep("auth");
      setAuthMode(mode);
      setStep("auth");
    },
    [markSeen]
  );

  const fromGetStartedToCreate = useCallback(() => {
    markSeen();
    writeSessionStep("auth");
    setAuthMode("signup");
    setStep("auth");
  }, [markSeen]);

  const fromGetStartedToSignin = useCallback(() => {
    markSeen();
    writeSessionStep("auth");
    setAuthMode("signin");
    setStep("auth");
  }, [markSeen]);

  const onAuthBack = useCallback(() => {
    writeSessionStep("get-started");
    setStep("get-started");
  }, []);

  const onAuthenticated = useCallback(() => {
    markSeen();
    onComplete();
  }, [markSeen, onComplete]);

  // Write initial step to sessionStorage on first mount so refresh stays on same screen.
  useEffect(() => {
    writeSessionStep(step);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Defensive: if the URL hash includes #signup or #signin, deep-link.
  useEffect(() => {
    const hash = (window.location.hash || "").toLowerCase();
    if (hash.includes("signup")) {
      setAuthMode("signup");
      setStep("auth");
    } else if (hash.includes("signin") || hash.includes("login")) {
      setAuthMode("signin");
      setStep("auth");
    }
  }, []);

  // NOTE: We intentionally use the default ("sync") AnimatePresence mode here
  // — not "wait" — because the splash → intro shield morph relies on both
  // ShieldMark components (sharing layoutId="ssShieldMark") being present
  // simultaneously during the transition so Framer Motion can FLIP between them.
  return (
    <AnimatePresence>
      {step === "splash" ? (
        <motion.div
          key="splash"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.4, ease: BRAND_EASE } }}
        >
          <SplashScreen
            onComplete={fromSplash}
            onSkip={() => skipToAuth("signin")}
            shieldLayoutId={SHIELD_LAYOUT_ID}
          />
        </motion.div>
      ) : null}

      {step === "intro" ? (
        <motion.div
          key="intro"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.55, ease: BRAND_EASE } }}
          exit={{ opacity: 0, transition: { duration: 0.35, ease: BRAND_EASE } }}
        >
          <IntroStory
            onFinish={fromIntro}
            onSkip={() => skipToAuth("signin")}
            shieldLayoutId={SHIELD_LAYOUT_ID}
          />
        </motion.div>
      ) : null}

      {step === "get-started" ? (
        <motion.div
          key="get-started"
          initial={{ opacity: 0, scale: 0.985 }}
          animate={{
            opacity: 1,
            scale: 1,
            transition: { duration: 0.55, ease: BRAND_EASE },
          }}
          exit={{ opacity: 0, transition: { duration: 0.35, ease: BRAND_EASE } }}
        >
          <GetStartedScreen
            onCreate={fromGetStartedToCreate}
            onSignIn={fromGetStartedToSignin}
            shieldLayoutId={SHIELD_LAYOUT_ID}
          />
        </motion.div>
      ) : null}

      {step === "auth" ? (
        <motion.div
          key="auth"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.55, ease: BRAND_EASE } }}
          exit={{ opacity: 0, transition: { duration: 0.35, ease: BRAND_EASE } }}
        >
          <IntroAuth
            initialMode={authMode}
            onAuthenticated={onAuthenticated}
            onBack={onAuthBack}
            shieldLayoutId={SHIELD_LAYOUT_ID}
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export default IntroFlow;
