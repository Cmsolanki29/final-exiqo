/**
 * useFeedbackStats — fetches user-level fraud feedback stats.
 */

import { useEffect, useState } from "react";
import { getFeedbackStats } from "../../services/riskApi";
import { useAuth } from "../../context/AuthContext";

export function useFeedbackStats() {
  const { user } = useAuth();
  const userId = user?.id;

  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    setLoading(true);

    getFeedbackStats(userId)
      .then((res) => { if (!cancelled) { setData(res); setLoading(false); } })
      .catch((err) => { if (!cancelled) { setError(err); setLoading(false); } });

    return () => { cancelled = true; };
  }, [userId]);

  return { data, loading, error };
}
