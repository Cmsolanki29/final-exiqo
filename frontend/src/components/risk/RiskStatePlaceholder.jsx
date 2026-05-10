/**
 * RiskStatePlaceholder — shows a loading skeleton, an error card,
 * or an "offline/not-available" state for any risk component.
 *
 * Props:
 *   loading  {bool}
 *   error    {Error|null}
 *   empty    {bool}         — data loaded but list is empty
 *   message  {string}       — custom text (overrides defaults)
 *   compact  {bool}         — small inline variant
 */

import React from "react";
import { motion } from "framer-motion";
import { ShieldOff, Loader2, WifiOff, Inbox } from "lucide-react";

function SkeletonBar({ w = "100%", h = "h-3" }) {
  return (
    <div
      className={`${h} rounded-full bg-gray-200 animate-pulse`}
      style={{ width: w }}
    />
  );
}

export function RiskStatePlaceholder({
  loading = false,
  error   = null,
  empty   = false,
  message = null,
  compact = false,
}) {
  const base = compact
    ? "flex items-center gap-2 px-3 py-2 rounded-lg text-sm"
    : "flex flex-col items-center justify-center gap-3 p-6 rounded-xl text-sm";

  if (loading) {
    if (compact) {
      return (
        <div className={`${base} bg-gray-50`}>
          <Loader2 size={14} className="animate-spin text-gray-400" />
          <span className="text-gray-400">Loading…</span>
        </div>
      );
    }
    return (
      <div className="space-y-2 p-4">
        <SkeletonBar w="75%" />
        <SkeletonBar w="55%" />
        <SkeletonBar w="85%" />
      </div>
    );
  }

  if (error) {
    const isOffline =
      error.message?.includes("Network Error") ||
      error.message?.includes("not yet available");

    return (
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className={`${base} bg-gray-50 text-gray-500 border border-gray-100`}
      >
        {isOffline ? (
          <WifiOff size={compact ? 14 : 20} className="text-gray-400 shrink-0" />
        ) : (
          <ShieldOff size={compact ? 14 : 20} className="text-gray-400 shrink-0" />
        )}
        <span>{message || (isOffline ? "Risk engine offline" : "Data unavailable")}</span>
      </motion.div>
    );
  }

  if (empty) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={`${base} bg-gray-50 text-gray-400 border border-dashed border-gray-200`}
      >
        <Inbox size={compact ? 14 : 20} className="shrink-0" />
        <span>{message || "No data yet"}</span>
      </motion.div>
    );
  }

  return null;
}
