import { useCallback, useEffect, useState } from "react";
import {
  getAnomalies,
  getAnomalyStats,
  getHealthScore,
  getMonthlyTrends,
  getQuickSummary,
  getSpendingAnalysis,
  getTopMerchants,
} from "../services/api";

export const useSmartSpend = (userId, month, year) => {
  const [data, setData] = useState({
    summary: null,
    spending: [],
    trends: [],
    anomalies: [],
    anomalyStats: null,
    health: null,
    merchants: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError("");
    try {
      const [summary, spending, trends, anomalies, anomalyStats, health, merchants] =
        await Promise.all([
          getQuickSummary(userId),
          getSpendingAnalysis(userId, month, year),
          getMonthlyTrends(userId),
          getAnomalies(userId),
          getAnomalyStats(userId),
          getHealthScore(userId, month, year),
          getTopMerchants(userId, month, year),
        ]);

      setData({
        summary,
        spending,
        trends,
        anomalies,
        anomalyStats,
        health,
        merchants,
      });
    } catch (err) {
      setError(err.message || "Unable to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, [userId, month, year]);

  useEffect(() => {
    load();
  }, [load]);

  return {
    ...data,
    loading,
    error,
    refetch: load,
  };
};

export default useSmartSpend;
