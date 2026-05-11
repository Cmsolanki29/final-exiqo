/**
 * useReviewQueue — fetches + refreshes the admin review queue.
 */

import { useCallback, useEffect, useState } from "react";
import { getReviewQueue, decideReviewItem } from "../../services/riskApi";

export function useReviewQueue(params = {}) {
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getReviewQueue(params);
      // Tolerate any shape: array, {items: [...]}, {queue: [...]}, etc.
      const arr = Array.isArray(res) ? res
                : Array.isArray(res?.items) ? res.items
                : Array.isArray(res?.queue) ? res.queue
                : [];
      setData(arr);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(params)]);

  useEffect(() => { load(); }, [load]);

  const decide = useCallback(async (queueId, resolution, notes) => {
    await decideReviewItem(queueId, resolution, notes);
    await load();
  }, [load]);

  return { data, loading, error, refresh: load, decide };
}
