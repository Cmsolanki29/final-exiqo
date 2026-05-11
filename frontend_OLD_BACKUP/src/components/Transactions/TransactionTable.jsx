import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { apiUtils, getTransactions } from "../../services/api";
import { EmptyState } from "../common/EmptyState";
import { ErrorCard } from "../common/ErrorCard";
import { SkeletonCard } from "../common/SkeletonCard";
// ── Phase 1-8 Risk Engine addons ──────────────────────────────────────────
import { RiskScoreChip } from "../risk/RiskScoreChip";
import { RiskChallengeModal } from "../risk/RiskChallengeModal";

/**
 * Derive a Phase 4-style risk_action from existing transaction fields when
 * the backend doesn't yet provide one. Keeps every transaction chip-ready.
 *
 * Rules:
 *   - explicit risk_action wins
 *   - anomaly_flag + HIGH risk_level → "block"
 *   - HIGH risk_level                → "challenge"
 *   - MEDIUM risk_level              → "review"
 *   - anything else                  → "allow"
 */
function deriveRiskAction(tx) {
  if (tx.risk_action) return tx.risk_action;
  const lvl = String(tx.risk_level || "").toUpperCase();
  if (tx.anomaly_flag && lvl === "HIGH") return "block";
  if (lvl === "HIGH")    return "challenge";
  if (lvl === "MEDIUM")  return "review";
  return "allow";
}

const categories = ["All", "Food", "Shopping", "Travel", "Bills", "Anomalies Only"];

const csvEscape = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;

const TransactionTable = ({ userId, month, year }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [sortBy, setSortBy] = useState("date");
  const [page, setPage] = useState(1);
  // ── Phase 7 SHAP modal state ─────────────────────────────────────────────
  const [selectedTxn, setSelectedTxn] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const anomalyOnly = category === "Anomalies Only" ? true : undefined;
      const apiCategory = ["All", "Anomalies Only"].includes(category) ? undefined : category;
      const data = await getTransactions(userId, {
        month,
        year,
        category: apiCategory,
        anomaly_only: anomalyOnly,
        limit: 200,
      });
      setRows(data || []);
    } catch (err) {
      setError(err.message || "Unable to load transactions");
    } finally {
      setLoading(false);
    }
  }, [userId, month, year, category]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    let data = rows.filter((r) => String(r.merchant || "").toLowerCase().includes(search.toLowerCase()));

    if (sortBy === "amount") {
      data = [...data].sort((a, b) => Number(b.amount || 0) - Number(a.amount || 0));
    } else if (sortBy === "risk") {
      data = [...data].sort((a, b) => Number(b.risk_score || 0) - Number(a.risk_score || 0));
    } else {
      data = [...data].sort((a, b) => new Date(`${b.transaction_date}T${b.transaction_time}`) - new Date(`${a.transaction_date}T${a.transaction_time}`));
    }

    return data;
  }, [rows, search, sortBy]);

  const pageSize = 20;
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const pagedRows = filtered.slice((page - 1) * pageSize, page * pageSize);

  useEffect(() => {
    setPage(1);
  }, [search, sortBy, category, month, year, userId]);

  const exportCsv = () => {
    const headers = ["Date", "Merchant", "Category", "Amount", "Type", "Method", "Risk", "Risk Score"];
    const lines = [headers.join(",")];

    filtered.forEach((r) => {
      lines.push(
        [
          csvEscape(r.transaction_date),
          csvEscape(r.merchant),
          csvEscape(r.category),
          csvEscape(r.amount),
          csvEscape(r.type),
          csvEscape(r.payment_method),
          csvEscape(r.risk_level),
          csvEscape(r.risk_score),
        ].join(",")
      );
    });

    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `transactions-user-${userId}-${month}-${year}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <>
    <section className="glass-card table-wrap">
      <div className="panel-head">
        <h3>Transactions</h3>
        <button type="button" className="ghost-btn" onClick={exportCsv}>
          <Download size={16} /> Export CSV
        </button>
      </div>

      <div className="table-controls">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by merchant..."
        />

        <div className="filter-row">
          {categories.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setCategory(item)}
              className={`chip-btn ${category === item ? "active" : ""}`}
            >
              {item}
            </button>
          ))}
        </div>

        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="date">Date</option>
          <option value="amount">Amount</option>
          <option value="risk">Risk Score</option>
        </select>
      </div>

      {loading ? (
        <div>
          <p className="muted small" style={{ marginBottom: 12 }}>
            Loading transactions…
          </p>
          <SkeletonCard lines={6} height={200} />
        </div>
      ) : error ? (
        <ErrorCard message={error} onRetry={load} />
      ) : pagedRows.length === 0 ? (
        <EmptyState
          icon="📄"
          title="No transactions match"
          subtitle="Try widening filters or pick another month."
        />
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Merchant</th>
                  <th>Category</th>
                  <th>Amount</th>
                  <th>Method</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {pagedRows.map((tx) => (
                  <tr key={tx.id} className={`risk-row ${String(tx.risk_level || "LOW").toLowerCase()}`}>
                    <td>{String(tx.transaction_date)}</td>
                    <td>{tx.merchant || "-"}</td>
                    <td>{tx.category || "Uncategorized"}</td>
                    <td className={tx.type === "CREDIT" ? "amount-positive" : "amount-neutral"}>
                      {apiUtils.formatINR(tx.amount)}
                    </td>
                    <td>{tx.payment_method || "-"}</td>
                    <td>
                      {/* Phase 7 — SHAP chip; derives risk_action when backend doesn't supply one */}
                      <RiskScoreChip
                        txnId={tx.id}
                        action={deriveRiskAction(tx)}
                        score={tx.risk_score}
                        onClick={() => setSelectedTxn(tx)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
              &lt; Prev
            </button>
            <span>
              Page {page} / {pageCount}
            </span>
            <button type="button" onClick={() => setPage((p) => Math.min(pageCount, p + 1))} disabled={page === pageCount}>
              Next &gt;
            </button>
          </div>
        </>
      )}
    </section>

    {/* ── Phase 7 SHAP explanation modal ──────────────────────────── */}
    <RiskChallengeModal
      txnId={selectedTxn?.id ?? null}
      txnMeta={{ merchant: selectedTxn?.merchant, amount: selectedTxn?.amount }}
      onClose={() => setSelectedTxn(null)}
    />
  </>
  );
};

export default TransactionTable;
