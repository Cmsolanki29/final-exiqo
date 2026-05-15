/**
 * UserMenu — Profile avatar chip + dropdown with backdrop.
 *
 * Z-INDEX / OPACITY LAYERING (read before touching):
 * ─────────────────────────────────────────────────────────────────────────────
 *  z-40  Backdrop  → fixed inset-0, bg-black/40 backdrop-blur-sm
 *                    Dims the page softly. Clicking it closes the menu.
 *  z-50  Dropdown  → bg-[#0B0716]  ← FULLY SOLID. No /XX alpha on container.
 *                    Never add backdrop-blur to this element — it causes the
 *                    page content to bleed through regardless of opacity.
 * ─────────────────────────────────────────────────────────────────────────────
 *  Portal at document.body avoids stacking-context and overflow-hidden issues
 *  from parent elements in the TopBar.
 */
import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronDown, ExternalLink, HelpCircle, LogOut, UserCircle, Zap,
} from "lucide-react";
import useEscapeKey from "../../hooks/useEscapeKey";
import useClickOutside from "../../hooks/useClickOutside";

// ─── Menu catalogue ───────────────────────────────────────────────────────────
const MENU_ITEMS = [
  {
    id: "settings",
    label: "Account & Settings",
    icon: UserCircle,
    description: "Profile, preferences & config",
  },
  null, // ── divider ──
  {
    id: "_help",
    label: "Help & Support",
    icon: HelpCircle,
    description: "Docs, FAQs & contact",
    external: true,
  },
  {
    id: "_logout",
    label: "Sign out",
    icon: LogOut,
    danger: true,
  },
];

// ─── Lock body scroll while dropdown is open ─────────────────────────────────
function useLockBodyScroll(active) {
  useEffect(() => {
    if (!active) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = original; };
  }, [active]);
}

