import React, { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import CyberSafeHub from "./screens/CyberSafeHub";
import CyberSafeReport from "./screens/CyberSafeReport";
import CyberSafeReports from "./screens/CyberSafeReports";
import CyberSafeSuccess from "./screens/CyberSafeSuccess";
import CyberSafeScamDetail from "./screens/CyberSafeScamDetail";

const SCREENS = {
  hub: "hub",
  report: "report",
  reports: "reports",
  success: "success",
  scam: "scam",
};

/**
 * CyberSafe Connect — native full-width SmartSpend page flow.
 * Sidebar: Risk Awareness › CyberSafe Connect
 */
export default function CyberSafeConnect({ onScreenChange }) {
  const [screen, setScreen] = useState(SCREENS.hub);
  const [scamId, setScamId] = useState("upi-fraud");

  const go = useCallback(
    (next) => {
      setScreen(next);
      onScreenChange?.(next);
      try {
        const url = new URL(window.location.href);
        if (next === SCREENS.hub) url.searchParams.delete("cybersafeScreen");
        else url.searchParams.set("cybersafeScreen", next);
        window.history.replaceState({}, "", url.toString());
      } catch {
        /* ignore */
      }
    },
    [onScreenChange],
  );

  useEffect(() => {
    const syncFromUrl = () => {
      try {
        const q = new URLSearchParams(window.location.search).get("cybersafeScreen");
        if (q && Object.values(SCREENS).includes(q)) setScreen(q);
      } catch {
        /* ignore */
      }
    };
    syncFromUrl();
    const onNav = (e) => {
      const cs = e.detail?.cybersafeScreen;
      if (cs && Object.values(SCREENS).includes(cs)) setScreen(cs);
    };
    window.addEventListener("smartspend:navigate", onNav);
    return () => window.removeEventListener("smartspend:navigate", onNav);
  }, []);

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={screen}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.2 }}
      >
        {screen === SCREENS.hub && (
          <CyberSafeHub
            onReport={() => go(SCREENS.report)}
            onViewReports={() => go(SCREENS.reports)}
            onScamDetail={(id) => {
              setScamId(id);
              go(SCREENS.scam);
            }}
          />
        )}
        {screen === SCREENS.report && (
          <CyberSafeReport
            onBack={() => go(SCREENS.hub)}
            onSubmit={() => go(SCREENS.success)}
            onCancel={() => go(SCREENS.hub)}
          />
        )}
        {screen === SCREENS.reports && (
          <CyberSafeReports onBack={() => go(SCREENS.hub)} onBackToHub={() => go(SCREENS.hub)} />
        )}
        {screen === SCREENS.success && (
          <CyberSafeSuccess onTrackCase={() => go(SCREENS.reports)} onBackToHub={() => go(SCREENS.hub)} />
        )}
        {screen === SCREENS.scam && (
          <CyberSafeScamDetail scamId={scamId} onBack={() => go(SCREENS.hub)} onReport={() => go(SCREENS.report)} />
        )}
      </motion.div>
    </AnimatePresence>
  );
}

export { SCREENS as CYBERSAFE_SCREENS };
