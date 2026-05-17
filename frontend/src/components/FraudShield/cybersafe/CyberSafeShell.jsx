import React from "react";
import { ArrowLeft } from "lucide-react";

export function CSCard({ children, className = "", accentLeft }) {
  return (
    <div
      className={`rounded-xl border border-white/[0.08] bg-[#1a1d27] ${className}`}
      style={accentLeft ? { borderLeftWidth: 4, borderLeftColor: accentLeft } : undefined}
    >
      {children}
    </div>
  );
}

export function CSBadge({ children, variant = "teal" }) {
  const cls =
    variant === "teal"
      ? "border border-emerald-500/35 bg-emerald-500/15 text-emerald-200"
      : "border border-white/10 bg-white/[0.04] text-gray-300";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium ${cls}`}>
      {children}
    </span>
  );
}

export function CSButton({ children, variant = "primary", onClick, className = "", type = "button", icon: Icon }) {
  const base =
    "inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50";
  const variants = {
    primary: "bg-violet-600 text-white hover:bg-violet-500",
    danger: "bg-[#e24b4a] text-white hover:opacity-90",
    outline: "border border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]",
  };
  return (
    <button type={type} onClick={onClick} className={`${base} ${variants[variant] || variants.primary} ${className}`}>
      {Icon ? <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden /> : null}
      {children}
    </button>
  );
}

export function PageBackRow({ label, onBack }) {
  return (
    <button
      type="button"
      onClick={onBack}
      className="mb-6 inline-flex min-h-[44px] items-center gap-2 text-sm font-medium text-gray-400 transition hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden />
      {label}
    </button>
  );
}
