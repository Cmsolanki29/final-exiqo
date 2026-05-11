import React from "react";
import { motion } from "framer-motion";
import { TrendingDown, TrendingUp } from "lucide-react";

const VARIANTS = {
  default: {
    gradient:
      "from-exiqo-purple/25 via-exiqo-dark/90 to-exiqo-purple/10",
    border: "border-exiqo-purple/35",
    glow: "shadow-exiqo-card hover:shadow-purple-glow",
    iconBg: "from-exiqo-purple to-exiqo-dark-purple",
    accent: "text-exiqo-glow",
  },
  success: {
    gradient:
      "from-emerald-500/20 via-exiqo-dark/90 to-emerald-500/10",
    border: "border-emerald-500/35",
    glow: "shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/35",
    iconBg: "from-emerald-500 to-emerald-700",
    accent: "text-emerald-300",
  },
  warning: {
    gradient:
      "from-amber-500/20 via-exiqo-dark/90 to-amber-500/10",
    border: "border-amber-500/35",
    glow: "shadow-lg shadow-amber-500/20 hover:shadow-amber-500/35",
    iconBg: "from-amber-500 to-orange-600",
    accent: "text-amber-300",
  },
  danger: {
    gradient:
      "from-rose-500/20 via-exiqo-dark/90 to-rose-500/10",
    border: "border-rose-500/35",
    glow: "shadow-lg shadow-rose-500/20 hover:shadow-rose-500/35",
    iconBg: "from-rose-500 to-red-600",
    accent: "text-rose-300",
  },
};

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
  variant = "default",
}) {
  const cfg = VARIANTS[variant] || VARIANTS.default;

  return (
    <motion.div
      whileHover={{ y: -6, scale: 1.015 }}
      transition={{ type: "spring", stiffness: 420, damping: 22 }}
      className={`relative overflow-hidden rounded-3xl border ${cfg.border} bg-gradient-to-br ${cfg.gradient} p-5 backdrop-blur-xl ${cfg.glow} transition-all duration-300`}
    >
      <motion.div
        aria-hidden
        animate={{ scale: [1, 1.15, 1], opacity: [0.25, 0.45, 0.25] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
        className={`pointer-events-none absolute -right-16 -top-16 h-52 w-52 rounded-full bg-gradient-to-br ${cfg.iconBg} opacity-25 blur-3xl`}
      />

      <div className="relative z-10 mb-3 flex items-start justify-between gap-3">
        <div
          className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${cfg.iconBg} shadow-lg shadow-black/30`}
        >
          {Icon ? <Icon className="h-6 w-6 text-white" /> : null}
        </div>
        {trend && trendValue ? (
          <div
            className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
              trend === "up"
                ? "bg-emerald-500/20 text-emerald-300"
                : trend === "down"
                  ? "bg-rose-500/20 text-rose-300"
                  : "bg-slate-500/20 text-slate-300"
            }`}
          >
            {trend === "up" ? (
              <TrendingUp className="h-3.5 w-3.5" />
            ) : trend === "down" ? (
              <TrendingDown className="h-3.5 w-3.5" />
            ) : null}
            <span>{trendValue}</span>
          </div>
        ) : null}
      </div>

      <div className="relative z-10">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-exiqo-glow/70">
          {title}
        </p>
        <h3 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          {value}
        </h3>
        {subtitle ? (
          <p className={`mt-1 text-sm font-medium ${cfg.accent}`}>{subtitle}</p>
        ) : null}
      </div>

      <div className="pointer-events-none absolute bottom-0 right-0 h-28 w-28 rounded-tl-full bg-gradient-to-tl from-white/[0.06] to-transparent" />
    </motion.div>
  );
}
