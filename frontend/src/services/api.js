import axios from "axios";

const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8001";

export const TOKEN_ACCESS_KEY = "smartspend_access_token";
export const TOKEN_REFRESH_KEY = "smartspend_refresh_token";

export function getAccessToken() {
  try {
    return localStorage.getItem(TOKEN_ACCESS_KEY);
  } catch {
    return null;
  }
}

export function setAuthTokens(access, refresh) {
  try {
    localStorage.setItem(TOKEN_ACCESS_KEY, access);
    localStorage.setItem(TOKEN_REFRESH_KEY, refresh);
  } catch {
    /* ignore */
  }
}

export function clearAuthTokens() {
  try {
    localStorage.removeItem(TOKEN_ACCESS_KEY);
    localStorage.removeItem(TOKEN_REFRESH_KEY);
  } catch {
    /* ignore */
  }
}

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

const refreshClient = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const path = String(config.url || "");
  const publicAuth = path.includes("/auth/signin") || path.includes("/auth/signup");
  if (!publicAuth) {
    const t = getAccessToken();
    if (t) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${t}`;
    }
  } else if (config.headers) {
    delete config.headers.Authorization;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const orig = error.config;
    if (!orig || orig._retry || !error.response || error.response.status !== 401) {
      return Promise.reject(error);
    }
    const url = String(orig.url || "");
    if (url.includes("/auth/signin") || url.includes("/auth/signup") || url.includes("/auth/refresh")) {
      return Promise.reject(error);
    }
    let rt;
    try {
      rt = localStorage.getItem(TOKEN_REFRESH_KEY);
    } catch {
      rt = null;
    }
    if (!rt) {
      clearAuthTokens();
      return Promise.reject(error);
    }
    try {
      orig._retry = true;
      const { data } = await refreshClient.post("/auth/refresh", { refresh_token: rt });
      setAuthTokens(data.access_token, data.refresh_token);
      orig.headers = orig.headers || {};
      orig.headers.Authorization = `Bearer ${data.access_token}`;
      return api(orig);
    } catch (e) {
      clearAuthTokens();
      return Promise.reject(e);
    }
  }
);

const authDetail = (error) => {
  const d = error.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
  if (d && typeof d === "object") return JSON.stringify(d);
  return error.message || "Request failed";
};

const AUTH_TIMEOUT_MS = 60000;

export async function authSignin(body) {
  try {
    const { data } = await api.post("/auth/signin", body, { timeout: AUTH_TIMEOUT_MS });
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

export async function authSignup(body) {
  try {
    const { data } = await api.post("/auth/signup", body, { timeout: AUTH_TIMEOUT_MS });
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

export async function authGetMe() {
  try {
    const { data } = await api.get("/auth/me");
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

/** Mock Account Aggregator — public bank list */
export async function onboardingGetBanks() {
  try {
    const { data } = await api.get("/onboarding/available-banks");
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

export async function onboardingGetStatus() {
  try {
    const { data } = await api.get("/onboarding/status");
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

/** `bank_slug`: hdfc | sbi | icici | axis | kotak */
export async function onboardingLinkBank(body) {
  try {
    const { data } = await api.post("/onboarding/link-bank", body, { timeout: 60000 });
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

export async function otpSend(body) {
  try {
    const { data } = await api.post("/otp/send", body, { timeout: 30000 });
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

export async function otpVerify(body) {
  try {
    const { data } = await api.post("/otp/verify", body, { timeout: 30000 });
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

export async function authLogout() {
  try {
    const { data } = await api.post("/auth/logout");
    return data;
  } catch (e) {
    throw new Error(authDetail(e));
  }
}

export async function authRefresh(refreshToken) {
  const { data } = await refreshClient.post("/auth/refresh", { refresh_token: refreshToken });
  return data;
}

const handle = (response) => response.data;
const throwFriendly = (error) => {
  if (error.response?.data?.detail) {
    throw new Error(
      typeof error.response.data.detail === "string"
        ? error.response.data.detail
        : JSON.stringify(error.response.data.detail)
    );
  }
  throw new Error(error.message || "Request failed");
};

const request = async (promise) => {
  try {
    const response = await promise;
    return handle(response);
  } catch (error) {
    throwFriendly(error);
  }
};

export const getUsers = async () => request(api.get("/users"));
export const getUser = async (userId) => request(api.get(`/users/${userId}`));

export const getTransactions = async (userId, params = {}) =>
  request(api.get(`/transactions/${userId}`, { params }));

export const getTransactionSummary = async (userId, month, year) =>
  request(api.get(`/transactions/${userId}/summary`, { params: { month, year } }));

export const getSpendingAnalysis = async (userId, month, year) =>
  request(api.get(`/analysis/${userId}/spending`, { params: { month, year } }));

export const getMonthlyTrends = async (userId) =>
  request(api.get(`/analysis/${userId}/trends`));

export const getTopMerchants = async (userId, month, year) =>
  request(api.get(`/analysis/${userId}/merchants`, { params: { month, year } }));

export const getAnomalies = async (userId, severity = null) =>
  request(api.get(`/anomalies/${userId}`, { params: severity ? { severity } : {} }));

export const getAnomalyStats = async (userId) =>
  request(api.get(`/anomalies/${userId}/stats`));

export const runMLDetection = async (userId) =>
  request(api.post(`/anomalies/${userId}/run-detection`));

export const getHealthScore = async (userId, month, year) =>
  request(api.get(`/health-score/${userId}`, { params: { month, year } }));

export const getHealthHistory = async (userId) =>
  request(api.get(`/health-score/${userId}/history`));

export const getInsights = async (userId, month, year) =>
  request(api.get(`/insights/${userId}`, { params: { month, year } }));

export const getQuickSummary = async (userId) =>
  request(api.get(`/insights/${userId}/quick-summary`));

export const getAnomalyExplanation = async (userId, transactionId) =>
  request(api.get(`/insights/${userId}/anomaly/${transactionId}`));

export const simulateScenario = async (userId, scenario, month, year) =>
  request(api.post(`/insights/${userId}/simulate`, { scenario, month, year }));

export const getHealthNarrative = async (userId, month, year) =>
  request(api.get(`/insights/${userId}/health-narrative`, { params: { month, year } }));

export const getEmiReport = async (userId) => request(api.get(`/emi/${userId}`));

export const scanEmi = async (userId) => request(api.post(`/emi/${userId}/scan`));

export const getSubscriptions = async (userId) =>
  request(api.get(`/subscriptions/${userId}`));

export const getDarkPatterns = async (userId) =>
  request(api.get(`/dark-patterns/${userId}`));

export const getRupeeTraps = async (userId) =>
  request(api.get(`/dark-patterns/${userId}/rupee-traps`));

export const scanDarkPatterns = async (userId) =>
  request(api.post(`/dark-patterns/${userId}/scan`));

export const resolveDarkPattern = async (userId, patternId) =>
  request(api.post(`/dark-patterns/${userId}/${patternId}/resolve`));

export const getFraudShieldGlobalSummary = async () => request(api.get("/fraud-shield/summary"));

export const getFraudShieldPatterns = async () => request(api.get("/fraud-shield/patterns"));

export const getFraudShieldAnalyze = async (userId) =>
  request(api.get(`/fraud-shield/${userId}/analyze`));

export const postFraudShieldCheckTransaction = async (userId, payload) =>
  request(api.post(`/fraud-shield/${userId}/check-transaction`, payload));

export const getFraudShieldAlerts = async (userId) =>
  request(api.get(`/fraud-shield/${userId}/alerts`));

export const postFraudShieldAlertAction = async (userId, alertId, action) =>
  request(api.post(`/fraud-shield/${userId}/alerts/${alertId}/action`, { action }));

export const getFraudShieldStats = async (userId) =>
  request(api.get(`/fraud-shield/${userId}/stats`));

export const getFestivals = async (userId) => request(api.get(`/festivals/${userId}`));

export const getFestivalHistory = async (userId) =>
  request(api.get(`/festivals/${userId}/history`));

export const postFestivalSetBudget = async (userId, payload) =>
  request(api.post(`/festivals/${userId}/set-budget`, payload));

export const getFestivalImportantDays = async (userId) =>
  request(api.get(`/festivals/${userId}/important-days`));

export const postFestivalImportantDay = async (userId, payload) =>
  request(api.post(`/festivals/${userId}/important-days`, payload));

export const putFestivalImportantDay = async (userId, eventId, payload) =>
  request(api.put(`/festivals/${userId}/important-days/${eventId}`, payload));

export const deleteFestivalImportantDay = async (userId, eventId) =>
  request(api.delete(`/festivals/${userId}/important-days/${eventId}`));

export const getPurchases = async (userId) => request(api.get(`/purchases/${userId}`));

export const postPurchaseAddGoal = async (userId, payload) =>
  request(api.post(`/purchases/${userId}/add-goal`, payload));

export const putPurchaseUpdateSavings = async (userId, goalId, amountSaved) =>
  request(api.put(`/purchases/${userId}/${goalId}/update-savings`, { amount_saved: amountSaved }));

export const deletePurchaseGoal = async (userId, goalId) =>
  request(api.delete(`/purchases/${userId}/${goalId}`));

export const apiUtils = {
  formatINR: (amount) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(Number(amount || 0)),
};
