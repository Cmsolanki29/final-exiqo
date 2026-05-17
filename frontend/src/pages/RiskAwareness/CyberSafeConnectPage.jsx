import React, { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../../components/Dashboard/shared/PageHeader";
import CyberSafeConnect, { CYBERSAFE_SCREENS } from "../../components/FraudShield/cybersafe/CyberSafeConnect";

const ACCENT = "#0f6e56";

const HEADER_BY_SCREEN = {
  [CYBERSAFE_SCREENS.hub]: {
    title: "Report fraud to Cybercell",
    subtitle:
      "Pre-linked with the National Cybercrime Portal. Report within 24 hours for the best chance of recovery.",
  },
  [CYBERSAFE_SCREENS.report]: {
    title: "Report fraud",
    subtitle: "Review auto-filled details before submitting to Cybercell.",
  },
  [CYBERSAFE_SCREENS.reports]: {
    title: "My reports",
    subtitle: "Track investigation progress and case timeline.",
  },
  [CYBERSAFE_SCREENS.success]: {
    title: "Report submitted",
    subtitle: "Your complaint has been sent to Cybercell.",
  },
  [CYBERSAFE_SCREENS.scam]: {
    title: "Scam awareness",
    subtitle: "Learn how to protect yourself and when to report.",
  },
};

export default function CyberSafeConnectPage() {
  const [screen, setScreen] = useState(CYBERSAFE_SCREENS.hub);
  const header = HEADER_BY_SCREEN[screen] || HEADER_BY_SCREEN[CYBERSAFE_SCREENS.hub];

  const onScreenChange = useCallback((next) => {
    setScreen(next);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [screen]);

  return (
    <div className="w-full">
      <PageHeader
        eyebrow="RISK AWARENESS · CYBERSAFE CONNECT"
        title={header.title}
        subtitle={header.subtitle}
        accentHex={ACCENT}
      />
      <CyberSafeConnect onScreenChange={onScreenChange} />
    </div>
  );
}
