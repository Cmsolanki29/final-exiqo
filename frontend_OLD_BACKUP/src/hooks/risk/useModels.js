/**
 * useModels — fetches model registry + drift report.
 */

import { useEffect, useState } from "react";
import { getModels, getDriftReport, getShadowReport } from "../../services/riskApi";

export function useModels() {
  const [models, setModels]   = useState([]);
  const [drift, setDrift]     = useState(null);
  const [shadow, setShadow]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.allSettled([getModels(), getDriftReport(), getShadowReport()]).then(
      ([modRes, driftRes, shadowRes]) => {
        if (cancelled) return;
        if (modRes.status === "fulfilled") {
          // Tolerate any shape: array, {models: [...]}, {items: [...]}, or random object
          const v = modRes.value;
          const arr = Array.isArray(v) ? v
                    : Array.isArray(v?.models) ? v.models
                    : Array.isArray(v?.items)  ? v.items
                    : [];
          setModels(arr);
        }
        if (driftRes.status === "fulfilled") setDrift(driftRes.value);
        if (shadowRes.status === "fulfilled") setShadow(shadowRes.value);
        const failures = [modRes, driftRes, shadowRes].filter((r) => r.status === "rejected");
        if (failures.length === 3) setError(failures[0].reason);
        setLoading(false);
      }
    );

    return () => { cancelled = true; };
  }, []);

  return { models, drift, shadow, loading, error };
}
