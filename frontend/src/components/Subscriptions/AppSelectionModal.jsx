import React, { useCallback, useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { ALL_SUBSCRIPTION_APPS, INITIAL_CONNECT_APP_IDS, getAddableAppIds } from "../../constants/subscriptionApps";

/**
 * @param {object} props
 * @param {boolean} props.open
 * @param {"initial"|"add"} props.variant
 * @param {string[]} props.connectedIds — for variant "add", apps already linked
 * @param {(appIds: string[]) => void} props.onConfirm
 * @param {() => void} props.onClose
 */
export default function AppSelectionModal({ open, variant, connectedIds = [], onConfirm, onClose }) {
  const pool = useMemo(() => {
    if (variant === "initial") {
      const allow = new Set(INITIAL_CONNECT_APP_IDS);
      return ALL_SUBSCRIPTION_APPS.filter((a) => allow.has(a.id));
    }
    const addable = getAddableAppIds(connectedIds);
    return ALL_SUBSCRIPTION_APPS.filter((a) => addable.includes(a.id));
  }, [variant, connectedIds]);

  const [selected, setSelected] = useState(() => new Set());
  // Track which app logo images failed to load so we can show the letter fallback.
  const [imgErrors, setImgErrors] = useState({});
  const onImgError = useCallback((id) => setImgErrors((prev) => ({ ...prev, [id]: true })), []);

  useEffect(() => {
    if (!open) return;
    setSelected(new Set());
  }, [open, variant]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const title =
    variant === "initial" ? "Connect your subscription apps" : "Add more applications";

  const subtitle =
    variant === "initial"
      ? "Select the services SmartSpend should analyse for usage and billing intelligence."
      : "Choose additional apps to link. You can reconnect permissions after adding.";

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="app-select-title"
    >
      <div className="relative max-h-[90vh] w-full max-w-lg overflow-hidden rounded-2xl border border-white/15 bg-[#0b1224] shadow-2xl shadow-black/50">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 rounded-lg p-2 text-exiqo-glow/70 transition hover:bg-white/10 hover:text-white"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="border-b border-white/10 px-6 pb-4 pt-6 pr-14">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-300/90">Step 1</p>
          <h2 id="app-select-title" className="mt-1 font-heading text-xl font-semibold text-white">
            {title}
          </h2>
          <p className="mt-2 text-sm text-gray-400">{subtitle}</p>
        </div>

        <div className="max-h-[min(52vh,420px)] space-y-2 overflow-y-auto px-4 py-4">
          {pool.length === 0 ? (
            <p className="py-8 text-center text-sm text-gray-400">All available apps are already connected.</p>
          ) : (
            pool.map((app) => {
              const on = selected.has(app.id);
              return (
                <label
                  key={app.id}
                  className={`flex cursor-pointer items-center gap-4 rounded-xl border px-4 py-3 transition ${
                    on ? "border-cyan-400/50 bg-cyan-500/10" : "border-white/10 bg-white/[0.03] hover:border-white/20"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => toggle(app.id)}
                    className="h-4 w-4 shrink-0 rounded border-white/20 bg-black/40 text-cyan-500 focus:ring-cyan-400/60"
                  />
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.04]"
                    aria-hidden
                  >
                    {app.logo && !imgErrors[app.id] ? (
                      <img
                        src={`https://cdn.simpleicons.org/${app.logo.slug}/${app.logo.color}`}
                        alt=""
                        className="h-5 w-5 object-contain"
                        onError={() => onImgError(app.id)}
                      />
                    ) : (
                      // Original emoji shown when CDN image fails to load
                      <span className="text-base leading-none" aria-hidden>
                        {app.emoji}
                      </span>
                    )}
                  </div>
                  <span className="text-sm font-medium text-white">{app.label}</span>
                </label>
              );
            })
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-white/10 bg-black/20 px-4 py-4">
          <button type="button" className="ghost-btn px-4 py-2 text-sm" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="rounded-xl bg-gradient-to-r from-cyan-500 to-violet-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-cyan-500/20 disabled:opacity-40"
            disabled={selected.size === 0}
            onClick={() => onConfirm([...selected])}
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
