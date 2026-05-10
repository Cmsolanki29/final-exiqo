/**
 * RiskContext — global Phase 1-8 risk engine health state.
 * Polls /api/health every 30s; exposes healthy flag + metadata.
 * All risk components call useRisk() and hide gracefully when healthy=false.
 */

import React, { createContext, useContext, useEffect, useState } from "react";
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
  const [state, setState] = useState(defaultState);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const data = await riskHealth();
        if (!cancelled) {
          setState({
            healthy: data.status === "healthy",
            dbConnected: data.db === "connected",
            mlReady: data.ml === "ready",
            version: data.version ?? "2.0.0",
            lastCheckedAt: new Date(),
          });
        }
      } catch {
        if (!cancelled) {
          setState((prev) => ({
            ...prev,
            healthy: false,
            lastCheckedAt: new Date(),
          }));
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

  return <RiskContext.Provider value={state}>{children}</RiskContext.Provider>;
}

export const useRisk = () => useContext(RiskContext);
