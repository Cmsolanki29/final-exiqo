import React from "react";
import { motion } from "framer-motion";
import { CalendarDays, Cloud, Compass, MapPin, Sparkles, Wallet } from "lucide-react";
import VerdictBadge from "./VerdictBadge";
import BudgetBreakdown from "./BudgetBreakdown";

const inr = (n) =>
  typeof n === "number"
    ? `₹${Math.round(n).toLocaleString("en-IN")}`
    : "—";

function MetaPill({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-1.5">
      <Icon className="h-3.5 w-3.5 text-cyan-300" aria-hidden />
      <span className="text-[10px] uppercase tracking-[0.12em] text-gray-500">{label}</span>
      <span className="text-xs font-semibold text-white">{value}</span>
    </div>
  );
}

export default function ItineraryCard({ plan }) {
  if (!plan || typeof plan !== "object") return null;
  const {
    verdict,
    destination,
    origin,
    best_month,
    nights,
    travelers,
    total_cost_inr,
    user_savings_inr,
    monthly_surplus_inr,
    shortfall_inr,
    months_to_save,
    weather_summary,
    breakdown,
    itinerary,
    alternatives,
    save_until_date,
  } = plan;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="relative mt-4 overflow-hidden rounded-3xl border border-white/[0.08] bg-gradient-to-br from-[#15102A] to-[#0F0A1F] p-5 shadow-[0_18px_60px_rgba(124,58,237,0.18)] sm:p-6"
    >
      <div
        className="pointer-events-none absolute inset-0 -z-0 opacity-40"
        style={{
          background:
            "radial-gradient(60% 50% at 80% 0%, rgba(124,58,237,0.25), transparent 60%), radial-gradient(50% 40% at 0% 100%, rgba(34,211,238,0.18), transparent 65%)",
        }}
        aria-hidden
      />

      <div className="relative z-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <VerdictBadge verdict={verdict} />
          {best_month ? (
            <span className="text-[11px] uppercase tracking-[0.14em] text-gray-500">
              Best month · <span className="text-white">{best_month}</span>
            </span>
          ) : null}
        </div>

        <h3 className="mt-3 font-heading text-xl font-semibold tracking-tight text-white">
          {origin ? `${origin} → ${destination || "—"}` : destination || "Your trip"}
        </h3>

        {weather_summary ? (
          <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-gray-300">
            <Cloud className="h-3.5 w-3.5 text-cyan-300" aria-hidden />
            {weather_summary}
          </p>
        ) : null}

        <div className="mt-4 flex flex-wrap gap-2">
          {typeof nights === "number" ? (
            <MetaPill icon={CalendarDays} label="Nights" value={nights} />
          ) : null}
          {typeof travelers === "number" ? (
            <MetaPill icon={Sparkles} label="Travelers" value={travelers} />
          ) : null}
          {typeof user_savings_inr === "number" ? (
            <MetaPill icon={Wallet} label="Your savings" value={inr(user_savings_inr)} />
          ) : null}
          {typeof monthly_surplus_inr === "number" ? (
            <MetaPill icon={Wallet} label="Monthly surplus" value={inr(monthly_surplus_inr)} />
          ) : null}
        </div>

        <BudgetBreakdown breakdown={breakdown} total={total_cost_inr} />

        {verdict === "YELLOW" && (typeof shortfall_inr === "number" || save_until_date) ? (
          <div className="mt-4 rounded-2xl border border-amber-500/25 bg-amber-500/[0.06] p-3 text-xs text-amber-100/95">
            <p className="font-semibold uppercase tracking-[0.12em] text-amber-200/80">
              Bridge the gap
            </p>
            <p className="mt-1 text-amber-100/90">
              Shortfall {inr(shortfall_inr)}
              {typeof months_to_save === "number"
                ? ` · about ${months_to_save} month${months_to_save === 1 ? "" : "s"} at your current saving rate`
                : ""}
              {save_until_date ? ` · target ${save_until_date}` : ""}.
            </p>
          </div>
        ) : null}

        {Array.isArray(itinerary) && itinerary.length > 0 ? (
          <div className="mt-5">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500">
              Day-by-day plan
            </p>
            <ol className="space-y-2.5">
              {itinerary.map((day, idx) => (
                <li
                  key={day?.day ?? idx}
                  className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3"
                >
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <span className="grid h-6 w-6 place-items-center rounded-md bg-gradient-to-br from-violet-500/30 to-cyan-500/20 text-[10px] font-bold tabular-nums text-white">
                      {day?.day ?? idx + 1}
                    </span>
                    {day?.title || "Highlights"}
                  </div>
                  {Array.isArray(day?.activities) && day.activities.length > 0 ? (
                    <ul className="mt-2 space-y-1 text-xs text-gray-300">
                      {day.activities.slice(0, 6).map((a, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <Compass className="mt-0.5 h-3 w-3 shrink-0 text-cyan-300" aria-hidden />
                          <span>{a}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ol>
          </div>
        ) : null}

        {verdict === "RED" && Array.isArray(alternatives) && alternatives.length > 0 ? (
          <div className="mt-5">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500">
              Cheaper alternatives near you
            </p>
            <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-1 scrollbar-thin scrollbar-thumb-white/10">
              {alternatives.map((alt, idx) => (
                <div
                  key={alt?.name || idx}
                  className="min-w-[200px] shrink-0 rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3"
                >
                  <div className="flex items-center gap-1.5 text-sm font-semibold text-white">
                    <MapPin className="h-3.5 w-3.5 text-emerald-300" aria-hidden />
                    <span className="truncate">{alt?.name || "Option"}</span>
                  </div>
                  {alt?.why ? (
                    <p className="mt-1 line-clamp-3 text-xs text-gray-300">{alt.why}</p>
                  ) : null}
                  {typeof alt?.est_cost_inr === "number" ? (
                    <p className="mt-2 text-xs font-semibold text-emerald-200 tabular-nums">
                      ~{inr(alt.est_cost_inr)} total
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}
