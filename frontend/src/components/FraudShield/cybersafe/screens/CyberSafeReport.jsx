import React from "react";
import { motion } from "framer-motion";
import { Clock, Lock } from "lucide-react";
import { CSButton, CSCard, PageBackRow } from "../CyberSafeShell";

const FIELDS = [
  { label: "Fraudulent transaction", value: "₹12,500 · UPI · 14 May 2025, 3:41 PM" },
  { label: "Scammer UPI / account", value: "scam-upi@fraudbank" },
  { label: "Your bank account", value: "HDFC Bank · XXXX 4821" },
  { label: "Your registered mobile", value: "+91 98XXX XXXXX" },
];

export default function CyberSafeReport({ onBack, onSubmit, onCancel }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22 }}
    >
      <PageBackRow label="Back to CyberSafe Connect" onBack={onBack} />

      <CSCard className="mb-6 p-5" accentLeft="#854f0b">
        <div className="flex gap-3">
          <Clock className="h-5 w-5 shrink-0 text-amber-400" strokeWidth={1.75} />
          <p className="text-sm leading-relaxed text-amber-100/90">
            24-hour window active — Report abhi karein, paise wapas aane ke chances highest hain
          </p>
        </div>
      </CSCard>

      <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-gray-500">
        Auto-filled from your account
      </p>

      <div className="mb-6 grid gap-3 lg:grid-cols-2">
        {FIELDS.map((f) => (
          <CSCard key={f.label} className="p-4">
            <p className="text-[11px] font-medium uppercase tracking-wide text-gray-500">{f.label}</p>
            <p className="mt-1 text-sm font-medium text-white">{f.value}</p>
          </CSCard>
        ))}
      </div>

      <CSCard className="mb-8 flex gap-3 p-4">
        <Lock className="h-5 w-5 shrink-0 text-emerald-400" strokeWidth={1.75} />
        <p className="text-sm leading-relaxed text-gray-400">
          Yeh details seedha National Cybercrime Portal (cybercrime.gov.in) ko encrypted bheja jayega.
        </p>
      </CSCard>

      <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
        <CSButton variant="outline" className="sm:max-w-[200px]" onClick={onCancel}>
          Cancel
        </CSButton>
        <CSButton className="sm:max-w-[280px]" onClick={onSubmit}>
          Submit to Cybercell →
        </CSButton>
      </div>
    </motion.div>
  );
}
