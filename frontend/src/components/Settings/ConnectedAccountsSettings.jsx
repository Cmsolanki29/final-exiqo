import React, { useCallback, useEffect, useState } from "react";
import { Landmark, CreditCard, Eye, EyeOff, Plus } from "lucide-react";
import { getConnectedSources, toggleSourceVisibility, updateDashboardMode } from "../../services/api";
import { useAuth } from "../../context/AuthContext";

function iconForType(t) {
  if (t === "credit_card") return CreditCard;
  return Landmark;
}

export default function ConnectedAccountsSettings({ userId, onGoUpload }) {
  const { reloadUser, user } = useAuth();
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [mode, setMode] = useState("merged");
  const [savingMode, setSavingMode] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setErr("");
    try {
      const data = await getConnectedSources(userId);
      setSources(data.sources || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load accounts");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (user?.dashboard_mode) setMode(user.dashboard_mode);
  }, [user?.dashboard_mode]);

  const onToggleVisible = async (sourceId, next) => {
    try {
      await toggleSourceVisibility({ userId, sourceId, visible: next });
      await load();
      await reloadUser();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    }
  };

  const applyMode = async () => {
    setSavingMode(true);
    setErr("");
    try {
      const visibleIds = sources.filter((s) => s.is_visible_on_dashboard).map((s) => s.id);
      await updateDashboardMode({ userId, mode, visibleSourceIds: visibleIds });
      await reloadUser();
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save dashboard mode");
    } finally {
      setSavingMode(false);
    }
  };

  const bankCount = sources.filter((s) => s.source_type === "bank" || s.source_type === "bank_statement_pdf").length;
  const cardCount = sources.filter((s) => s.source_type === "credit_card").length;

  return (
    <div className="rounded-2xl border border-white/10 bg-[#0c1022]/90 p-5 md:p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-heading text-lg font-semibold text-white">Connected accounts</h2>
          <p className="mt-1 text-sm text-white/55">
            Toggle which sources feed your dashboard, then pick bank-only, card-only, or merged view.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onGoUpload?.("credit_card")}
            className="inline-flex items-center gap-2 rounded-xl border border-violet-500/40 bg-violet-500/15 px-3 py-2 text-sm font-semibold text-violet-100 hover:bg-violet-500/25"
          >
            <Plus className="h-4 w-4" aria-hidden />
            Add credit card
          </button>
          <button
            type="button"
            onClick={() => onGoUpload?.("bank_statement_pdf")}
            className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/35 bg-cyan-500/10 px-3 py-2 text-sm font-semibold text-cyan-100 hover:bg-cyan-500/20"
          >
            <Plus className="h-4 w-4" aria-hidden />
            Upload bank statement
          </button>
        </div>
      </div>

      {err ? (
        <p className="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{err}</p>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-white/45">Loading accounts…</p>
      ) : sources.length === 0 ? (
        <p className="mt-6 text-sm text-white/50">
          No linked sources yet. Use the buttons above to upload a card or bank statement (demo seed data still appears
          in merged mode).
        </p>
      ) : (
        <ul className="mt-5 space-y-3">
          {sources.map((s) => {
            const Icon = iconForType(s.source_type);
            const vis = Boolean(s.is_visible_on_dashboard);
            return (
              <li
                key={s.id}
                className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/[0.04] p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <span className="mt-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/[0.06] text-white/90">
                    <Icon className="h-5 w-5" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-white">{s.institution_name}</p>
                    <p className="text-xs text-white/45">
                      {String(s.source_type || "").replace(/_/g, " ")}
                      {s.account_number_masked ? ` · ${s.account_number_masked}` : ""}
                      {s.is_primary ? " · Primary" : ""}
                      {s.added_via ? ` · via ${s.added_via}` : ""}
                    </p>
                    <p className="mt-1 text-xs text-white/35">
                      {Number(s.transactions_count || 0)} transactions
                      {s.last_upload ? ` · last upload ${new Date(s.last_upload).toLocaleDateString("en-IN")}` : ""}
                    </p>
                  </div>
                </div>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-white/80">
                  {vis ? <Eye className="h-4 w-4 text-emerald-300" /> : <EyeOff className="h-4 w-4 text-white/35" />}
                  <span>On dashboard</span>
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-violet-500"
                    checked={vis}
                    onChange={(e) => onToggleVisible(s.id, e.target.checked)}
                  />
                </label>
              </li>
            );
          })}
        </ul>
      )}

      {(bankCount >= 1 && cardCount >= 1) || sources.length >= 2 ? (
        <div className="mt-8 border-t border-white/10 pt-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-white/50">Dashboard view</h3>
          <p className="mt-1 text-xs text-white/40">Currently: {mode.replace(/_/g, " ")}</p>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {[
              { id: "bank_only", label: "Bank only" },
              { id: "credit_card_only", label: "Card only" },
              { id: "merged", label: "Both (merged)" },
            ].map((o) => (
              <label
                key={o.id}
                className={`flex cursor-pointer items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium transition ${
                  mode === o.id
                    ? "border-violet-500/60 bg-violet-500/15 text-white"
                    : "border-white/10 bg-white/[0.03] text-white/60 hover:border-white/20"
                }`}
              >
                <input
                  type="radio"
                  name="dash-mode"
                  className="accent-violet-500"
                  checked={mode === o.id}
                  onChange={() => setMode(o.id)}
                />
                {o.label}
              </label>
            ))}
          </div>
          <button
            type="button"
            disabled={savingMode}
            onClick={applyMode}
            className="mt-4 w-full rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 py-2.5 text-sm font-semibold text-white hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 sm:w-auto sm:px-8"
          >
            {savingMode ? "Saving…" : "Switch view"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
