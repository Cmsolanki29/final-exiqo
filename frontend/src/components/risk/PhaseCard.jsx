/**
 * PhaseCard — one card per phase (1-8) in the Trust Center.
 * Shows phase number, title, subtitle, description, and key metrics.
 */

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Zap, Database, Brain, Settings2, RefreshCw, Network, BarChart2, MessageSquare,
  Bot, Share2, Layers, GitMerge,
  ChevronDown,
} from "lucide-react";

const ICONS = {
  Zap, Database, Brain, Settings2, RefreshCw, Network, BarChart2, MessageSquare,
  Bot, Share2, Layers, GitMerge,
};

export function PhaseCard({ phase, index }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = ICONS[phase.icon] || Zap;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left p-4 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-start gap-3">
          {/* Phase number badge */}
          <div
            className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold text-white shadow-sm"
            style={{ background: phase.color }}
          >
            {phase.id}
          </div>

          {/* Icon */}
          <div
            className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: phase.bg }}
          >
            <Icon size={18} style={{ color: phase.color }} />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h4 className="font-semibold text-gray-900 text-sm">{phase.title}</h4>
              <div className="flex items-center gap-1 shrink-0">
                {phase.badge && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-50 text-purple-600 font-bold border border-purple-100 uppercase tracking-wider">
                    {phase.badge}
                  </span>
                )}
                {phase.adminOnly && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-50 text-orange-500 font-medium border border-orange-100">
                    Admin
                  </span>
                )}
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">{phase.subtitle}</p>
          </div>

          <motion.div
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="flex-shrink-0 mt-1"
          >
            <ChevronDown size={16} className="text-gray-400" />
          </motion.div>
        </div>

        {/* Metric pills (always visible) */}
        <div className="mt-3 flex flex-wrap gap-1.5 pl-[4.5rem]">
          {phase.metrics.map((m) => (
            <span
              key={m}
              className="text-[10px] px-2 py-0.5 rounded-full font-medium border"
              style={{ background: phase.bg, color: phase.color, borderColor: `${phase.color}30` }}
            >
              {m}
            </span>
          ))}
        </div>
      </button>

      {/* Expandable description */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-4 pb-4 pt-0 border-t border-gray-50">
              <p className="text-sm text-gray-500 leading-relaxed mt-3 pl-[4.5rem]">
                {phase.description}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
