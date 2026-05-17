import React from "react";

/**
 * Consistent post-upload summary for signup + settings flows.
 */
export default function UploadResultSummary({
  result,
  variant = "dark",
  onViewTransactions,
}) {
  if (!result?.success) return null;

  const extracted = result.extracted ?? result.transactions_extracted ?? 0;
  const imported = result.imported ?? result.transactions_stored ?? 0;
  const duplicates = result.duplicates ?? 0;
  const institution = result.institution || "Document";

  const box =
    variant === "signup"
      ? "rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-6 py-4 text-left"
      : "rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 space-y-2";

  const titleClass =
    variant === "signup"
      ? "text-base text-emerald-300"
      : "font-semibold text-emerald-300";

  return (
    <div className={box}>
      <p className={titleClass}>
        ✓ {institution} — {imported} imported
        {duplicates > 0 ? ` (${duplicates} duplicates skipped)` : ""}
      </p>

      {result.date_range && (
        <p className="text-xs text-white/50 mt-1">Period: {result.date_range}</p>
      )}

      {(result.quality_score != null || result.extraction_method) && (
        <p className="text-xs text-white/45 mt-1">
          Quality {result.quality_score ?? "—"}%
          {result.extraction_method ? ` · ${result.extraction_method}` : ""}
          {result.attempts > 1 ? ` · ${result.attempts} attempts` : ""}
        </p>
      )}

      <div className="grid grid-cols-3 gap-2 mt-3">
        {[
          { label: "Extracted", value: extracted },
          { label: "Imported", value: imported },
          { label: "Skipped", value: duplicates },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-lg border border-white/10 bg-white/[0.04] px-2 py-2 text-center"
          >
            <p className="text-lg font-bold text-white">{s.value ?? 0}</p>
            <p className="text-[10px] text-white/50">{s.label}</p>
          </div>
        ))}
      </div>

      {result.source_id && (
        <p className="text-xs text-white/35 mt-2">
          Linked to source #{result.source_id}
          {result.document_id ? ` · document #${result.document_id}` : ""}
        </p>
      )}

      {result.internal_transfers_skipped > 0 && (
        <p className="text-xs text-white/40 mt-1">
          {result.internal_transfers_skipped} internal transfer(s) excluded.
        </p>
      )}

      {onViewTransactions && (
        <button
          type="button"
          onClick={onViewTransactions}
          className="mt-3 text-sm font-semibold text-violet-300 hover:text-violet-200"
        >
          View transactions →
        </button>
      )}
    </div>
  );
}
