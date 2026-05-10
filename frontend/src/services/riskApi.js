/**
 * riskApi.js — Phase 1-8 Risk Engine API calls
 *
 * Auth pattern mirrors services/api.js:
 *   - JWT Bearer token from localStorage key "smartspend_access_token"
 *   - Admin endpoints additionally require X-Admin-Token header
 *
 * All functions return the response .data directly.
 * On error they throw — callers must catch and show RiskStatePlaceholder.
 */

import axios from "axios";
import { getAccessToken } from "./api";

const ADMIN_TOKEN = process.env.REACT_APP_ADMIN_TOKEN || "dev-admin-secret";
const BASE = process.env.REACT_APP_API_URL || "http://localhost:8000/api";

// ── Axios client for regular JWT-authenticated risk calls ──────────────────
const riskClient = axios.create({ baseURL: BASE, timeout: 8000 });

riskClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Axios client for admin calls (JWT + X-Admin-Token) ────────────────────
const adminClient = axios.create({ baseURL: BASE, timeout: 8000 });

adminClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  config.headers = config.headers || {};
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers["X-Admin-Token"] = ADMIN_TOKEN;
  return config;
});

// ── Helper ────────────────────────────────────────────────────────────────
const d = (res) => res.data;

// ── Phase 1 — Real-time event health ──────────────────────────────────────
// Backend health endpoint lives at GET /health (no /api prefix)
export const riskHealth = () =>
  axios.get("http://localhost:8000/health", { timeout: 5000 })
    .then(d)
    .catch(() => ({ status: "degraded" }));

// ── Phase 2 — Feature store / behavior profile ────────────────────────────
// Not yet exposed on backend; graceful 404 → empty state
export const getBehaviorProfile = (userId) =>
  riskClient.get(`/risk/users/${userId}/behavior-profile`).then(d);

// ── Phase 3 — Fraud labels / feedback stats ───────────────────────────────
export const getFeedbackStats = (userId) =>
  riskClient.get(`/risk/users/${userId}/feedback-stats`).then(d);

// ── Phase 4 — Decision engine: merchant config + blacklist ────────────────
export const getMerchantConfig = (merchantId) =>
  adminClient.get(`/admin/merchants/${merchantId}/risk-config`).then(d);

export const getBlacklist = () =>
  adminClient.get("/admin/blacklist").then(d);

export const addBlacklist = (payload) =>
  adminClient.post("/admin/blacklist", payload).then(d);

export const removeBlacklist = (entityId) =>
  adminClient.delete(`/admin/blacklist/${entityId}`).then(d);

// ── Phase 5 — MLOps: models, drift, shadow ───────────────────────────────
export const getModels = () =>
  adminClient.get("/admin/models").then(d);

export const getDriftReport = () =>
  adminClient.get("/admin/drift-report").then(d);

export const getShadowReport = () =>
  adminClient.get("/admin/shadow-report").then(d);

export const triggerDriftRun = () =>
  adminClient.get("/admin/drift-run").then(d);

// ── Phase 6 — Device trust (new endpoint) ────────────────────────────────
export const getDevices = (userId) =>
  riskClient.get(`/risk/users/${userId}/devices`).then(d);

// ── Phase 6 — Graph / network (admin deep-dive) ──────────────────────────
export const getUserNetwork = (userId) =>
  adminClient.get(`/admin/users/${userId}/network`).then(d);

export const getFraudDistance = (userId) =>
  adminClient.get(`/admin/users/${userId}/fraud-distance`).then(d);

export const getFraudRing = (userId) =>
  adminClient.get(`/admin/users/${userId}/fraud-ring`).then(d);

// ── Phase 7 — SHAP explainability ────────────────────────────────────────
export const getExplanation = (txnId) =>
  adminClient.get(`/transactions/${txnId}/explain`).then(d);

export const getSimilarTransactions = (txnId) =>
  adminClient.get(`/transactions/${txnId}/similar`).then(d);

// ── Phase 8 — Feedback flywheel / review queue ───────────────────────────
export const reportFraud = (txnId, notes = "") =>
  riskClient.post(`/transactions/${txnId}/report-fraud`, { notes }).then(d);

// Enriched review queue — includes merchant, amount, reason joined from transactions
export const getEnrichedReviewQueue = (status = "pending", limit = 20) =>
  riskClient.get("/risk/review-queue", { params: { status, limit } }).then(d);

export const getReviewQueue = (params = {}) =>
  adminClient.get("/admin/review-queue", { params }).then(d);

export const getReviewItem = (queueId) =>
  adminClient.get(`/admin/review-queue/${queueId}`).then(d);

export const decideReviewItem = (queueId, resolution, notes = "") =>
  adminClient
    .post(`/admin/review-queue/${queueId}/decide`, { resolution, notes })
    .then(d);

// ── Model status (real trained model metrics) ─────────────────────────────
export const getModelStatus = () =>
  riskClient.get("/risk/model-status").then(d);

// ── Trust score (not yet on backend — graceful stub) ──────────────────────
export const getTrustScore = (_userId) =>
  Promise.reject(new Error("trust-score endpoint not yet available"));

// ── Live feed (not yet on backend — graceful stub) ───────────────────────
export const getRiskFeed = (_since) =>
  Promise.reject(new Error("risk-feed endpoint not yet available"));
