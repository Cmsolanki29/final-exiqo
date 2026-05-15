/**
 * MonthYearPicker — Premium period selector overlay.
 *
 * Z-INDEX / OPACITY LAYERING (keep consistent with CommandPalette & UserMenu):
 * ─────────────────────────────────────────────────────────────────────────────
 *  z-40  Backdrop  → fixed inset-0, bg-black/60 backdrop-blur-md
 *                    Dims + blurs the page. Click closes the picker.
 *  z-50  Picker    → bg-[#0B0716]  ← FULLY SOLID. Zero alpha on container.
 *                    NO backdrop-blur on this element — causes content bleed.
 * ─────────────────────────────────────────────────────────────────────────────
 *  Portal at document.body — avoids TopBar's sticky z-40 stacking context.
 *  Position is calculated from the trigger button rect on open (same pattern
 *  as UserMenu) so it anchors correctly at any scroll position.
 */
import React, { useEffect, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import useEscapeKey from "../../hooks/useEscapeKey";
import useClickOutside from "../../hooks/useClickOutside";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function useLockBodyScroll(active) {
  useEffect(() => {
    if (!active) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [active]);
}

const MonthYearPicker = ({
  open,
  onClose,
  triggerRef,        // ref to the trigger button in TopBar
  month,             // 1-based
  year,
  onMonthChange,
  onYearChange,
}) => {
  const pickerRef = useRef(null);
  const [pos, setPos] = useState({ top: 0, right: 0 });

  const currentYear = new Date().getFullYear();
  const yearOptions = [currentYear - 2, currentYear - 1, currentYear, currentYear + 1, currentYear + 2];

  const todayMonth = new Date().getMonth() + 1;
  const todayYear  = new Date().getFullYear();

  useEscapeKey(open, onClose);
  useClickOutside([pickerRef, triggerRef], open ? onClose : null);
  useLockBodyScroll(open);

  // Anchor to trigger button
  useEffect(() => {
    if (!open || !triggerRef?.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setPos({
      top:   rect.bottom + 8,
      right: Math.max(8, window.innerWidth - rect.right),
    });
  }, [open, triggerRef]);

  const handleMonth = useCallback((m) => {
    onMonthChange?.(m);
    // Small delay so user sees selection highlight before close
    setTimeout(onClose, 120);
  }, [onMonthChange, onClose]);

  const handleYear = useCallback((y) => {
    onYearChange?.(y);
  }, [onYearChange]);

  const goToToday = useCallback(() => {
    onMonthChange?.(todayMonth);
    onYearChange?.(todayYear);
    setTimeout(onClose, 150);
  }, [onMonthChange, onYearChange, todayMonth, todayYear, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/*
           * LAYER 1 — Backdrop  z-40
           * backdrop-blur-md + bg-black/60 dims and blurs the page.
           * The blur lives here — NEVER on the picker container.
           */}
          <motion.div
            key="period-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-md"
            aria-hidden
          />

          {/*
           * LAYER 2 — Picker  z-50
           * bg-[#0B0716] is FULLY SOLID — no /XX alpha, no backdrop-blur.
           * A solid colour blocks everything behind it completely.
           */}
          <motion.div
            key="period-picker"
            ref={pickerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Select month and year"
            initial={{ opacity: 0, scale: 0.96, y: -6 }}
            animate={{ opacity: 1, scale: 1,    y:  0 }}
            exit={{    opacity: 0, scale: 0.96, y: -4 }}
            transition={{ type: "spring", stiffness: 500, damping: 30 }}
            style={{ top: pos.top, right: pos.right }}
            className={[
              // Positioning via JS-anchored fixed
              "fixed z-50",
              // Width — 440px desktop, constrained on small screens
              "w-[min(440px,calc(100vw-2rem))]",
              // ✅ SOLID background — blocks all content behind
              "bg-[#0B0716]",
              "overflow-hidden rounded-2xl",
              "border border-purple-500/20",
              "shadow-[0_20px_70px_-10px_rgba(139,92,246,0.3)]",
            ].join(" ")}
          >
            {/* ── Gradient top-border accent ─────────────────────── */}
            <div
              className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-purple-500/50 to-transparent"
              aria-hidden
            />

            {/* ── Column headers ────────────────────────────────── */}
            <div className="grid grid-cols-[1fr_1px_1fr] border-b border-white/10">
              <p className="px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-gray-500">
                Month
              </p>
              <div className="bg-white/10" aria-hidden />
              <p className="px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-gray-500">
                Year
              </p>
            </div>

            {/* ── Body ──────────────────────────────────────────── */}
            <div className="grid grid-cols-[1fr_1px_1fr]">

              {/* Month grid */}
              <div className="grid grid-cols-3 gap-1.5 p-4">
                {MONTHS.map((m, idx) => {
                  const mNum     = idx + 1;
                  const selected = mNum === Number(month);
                  const isToday  = mNum === todayMonth && Number(year) === todayYear;

                  return (
                    <button
                      key={m}
                      type="button"
                      role="button"
                      aria-pressed={selected}
                      onClick={() => handleMonth(mNum)}
                      className={[
                        "relative rounded-lg px-2 py-2.5 text-sm font-medium",
                        "cursor-pointer transition-all duration-150",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/50",
                        selected
                          ? "bg-gradient-to-br from-purple-500 to-violet-600 text-white font-semibold shadow-lg shadow-purple-500/30"
                          : isToday
                            ? "bg-white/[0.04] text-white ring-1 ring-purple-400/40 hover:bg-white/[0.08]"
                            : "bg-white/[0.03] text-gray-300 hover:bg-white/[0.08] hover:text-white",
                      ].join(" ")}
                    >
                      {m}
                    </button>
                  );
                })}
              </div>

              {/* Vertical divider */}
              <div className="bg-white/10" aria-hidden />

              {/* Year list */}
              <div className="flex flex-col gap-1.5 p-4">
                {yearOptions.map((y) => {
                  const selected = y === Number(year);
                  const isToday  = y === todayYear;

                  return (
                    <button
                      key={y}
                      type="button"
                      role="button"
                      aria-pressed={selected}
                      onClick={() => handleYear(y)}
                      className={[
                        "rounded-lg px-3 py-2.5 text-sm font-medium tabular-nums",
                        "cursor-pointer transition-all duration-150 text-center",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/50",
                        selected
                          ? "bg-gradient-to-br from-purple-500 to-violet-600 text-white font-semibold shadow-lg shadow-purple-500/30"
                          : isToday
                            ? "bg-white/[0.04] text-white ring-1 ring-purple-400/40 hover:bg-white/[0.08]"
                            : "bg-white/[0.03] text-gray-300 hover:bg-white/[0.08] hover:text-white",
                      ].join(" ")}
                    >
                      {y}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* ── Footer ────────────────────────────────────────── */}
            <div className="flex items-center justify-between border-t border-white/10 px-4 py-3">
              <button
                type="button"
                onClick={goToToday}
                className="text-xs font-medium text-purple-300 transition-colors hover:text-purple-200 focus-visible:outline-none"
              >
                Today
              </button>
              <span className="text-[11px] text-gray-500">
                <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-gray-500">
                  ESC
                </kbd>
                {" "}to close
              </span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default MonthYearPicker;
