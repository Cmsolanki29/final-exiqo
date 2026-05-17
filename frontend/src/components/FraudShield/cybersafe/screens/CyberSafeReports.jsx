import React from "react";
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { CASE_REF, TIMELINE_STEPS } from "../constants";
import { CSBadge, CSButton, CSCard, PageBackRow } from "../CyberSafeShell";

export default function CyberSafeReports({ onBack, onBackToHub }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }}>
      <PageBackRow label="Back to CyberSafe Connect" onBack={onBack} />

      <CSCard className="mb-8 p-5 transition-colors hover:border-white/[0.12]">
        <DIV className="flex flex-wrap items-start justify-between gap-3 border-b border-white/[0.06] pb-4">
          <DIV className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" aria-hidden />
            <span className="font-semibold text-white">Case #{CASE_REF}</span>
          </DIV>
          <CSBadge variant="teal">Active</CSBadge>
        </DIV>
        <DIV className="mt-4 flex flex-wrap items-center justify-between gap-4 text-sm">
          <span className="text-gray-400">Submitted 14 May ? ?12,500</span>
          <span className="text-gray-500">UPI fraud</span>
        </DIV>
        <DIV className="mt-6">
          <DIV className="mb-2 flex items-center justify-between text-xs">
            <span className="font-medium text-gray-400">Investigation progress</span>
            <span className="text-gray-500">45%</span>
          </DIV>
          <DIV className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
            <DIV className="h-full w-[45%] rounded-full bg-emerald-500" />
          </DIV>
          <p className="mt-2 text-xs text-gray-500">Bank freeze requested ? Awaiting confirmation</p>
        </DIV>
      </CSCard>

      <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.14em] text-gray-500">Timeline</h2>

      <CSCard className="mb-8 p-5">
        <ul className="space-y-0">
          {TIMELINE_STEPS.map((step, idx) => (
            <li key={step.id} className="flex gap-4">
              <DIV className="flex flex-col items-center">
                <DIV
                  className={
                    step.done
                      ? "flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-xs font-semibold text-white"
                      : "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-xs font-semibold text-gray-500"
                  }
                >
                  {step.done ? <Check className="h-4 w-4" strokeWidth={2} /> : step.id}
                </DIV>
                {idx < TIMELINE_STEPS.length - 1 ? (
                  <DIV className="my-1 w-px flex-1 min-h-[28px] bg-white/[0.08]" />
                ) : null}
              </DIV>
              <DIV className="pb-6 pt-1">
                <p className="text-sm font-medium text-white">{step.title}</p>
                <p className="mt-0.5 text-xs text-gray-500">{step.time}</p>
              </DIV>
            </li>
          ))}
        </ul>
      </CSCard>

      <CSButton variant="outline" className="max-w-xs" onClick={onBackToHub}>
        Back to CyberSafe Connect
      </CSButton>
    </motion.div>
  );
}

const DIV = "div";
