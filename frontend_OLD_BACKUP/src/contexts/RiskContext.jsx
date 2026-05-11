/**
 * RiskContext — global Phase 1-12 risk engine health state.
 * Polls /api/health every 30s; exposes healthy flag + metadata.
 * All risk components call useRisk() and hide gracefully when healthy=false.
 *
 * Performance note: the context value is memoized so that a health-poll
 * result that returns the same data does not cause every consumer to
 * re-render.
 */

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { riskHealth } from "../services/riskApi";

const defaultState = {
  healthy: false,
  dbConnected: false,
  mlReady: false,
  version: null,
  lastCheckedAt: null,
};

const RiskContext = createContext(defaultState);

export function RiskProvider({ children }) {
  const [healthy, setHealthy] = useState(false);
  const [dbConnected, setDbConnected] = useState(false);
  const [mlReady, setMlReady] = useState(false);
  const [version, setVersion] = useState(null);
  const [lastCheckedAt, setLastCheckedAt] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const data = await riskHealth();
        if (!cancelled) {
          setHealthy(data.status === "healthy");
          setDbConnected(data.db === "connected");
          setMlReady(data.ml === "ready");
          setVersion(data.version ?? "2.0.0");
          setLastCheckedAt(new Date());
        }
      } catch {
        if (!cancelled) {
          setHealthy(false);
          setLastCheckedAt(new Date());
        }
      }
    };

    check();
    const id = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Memoize the context object so consumers only re-render when
  // an individual value actually changes, not on every state flush.
  const value = useMemo(
    () => ({ healthy, dbConnected, mlReady, version, lastCheckedAt }),
    [healthy, dbConnected, mlReady, version, lastCheckedAt]
  );

  return <RiskContext.Provider value={value}>{children}</RiskContext.Provider>;
}

export const useRisk = () => useContext(RiskContext);