// ─── Component ────────────────────────────────────────────────────────────────
const UserMenu = ({ userName = "User", userEmail, onTabChange, onLogout }) => {
  const [open, setOpen]     = useState(false);
  const [dropPos, setDropPos] = useState({ top: 0, right: 0 });
  const triggerRef  = useRef(null);
  const dropdownRef = useRef(null);

  const close = () => setOpen(false);

  useEscapeKey(open, close);
  useClickOutside([triggerRef, dropdownRef], open ? close : null);
  useLockBodyScroll(open);

  // Recalculate position from trigger whenever we open
  useEffect(() => {
    if (!open || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setDropPos({
      top:   rect.bottom + 8,
      right: Math.max(8, window.innerWidth - rect.right),
    });
  }, [open]);

  // ── Avatar initials ───────────────────────────────────────────────────────
  const displayName = (userName?.trim() || "User");
  const parts = displayName.split(" ").filter(Boolean);
  const avatarText = parts.length > 1
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : displayName.charAt(0).toUpperCase();

  // ── Item handler ──────────────────────────────────────────────────────────
  const handleItem = (item) => {
    close();
    if (item.id === "_logout") { onLogout?.(); return; }
    if (item.id === "_help")   { window.open("https://cybercrime.gov.in", "_blank"); return; }
    onTabChange?.(item.id);
  };

  return (
    <>
      {/* ── Trigger chip ─────────────────────────────────────────────────── */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${displayName}`}
        className={`flex h-10 shrink-0 items-center gap-2 rounded-full border p-1 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/50 md:pr-3 ${
          open
            ? "border-purple-400/50 bg-purple-500/15 shadow-[0_0_24px_-6px_rgba(139,92,246,0.6)]"
            : "border-white/10 bg-white/[0.04] hover:border-purple-400/30 hover:bg-white/[0.07] hover:shadow-[0_0_16px_-8px_rgba(139,92,246,0.35)]"
        }`}
      >
        {/* Avatar */}
        <span className={`relative grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-purple-500 to-purple-700 text-[11px] font-bold text-white transition-shadow duration-300 ${
          open
            ? "shadow-[0_0_18px_-2px_rgba(139,92,246,0.8)]"
            : "shadow-[0_0_10px_-4px_rgba(139,92,246,0.5)]"
        }`}>
          {avatarText}
          {/* Online dot */}
          <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[#070418] bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
        </span>

        {/* Name + badge */}
        <span className="hidden flex-col items-start leading-none md:flex">
          <span className="max-w-[7.5rem] truncate text-[13px] font-medium leading-tight text-white/90">
            {displayName}
          </span>
          <span className="mt-0.5 flex items-center gap-0.5 text-[10px] font-semibold tracking-wide text-purple-400">
            <Zap size={8} aria-hidden />
            Premium
          </span>
        </span>

        <ChevronDown
          size={14}
          className={`hidden text-white/40 transition-transform duration-200 md:block ${open ? "rotate-180" : ""}`}
          aria-hidden
        />
      </button>

      {/* ── Portal ── backdrop + dropdown at document.body level ─────────── */}
      {createPortal(
        <AnimatePresence>
          {open && (
            <>
              {/*
               * LAYER 1 — Backdrop  z-40
               * backdrop-blur-sm + bg-black/40 dims the page softly.
               * The blur effect belongs HERE, not on the dropdown container.
               */}
              <motion.div
                key="user-backdrop"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                onClick={close}
                className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
                aria-hidden
              />

              {/*
               * LAYER 2 — Dropdown  z-50
               * bg-[#0B0716] is FULLY SOLID — zero transparency on the container.
               * This is the ONLY correct way to prevent page content bleeding through.
               * Position driven by JS (dropPos) so it anchors to the trigger button
               * correctly regardless of scroll position.
               */}
              <motion.div
                key="user-dropdown"
                ref={dropdownRef}
                role="menu"
                aria-label="User account menu"
                initial={{ opacity: 0, scale: 0.96, y: -6 }}
                animate={{ opacity: 1, scale: 1,    y:  0 }}
                exit={{    opacity: 0, scale: 0.96, y: -4 }}
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
                style={{ top: dropPos.top, right: dropPos.right }}
                className={[
                  "fixed z-50 w-72",
                  // ✅ SOLID background
                  "bg-[#0B0716]",
                  "overflow-hidden rounded-xl",
                  "border border-purple-500/20",
                  "shadow-2xl shadow-purple-500/10",
                ].join(" ")}
              >
                {/* Gradient top-border accent */}
                <div
                  className="absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-purple-500/50 to-transparent"
                  aria-hidden
                />

                {/* ── User info header ── */}
                <div className="flex items-center gap-3 border-b border-white/10 p-4">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-purple-700 text-sm font-semibold text-white">
                    {avatarText}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-white">
                      {displayName}
                    </p>
                    {userEmail && (
                      <p
                        className="mt-0.5 truncate text-xs text-gray-400"
                        title={userEmail}
                      >
                        {userEmail}
                      </p>
                    )}
                  </div>
                  <span className="ml-auto shrink-0 rounded border border-purple-500/30 bg-purple-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-purple-300">
                    PRO
                  </span>
                </div>

                {/* ── Menu items ── */}
                <div className="p-2">
                  {MENU_ITEMS.map((item, idx) => {
                    if (item === null) {
                      return <div key={`divider-${idx}`} className="my-1 h-px bg-white/[0.07]" />;
                    }
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        role="menuitem"
                        onClick={() => handleItem(item)}
                        className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/40 ${
                          item.danger
                            ? "text-gray-300 hover:bg-red-500/10 hover:text-red-400"
                            : "text-gray-300 hover:bg-white/5 hover:text-white"
                        }`}
                      >
                        {/* Icon container */}
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors duration-150 ${
                          item.danger
                            ? "bg-white/[0.04] group-hover:bg-red-500/15"
                            : "bg-white/5 group-hover:bg-purple-500/20"
                        }`}>
                          <Icon
                            size={15}
                            className={`transition-colors duration-150 ${
                              item.danger
                                ? "text-gray-400 group-hover:text-red-400"
                                : "text-gray-400 group-hover:text-purple-300"
                            }`}
                          />
                        </span>

                        {/* Label + description */}
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium leading-none">
                            {item.label}
                          </p>
                          {item.description && (
                            <p className="mt-0.5 text-xs leading-none text-gray-400 transition-colors group-hover:text-gray-300">
                              {item.description}
                            </p>
                          )}
                        </div>

                        {/* External link icon — flush right */}
                        {item.external && (
                          <ExternalLink
                            size={13}
                            className="ml-auto shrink-0 text-gray-600 transition-colors group-hover:text-gray-400"
                            aria-hidden
                          />
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* ── Footer ── */}
                <div className="border-t border-white/10 px-4 py-2.5">
                  <p className="text-center text-[10px] text-gray-500">
                    SmartSpend v2 · Protected by FraudShield AI
                  </p>
                </div>
              </motion.div>
            </>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
};

export default UserMenu;
