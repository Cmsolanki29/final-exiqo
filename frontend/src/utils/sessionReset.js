/**
 * Clear client-side session artifacts on logout so the next login never sees stale data.
 */
import { clearAuthTokens, TOKEN_ACCESS_KEY, TOKEN_REFRESH_KEY } from "../services/api";

const PREFIX_KEYS = [
  "smartspend",
  "ss_",
  "subscription_flow_",
];

export function clearClientSessionState(userId) {
  clearAuthTokens();

  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (!key) continue;
      if (key === TOKEN_ACCESS_KEY || key === TOKEN_REFRESH_KEY) continue;
      if (PREFIX_KEYS.some((p) => key.startsWith(p) || key.includes(p))) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((k) => localStorage.removeItem(k));
  } catch {
    /* ignore */
  }

  try {
    const sessionKeys = [];
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const key = sessionStorage.key(i);
      if (!key) continue;
      if (PREFIX_KEYS.some((p) => key.startsWith(p) || key.includes(p))) {
        sessionKeys.push(key);
      }
    }
    sessionKeys.forEach((k) => sessionStorage.removeItem(k));
  } catch {
    /* ignore */
  }

  if (userId) {
    try {
      sessionStorage.removeItem(`ss_pre_onboard_intro_done_${userId}`);
    } catch {
      /* ignore */
    }
  }

  try {
    window.dispatchEvent(new CustomEvent("smartspend:session-cleared", { detail: { userId } }));
  } catch {
    /* ignore */
  }
}
