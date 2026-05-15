import React, { useEffect } from "react";
import { ShieldCheck, X } from "lucide-react";
import { labelsForIds } from "../../constants/subscriptionApps";

/**
 * @param {object} props
 * @param {boolean} props.open
 * @param {string[]} props.appIds
 * @param {() => void} props.onAllow
 * @param {() => void} props.onDeny
 */
export default function PermissionModal({ open, appIds, onAllow, onDeny }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onDeny();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onDeny]);

  if (!open) return null;

  const names = labelsForIds(appIds);

  return (
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="perm-title"
    >
      <div className="relative w-full max-w-md rounded-2xl border border-violet-400/25 bg-[#0b1224] p-6 shadow-2xl">
        <button
          type="button"
          onClick={onDeny}
          className="absolute right-3 top-3 rounded-lg p-2 text-exiqo-glow/70 transition hover:bg-white/10 hover:text-white"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500">
          <ShieldCheck className="h-7 w-7 text-white" aria-hidden />
        </div>

        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-gray-500">Step 2</p>
        <h2 id="perm-title" className="mt-1 font-heading text-xl font-semibold text-white">
          Permission access
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-gray-400">
          SmartSpend wants permission to analyse subscription usage and billing behaviour for:{" "}
          <span className="font-medium text-white">{names.join(", ")}</span>.
        </p>

        <ul className="mt-4 space-y-2 text-sm text-gray-300">
          <li className="flex gap-2">
            <span className="text-emerald-400">✔</span> Usage access
          </li>
          <li className="flex gap-2">
            <span className="text-emerald-400">✔</span> App activity monitoring
          </li>
          <li className="flex gap-2">
            <span className="text-emerald-400">✔</span> Billing reminder access
          </li>
          <li className="flex gap-2">
            <span className="text-emerald-400">✔</span> Notification permission
          </li>
        </ul>

        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <button type="button" className="ghost-btn px-4 py-2 text-sm" onClick={onDeny}>
            Not now
          </button>
          <button
            type="button"
            className="rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg"
            onClick={onAllow}
          >
            Allow
          </button>
        </div>
      </div>
    </div>
  );
}
