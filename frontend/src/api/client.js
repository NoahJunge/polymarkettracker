import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "";

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  timeout: 30000,
});

// --- Markets ---
export const getMarkets = (params = {}) => api.get("/markets", { params });
export const getMarket = (id) => api.get(`/markets/${id}`);
export const getSnapshots = (id, params = {}) =>
  api.get(`/markets/${id}/snapshots`, { params });
export const getNewBets = (params = {}) => api.get("/new_bets", { params });
export const exportNewBets = () =>
  api.get("/new_bets/export", { responseType: "blob" });
export const exportNewBetsFiltered = (excludeFile) => {
  const form = new FormData();
  form.append("file", excludeFile);
  return api.post("/new_bets/export", form, {
    responseType: "blob",
    headers: { "Content-Type": "multipart/form-data" },
  });
};
export const getCategories = () => api.get("/markets/categories");
export const getDashboardSummary = () => api.get("/markets/summary");

// --- Tracking ---
export const getTrackedMarkets = () => api.get("/tracked_markets");
export const setTracking = (marketId, body) =>
  api.post(`/tracked_markets/${marketId}`, body);

// --- Jobs ---
export const runCollector = () => api.post("/jobs/collect");
export const getJobStatus = () => api.get("/jobs/status");

// --- Paper Trading ---
export const openTrade = (body) => api.post("/paper_trades/open", body);
export const closeTrade = (body) => api.post("/paper_trades/close", body);
export const getPositions = () => api.get("/paper_positions");
export const getPortfolioSummary = () => api.get("/paper_portfolio/summary");
export const getEquityCurve = (params = {}) => api.get("/paper_portfolio/equity_curve", { params });
export const getEquityCurveDual = () => api.get("/paper_portfolio/equity_curve_dual");
export const getMonteCarlo = (params = {}) =>
  api.get("/monte_carlo", { params, timeout: 60000 });
export const getAllTrades = () => api.get("/paper_trades");

// --- Settings ---
export const getSettings = () => api.get("/settings");
export const updateSettings = (body) => api.post("/settings", body);
export const getExports = () => api.get("/exports");
export const exportAll = () => api.post("/exports/all");

// --- Database ---
export const getDatabaseMarkets = (params = {}) =>
  api.get("/database/markets", { params });
export const getDatabaseSnapshots = (params = {}) =>
  api.get("/database/snapshots", { params });
export const exportDatabaseXlsx = (params = {}) =>
  api.get("/database/export", { params, responseType: "blob" });

// --- DCA ---
export const createDCA = (body) => api.post("/dca", body);
export const getDCAList = (params = {}) => api.get("/dca", { params });
export const cancelDCA = (dcaId) => api.post(`/dca/${dcaId}/cancel`);
export const getDCAAnalytics = (dcaId) => api.get(`/dca/${dcaId}/analytics`);
export const getDCATrades = (params = {}) => api.get("/dca/trades", { params });

// --- Alerts ---
export const getAlerts = (params = {}) => api.get("/alerts", { params });
export const getTriggeredAlerts = () => api.get("/alerts/triggered");
export const createAlert = (body) => api.post("/alerts", body);
export const deleteAlert = (id) => api.delete(`/alerts/${id}`);
export const dismissAlert = (id) => api.post(`/alerts/${id}/dismiss`);
