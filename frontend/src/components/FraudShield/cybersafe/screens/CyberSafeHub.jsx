import React from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Clock,
  FileWarning,
  Globe,
  MessageSquare,
  Phone,
  Shield,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { CYBERCELL_ID, SCAM_CARDS } from "../constants";
import { CSBadge, CSButton, CSCard } from "../CyberSafeShell";

const SCAM_ICONS = { Smartphone, MessageSquare, FileWarning };

export default function CyberSafeHub({ onReport, onViewReports, onScamDetail }) {
  return (
    <motion.div
      className="space-y-6"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <CSCard className="p-5">
          <motion.div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" aria-hidden />
              <span className="text-sm font-semibold text-white">Cybercell — Active Link</span>
            </div>
            <CSBadge variant="teal">Verified</CSBadge>
          </motion.div>
          <p className="mt-3 text-sm text-gray-400">
            National Cybercrime Portal · ID: {CYBERCELL_ID}
          </p>
        </CSCard>

        <CSCard className="p-5" accentLeft="#854f0b">
          <div className="flex gap-3">
            <Clock className="h-5 w-5 shrink-0 text-amber-400" strokeWidth={1.75} />
            <p className="text-sm leading-relaxed text-amber-100/90">
              Report within 24 hours of fraud for maximum chance of money recovery by Cybercell.
            </p>
          </div>
        </CSCard>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <CSButton variant="danger" icon={AlertTriangle} onClick={onReport}>
          Report a Fraud Now
        </CSButton>
        <CSButton variant="outline" onClick={onViewReports}>
          View my reports
        </CSButton>
      </div>

      <section>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-gray-500">
          Scam awareness
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {SCAM_CARDS.map((card) => {
            const Icon = SCAM_ICONS[card.icon] || Smartphone;
            return (
              <CSCard key={card.id} className="flex h-full flex-col p-5">
                <Icon className="mb-3 h-6 w-6 text-violet-400" strokeWidth={1.75} />
                <p className="text-base font-semibold text-white">{card.title}</p>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-gray-400">{card.description}</p>
                <button
                  type="button"
                  onClick={() => onScamDetail(card.id)}
                  className="mt-4 text-left text-sm font-medium text-violet-400 transition hover:text-violet-300"
                >
                  Learn more →
                </button>
              </CSCard>
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-white">How Cybercell helps you</h2>
        <CSCard className="divide-y divide-white/[0.06]">
          {[
            { Icon: Phone, text: "Dial 1930 — 24x7 national cybercrime helpline" },
            { Icon: Globe, text: "cybercrime.gov.in — submit your complaint online" },
            { Icon: Shield, text: "Bank account freeze initiated within hours of your report" },
          ].map((row, i) => (
            <div key={i} className="flex items-center gap-4 p-5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10">
                <row.Icon className="h-5 w-5 text-emerald-300" strokeWidth={1.75} />
              </div>
              <p className="text-sm text-gray-300">{row.text}</p>
            </div>
          ))}
        </CSCard>
      </section>

      <div className="flex items-center gap-3 rounded-xl border border-white/[0.08] bg-[#1a1d27]/80 px-4 py-3">
        <ShieldCheck className="h-5 w-5 shrink-0 text-emerald-400" strokeWidth={1.75} />
        <p className="text-sm text-gray-400">
          Your SmartSpend account is pre-linked with Cybercell — report fraud in one click.
        </p>
      </div>
    </motion.div>
  );
}
