import React, { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, CreditCard, Gift, ShieldAlert, Smartphone } from "lucide-react";

const CARDS = [
  {
    id: "kyc",
    title: "KYC fraud",
    subtitle: "Fake “bank” verification",
    body: "Scammers pose as RBI/SBI and ask you to pay a fee or send money to “complete KYC”. Banks never ask for UPI transfers to verify identity.",
    tip: "Use only your official app or branch. Ignore links in SMS.",
    Icon: ShieldAlert,
    accent: "from-rose-500/25 to-violet-600/15 border-rose-500/30",
  },
  {
    id: "lottery",
    title: "Lottery & prize scams",
    subtitle: "You “won” — pay first",
    body: "A small “tax”, “processing fee”, or “unlock charge” before a fake prize is released. Real lotteries do not collect fees over random UPI IDs.",
    tip: "If you did not enter a contest, you did not win.",
    Icon: Gift,
    accent: "from-amber-500/25 to-orange-600/15 border-amber-500/35",
  },
  {
    id: "collect",
    title: "UPI collect requests",
    subtitle: "You approve = you pay",
    body: "Fraudsters send collect requests that look like refunds or COD. Approving debits your account instantly — often non-reversible.",
    tip: "Read the payer name & amount twice. Decline unknown collects.",
    Icon: Smartphone,
    accent: "from-cyan-500/20 to-blue-600/15 border-cyan-500/30",
  },
  {
    id: "rupee1",
    title: "The ₹1 trap",
    subtitle: "“Just verify” your UPI",
    body: "A ₹1 or tiny debit is used to test stolen credentials or to start a grooming chain. Combined with phishing, it escalates fast.",
    tip: "Never “verify” your account by sending money to strangers.",
    Icon: CreditCard,
    accent: "from-violet-500/25 to-fuchsia-600/15 border-violet-500/35",
  },
];

export default function FraudEducationSwipe() {
  const [index, setIndex] = useState(0);
  const n = CARDS.length;
  const go = useCallback(
    (dir) => {
      setIndex((i) => (i + dir + n) % n);
    },
    [n]
  );

  const card = CARDS[index];
  const Icon = card.Icon;

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5 shadow-[0_0_40px_-20px_rgba(124,58,237,0.35)] backdrop-blur-xl sm:p-6">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-gray-500">Fraud education</p>
          <h3 className="mt-1 text-lg font-bold tracking-tight text-white">Swipe through 4 red flags</h3>
          <p className="mt-1 max-w-xl text-xs text-gray-400">Built for India — KYC, lottery, collect, and ₹1 verification patterns.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Previous tip"
            onClick={() => go(-1)}
            className="grid h-10 w-10 place-items-center rounded-xl border border-white/15 bg-white/[0.06] text-white transition hover:bg-white/10"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <button
            type="button"
            aria-label="Next tip"
            onClick={() => go(1)}
            className="grid h-10 w-10 place-items-center rounded-xl border border-white/15 bg-white/[0.06] text-white transition hover:bg-white/10"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="relative min-h-[220px] overflow-hidden sm:min-h-[200px]">
        <AnimatePresence mode="wait" initial={false}>
          <motion.article
            key={card.id}
            initial={{ opacity: 0, x: 28 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ type: "spring", stiffness: 380, damping: 34 }}
            className={`rounded-2xl border bg-gradient-to-br p-6 sm:p-7 ${card.accent} backdrop-blur-md`}
          >
            <div className="flex flex-wrap items-start gap-4">
              <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl border border-white/15 bg-black/25 text-white shadow-inner">
                <Icon className="h-7 w-7" aria-hidden />
              </div>
              <div className="min-w-0 flex-1">
                <h4 className="text-xl font-bold tracking-tight text-white">{card.title}</h4>
                <p className="mt-0.5 text-sm font-medium text-gray-400">{card.subtitle}</p>
                <p className="mt-3 text-sm leading-relaxed text-gray-300">{card.body}</p>
                <p className="mt-4 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs font-medium text-cyan-100/90">
                  <span className="text-cyan-300/90">Tip:</span> {card.tip}
                </p>
              </div>
            </div>
          </motion.article>
        </AnimatePresence>
      </div>

      <div className="mt-5 flex snap-x snap-mandatory gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {CARDS.map((c, i) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setIndex(i)}
            className={`snap-center shrink-0 rounded-xl border px-3 py-2 text-left text-[11px] font-semibold transition ${
              i === index
                ? "border-violet-400/50 bg-violet-500/20 text-white shadow-[0_0_20px_-8px_rgba(124,58,237,0.5)]"
                : "border-white/10 bg-white/[0.04] text-gray-400 hover:border-white/20 hover:text-white"
            }`}
          >
            {c.title}
          </button>
        ))}
      </div>

      <div className="mt-3 flex justify-center gap-1.5">
        {CARDS.map((c, i) => (
          <button
            key={c.id}
            type="button"
            aria-label={`Go to card ${i + 1}`}
            onClick={() => setIndex(i)}
            className={`h-2 rounded-full transition-all ${i === index ? "w-6 bg-violet-400" : "w-2 bg-white/20 hover:bg-white/35"}`}
          />
        ))}
      </div>
    </div>
  );
}
