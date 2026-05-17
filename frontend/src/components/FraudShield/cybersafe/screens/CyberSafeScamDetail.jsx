import React from "react";
import { motion } from "framer-motion";
import { AlertTriangle, FileWarning, MessageSquare, Shield, Smartphone } from "lucide-react";
import { SCAM_CARDS } from "../constants";
import { CSButton, CSCard, PageBackRow } from "../CyberSafeShell";

const ICONS = { Smartphone, MessageSquare, FileWarning };

const TIPS = {
  "upi-fraud": [
    "Never scan QR codes from unknown senders asking for payment.",
    "Verify UPI IDs on your bank app before sending money.",
    "Decline collect requests from strangers — legitimate refunds never need upfront payment.",
  ],
  "otp-scam": [
    "Banks never ask for OTP over phone or WhatsApp.",
    "If someone pressures you to share OTP, hang up immediately.",
    "Enable SMS alerts for every transaction on your account.",
  ],
  "fake-kyc": [
    "Only use official bank apps or cybercrime.gov.in for KYC.",
    "Ignore links in SMS claiming your account will be blocked.",
    "Report phishing pages to Cybercell via 1930 or the portal.",
  ],
};

export default function CyberSafeScamDetail({ scamId, onBack, onReport }) {
  const card = SCAM_CARDS.find((c) => c.id === scamId) || SCAM_CARDS[0];
  const Icon = ICONS[card.icon] || Smartphone;
  const tips = TIPS[card.id] || TIPS["upi-fraud"];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22 }}
    >
      <PageBackRow label="Back to CyberSafe Connect" onBack={onBack} />

      <div className="mb-6 flex items-start gap-4">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-violet-500/15">
          <Icon className="h-7 w-7 text-violet-400" strokeWidth={1.75} />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-white">{card.title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-gray-400">{card.description}</p>
        </div>
      </div>

      <CSCard className="mb-6 flex gap-3 p-5" accentLeft="#e24b4a">
        <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400" strokeWidth={1.75} />
        <p className="text-sm leading-relaxed text-gray-300">
          If you have already lost money, report immediately — Cybercell can freeze accounts within hours when
          reported within 24 hours.
        </p>
      </CSCard>

      <section className="mb-8">
        <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
          <Shield className="h-5 w-5 text-emerald-400" strokeWidth={1.75} />
          Stay safe
        </h3>
        <CSCard className="divide-y divide-white/[0.06]">
          {tips.map((tip, i) => (
            <p key={i} className="p-5 text-sm leading-relaxed text-gray-400">
              {tip}
            </p>
          ))}
        </CSCard>
      </section>

      <CSButton variant="danger" icon={AlertTriangle} className="max-w-md" onClick={onReport}>
        Report a Fraud Now
      </CSButton>
    </motion.div>
  );
}
