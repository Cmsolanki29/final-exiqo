import React from "react";
import { motion } from "framer-motion";
import { CheckCircle2, MessageSquare, Phone } from "lucide-react";
import { CASE_REF } from "../constants";
import { CSButton, CSCard, PageBackRow } from "../CyberSafeShell";

export default function CyberSafeSuccess({ onTrackCase, onBackToHub }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.25 }}
    >
      <PageBackRow label="Back to CyberSafe Connect" onBack={onBackToHub} />

      <CSCard className="p-8 text-center md:p-10">
        <CheckCircle2 className="mx-auto h-16 w-16 text-emerald-400" strokeWidth={1.25} />
        <h2 className="mt-6 text-2xl font-semibold text-white">Report submitted!</h2>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-gray-400">
          Aapki complaint Cybercell ko bhej di gayi hai. Woh abhi account freeze karne ki process shuru karenge.
        </p>

        <div className="mx-auto mt-8 max-w-sm rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-5">
          <p className="text-xs text-gray-500">Your case reference number</p>
          <p className="mt-2 font-mono text-2xl font-semibold tracking-wide text-emerald-300">{CASE_REF}</p>
        </div>

        <div className="mx-auto mt-8 max-w-md space-y-4 text-left">
          <div className="flex gap-3">
            <Phone className="h-5 w-5 shrink-0 text-emerald-400" strokeWidth={1.75} />
            <p className="text-sm text-gray-400">
              Cybercell Helpline: <span className="text-white">1930</span> (24x7 available)
            </p>
          </div>
          <div className="flex gap-3">
            <MessageSquare className="h-5 w-5 shrink-0 text-emerald-400" strokeWidth={1.75} />
            <p className="text-sm leading-relaxed text-gray-400">
              Aapko SMS aur app notification milega jab bank account freeze confirm ho jayega.
            </p>
          </div>
        </div>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <CSButton className="sm:max-w-[220px]" onClick={onTrackCase}>
            Track my case
          </CSButton>
          <CSButton variant="outline" className="sm:max-w-[220px]" onClick={onBackToHub}>
            Back to CyberSafe Connect
          </CSButton>
        </div>
      </CSCard>
    </motion.div>
  );
}
