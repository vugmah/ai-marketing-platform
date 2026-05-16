/**
 * Unified API client with interceptors, retry logic, and mock fallback.
 * All endpoints target the real backend at /api/v2 by default.
 * Set VITE_USE_MOCK=true to fall back to local mock data.
 */

import {
  mockAuthUser,
  mockBranchList,
  mockStats,
  mockChartData,
  mockRecentOrders,
  mockRevenueBreakdown,
  mockBestProducts,
  mockSalesComparison,
  mockEmployeePerformance,
  mockSystemHealth,
  mockAuditLogs,
  mockSavedReports,
  mockExportHistory,
  mockWeeklyRevenue,
  mockMonthlyRevenue,
  mockCustomerGrowth,
  mockTopCustomers,
  mockDigitalCampaigns,
  mockSocialAccounts,
  mockGoogleRankingData,
  mockBacklinkData,
  mockPageSpeedData,
  mockBehaviorFlowData,
  mockDemographicData,
  mockCustomEventsData,
  mockAlerts,
  mockFinancialOverview,
  mockInventoryStockData,
  mockSupplierData,
  mockInvoicesData,
  mockCompanyList,
} from "./mockApi";

// ═══════════════════════════════════════════════════════════════════════════════
// ENV CONFIG
// ═══════════════════════════════════════════════════════════════════════════════

// Mock fallback: only enabled in development mode AND when VITE_USE_MOCK=true
// Production builds always use the real API regardless of env vars
const USE_MOCK = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK === "true";
const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v2";

// ═══════════════════════════════════════════════════════════════════════════════
// RETRY + FETCH WITH TIMEOUT
// ═══════════════════════════════════════════════════════════════════════════════

const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 300;
const REQUEST_TIMEOUT_MS = 15000;

interface RequestOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}

async function fetchWithTimeout(
  url: string,
  opts: RequestOptions,
  timeoutMs: number
): Promise<Response> {
  return new Promise((resolve, reject) => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      controller.abort();
      reject(new Error("İstek zaman aşımına uğradı (15s)"));
    }, timeoutMs);

    fetch(url, { ...opts, signal: controller.signal })
      .then((res) => {
        clearTimeout(timer);
        resolve(res);
      })
      .catch((err) => {
        clearTimeout(timer);
        reject(err);
      });
  });
}

async function requestWithRetry<T>(
  endpoint: string,
  opts: RequestOptions = {}
): Promise<ApiResponse<T>> {
  const url = `${API_BASE}${endpoint}`;
  const method = opts.method || "GET";

  let lastError: Error | null = null;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      // Exponential backoff
      if (attempt > 0) {
        const delay = INITIAL_BACKOFF_MS * Math.pow(2, attempt - 1);
        await new Promise((r) => setTimeout(r, delay));
        console.warn(`[API] Retry ${attempt + 1}/${MAX_RETRIES} for ${method} ${endpoint}`);
      }

      const token = localStorage.getItem("token");
      const defaultHeaders: Record<string, string> = {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(opts.body ? { "Content-Type": "application/json" } : {}),
        ...opts.headers,
      };

      const res = await fetchWithTimeout(url, { ...opts, headers: defaultHeaders }, REQUEST_TIMEOUT_MS);

      // 401 Unauthorized → redirect to login
      if (res.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/login";
        return { success: false, message: "Oturum süresi doldu, lütfen tekrar giriş yapın." };
      }

      // 403 Forbidden
      if (res.status === 403) {
        return { success: false, message: "Bu işlem için yetkiniz yok." };
      }

      // 404 Not Found
      if (res.status === 404) {
        return { success: false, message: "İstenen kaynak bulunamadı." };
      }

      // 500+ errors → trigger retry
      if (res.status >= 500) {
        const text = await res.text().catch(() => "");
        lastError = new Error(`HTTP ${res.status}: ${text}`);
        continue; // retry
      }

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        return {
          success: false,
          message: json.message || json.detail || `HTTP ${res.status}`,
        };
      }

      return json as ApiResponse<T>;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      // Network errors → retry; abort errors → don't retry
      if (lastError.name === "AbortError") {
        break;
      }
    }
  }

  const msg = lastError?.message || "Bağlantı hatası";
  console.error(`[API] ${method} ${endpoint} failed after ${MAX_RETRIES} attempts:`, msg);
  return { success: false, message: `Bağlantı hatası: ${msg}` };
}

// ═══════════════════════════════════════════════════════════════════════════════
// RESPONSE TYPE
// ═══════════════════════════════════════════════════════════════════════════════

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  total?: number;
  unread_count?: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// MOCK FALLBACK (DEV ONLY)
// ═══════════════════════════════════════════════════════════════════════════════

/** Wraps real API call; falls back to mock in dev when USE_MOCK=true */
async function withMockFallback<T>(
  realCall: () => Promise<ApiResponse<T>>,
  mockCall: () => Promise<ApiResponse<T>>
): Promise<ApiResponse<T>> {
  if (USE_MOCK) {
    console.log("[MOCK] Using mock data for", mockCall.name || "endpoint");
    return mockCall();
  }
  return realCall();
}

// ═══════════════════════════════════════════════════════════════════════════════
// AUTH API
// ═══════════════════════════════════════════════════════════════════════════════

async function loginReal(
  email: string,
  password: string
): Promise<ApiResponse<{ token: string; user: any }>> {
  return requestWithRetry("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

async function meReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/auth/me");
}

async function registerReal(payload: { email: string; password: string; name: string; company_name: string }): Promise<ApiResponse<any>> {
  return requestWithRetry("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// DASHBOARD API
// ═══════════════════════════════════════════════════════════════════════════════

async function statsReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/dashboard/summary");
}

async function chartReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/dashboard/chart");
}

async function alertsReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/dashboard/alerts");
}

// ═══════════════════════════════════════════════════════════════════════════════
// BRANCHES API
// ═══════════════════════════════════════════════════════════════════════════════

async function listBranchesReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/branches");
}

async function createBranchReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/branches", { method: "POST", body: JSON.stringify(payload) });
}

async function updateBranchReal(id: string, payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry(`/branches/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

async function deleteBranchReal(id: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/branches/${id}`, { method: "DELETE" });
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPANIES API
// ═══════════════════════════════════════════════════════════════════════════════

async function listCompaniesReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/companies");
}

async function createCompanyReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/companies", { method: "POST", body: JSON.stringify(payload) });
}

async function updateCompanyReal(id: string, payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry(`/companies/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

async function deleteCompanyReal(id: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/companies/${id}`, { method: "DELETE" });
}

// ═══════════════════════════════════════════════════════════════════════════════
// NOTIFICATIONS API
// ═══════════════════════════════════════════════════════════════════════════════

async function listNotificationsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/notifications");
}

async function markNotificationReadReal(id: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/notifications/${id}/read`, { method: "POST" });
}

// ═══════════════════════════════════════════════════════════════════════════════
// ANALYTICS API
// ═══════════════════════════════════════════════════════════════════════════════

async function analyticsOverviewReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/analytics/overview");
}

async function analyticsTrafficReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/analytics/traffic");
}

async function analyticsAudienceReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/analytics/audience");
}

async function analyticsPagesReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/analytics/pages");
}

async function analyticsSourcesReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/analytics/sources");
}

async function analyticsDevicesReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/analytics/devices");
}

async function analyticsLocationsReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/analytics/locations");
}

async function generateCustomReportReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/analytics/custom-report", { method: "POST", body: JSON.stringify(payload) });
}

// ═══════════════════════════════════════════════════════════════════════════════
// ADS API
// ═══════════════════════════════════════════════════════════════════════════════

async function adsOverviewReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/ads/overview");
}

async function adsCampaignsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/ads/campaigns");
}

async function adsCreateCampaignReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/ads/campaigns", { method: "POST", body: JSON.stringify(payload) });
}

async function adsUpdateCampaignReal(id: string, payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry(`/ads/campaigns/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

async function adsDeleteCampaignReal(id: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/ads/campaigns/${id}`, { method: "DELETE" });
}

async function adsOptimizationTipsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/ads/optimization-tips");
}

async function adsSpendTrendReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/ads/spend-trend");
}

async function adsPlatformBreakdownReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/ads/platform-breakdown");
}

// ═══════════════════════════════════════════════════════════════════════════════
// SOCIAL MEDIA API
// ═══════════════════════════════════════════════════════════════════════════════

async function socialAccountsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/social/accounts");
}

async function socialPostsReal(status?: string): Promise<ApiResponse<any[]>> {
  const qs = status ? `?status=${status}` : "";
  return requestWithRetry(`/social/posts${qs}`);
}

async function socialCreatePostReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/social/posts", { method: "POST", body: JSON.stringify(payload) });
}

async function socialEngagementReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/social/engagement");
}

async function socialCompetitorsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/social/competitors");
}

async function socialSchedulePostReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/social/schedule", { method: "POST", body: JSON.stringify(payload) });
}

// ═══════════════════════════════════════════════════════════════════════════════
// USERS API
// ═══════════════════════════════════════════════════════════════════════════════

async function usersListReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/users");
}

async function usersCreateReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/users", { method: "POST", body: JSON.stringify(payload) });
}

async function usersUpdateReal(id: string, payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry(`/users/${id}`, { method: "PUT", body: JSON.stringify(payload) });
}

async function usersDeleteReal(id: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/users/${id}`, { method: "DELETE" });
}

async function usersInviteReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/users/invite", { method: "POST", body: JSON.stringify(payload) });
}

async function usersRolesReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/users/roles");
}

async function usersPermissionsReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/users/permissions");
}

// ═══════════════════════════════════════════════════════════════════════════════
// SUPPORT / CHAT INBOX API
// ═══════════════════════════════════════════════════════════════════════════════

async function supportConversationsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/support/conversations");
}

async function supportMessagesReal(convId: string): Promise<ApiResponse<any[]>> {
  return requestWithRetry(`/support/conversations/${convId}/messages`);
}

async function supportSendMessageReal(convId: string, payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry(`/support/conversations/${convId}/messages`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function supportCloseConversationReal(convId: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/support/conversations/${convId}/close`, { method: "POST" });
}

async function supportAssignReal(convId: string, userId: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/support/conversations/${convId}/assign`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// CREATIVE STUDIO API
// ═══════════════════════════════════════════════════════════════════════════════

async function creativeFeaturesReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/creative/features");
}

async function creativeGeneratedContentReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/creative/generated-content");
}

async function creativeGenerateReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/creative/generate", { method: "POST", body: JSON.stringify(payload) });
}

async function creativeAuditReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/creative/audit");
}

async function creativeCalendarReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/creative/calendar");
}

async function creativeFormatsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/creative/formats");
}

// ═══════════════════════════════════════════════════════════════════════════════
// AI REPORTS API
// ═══════════════════════════════════════════════════════════════════════════════

async function aiReportsOverviewReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/ai-reports/overview");
}

async function aiReportsTrendsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/ai-reports/trends");
}

async function aiReportsRecommendationsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/ai-reports/recommendations");
}

async function aiReportsForecastReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/ai-reports/revenue-forecast");
}

async function aiReportsHistoryReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/ai-reports/history");
}

async function aiReportsGenerateReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/ai-reports/generate", { method: "POST", body: JSON.stringify(payload) });
}

// ═══════════════════════════════════════════════════════════════════════════════
// SETTINGS API
// ═══════════════════════════════════════════════════════════════════════════════

async function settingsGetReal(): Promise<ApiResponse<any>> {
  return requestWithRetry("/settings");
}

async function settingsUpdateReal(payload: any): Promise<ApiResponse<any>> {
  return requestWithRetry("/settings", { method: "PUT", body: JSON.stringify(payload) });
}

async function settingsIntegrationsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/settings/integrations");
}

async function settingsToggleIntegrationReal(id: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/settings/integrations/${id}/toggle`, { method: "POST" });
}

async function settingsApiKeysReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/settings/api-keys");
}

async function settingsSessionsReal(): Promise<ApiResponse<any[]>> {
  return requestWithRetry("/settings/sessions");
}

async function settingsTerminateSessionReal(id: string): Promise<ApiResponse<any>> {
  return requestWithRetry(`/settings/sessions/${id}/terminate`, { method: "POST" });
}

// ═══════════════════════════════════════════════════════════════════════════════
// TOKEN HELPER
// ═══════════════════════════════════════════════════════════════════════════════

export const token = {
  get: () => localStorage.getItem("token"),
  set: (t: string) => localStorage.setItem("token", t),
  remove: () => localStorage.removeItem("token"),
  exists: () => !!localStorage.getItem("token"),
};

// ═══════════════════════════════════════════════════════════════════════════════
// AUTH REFRESH
// ═══════════════════════════════════════════════════════════════════════════════

async function refreshTokenReal(refreshToken: string): Promise<ApiResponse<any>> {
  return requestWithRetry("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// EXPORTED API OBJECT
// ═══════════════════════════════════════════════════════════════════════════════

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────
  auth: {
    login: (email: string, password: string) =>
      withMockFallback(() => loginReal(email, password), async () => ({
        success: true,
        data: { token: "mock-jwt-token", user: mockAuthUser },
      })),
    me: () =>
      withMockFallback(() => meReal(), async () => ({
        success: true,
        data: mockAuthUser,
      })),
    register: (payload: { email: string; password: string; name: string; company_name: string }) =>
      withMockFallback(() => registerReal(payload), async () => ({
        success: true,
        data: { token: "mock-jwt-token", user: mockAuthUser },
      })),
    refresh: (refreshToken: string) =>
      withMockFallback(() => refreshTokenReal(refreshToken), async () => ({
        success: true,
        data: { access_token: "mock-jwt-token", refresh_token: "mock-refresh-token" },
      })),
  },

  // ── Dashboard ─────────────────────────────────────────────────────────
  dashboard: {
    stats: () =>
      withMockFallback(() => statsReal(), async () => ({
        success: true,
        data: mockStats,
      })),
    chart: () =>
      withMockFallback(() => chartReal(), async () => ({
        success: true,
        data: mockChartData,
      })),
    alerts: () =>
      withMockFallback(() => alertsReal(), async () => ({
        success: true,
        data: mockAlerts,
      })),
  },

  // ── Branches ──────────────────────────────────────────────────────────
  branches: {
    list: () =>
      withMockFallback(() => listBranchesReal(), async () => ({
        success: true,
        data: mockBranchList,
      })),
    create: (payload: any) =>
      withMockFallback(() => createBranchReal(payload), async () => ({
        success: true,
        data: { id: Date.now(), ...payload },
      })),
    update: (id: string, payload: any) =>
      withMockFallback(() => updateBranchReal(id, payload), async () => ({
        success: true,
        data: payload,
      })),
    delete: (id: string) =>
      withMockFallback(() => deleteBranchReal(id), async () => ({
        success: true,
        data: { deleted: true },
      })),
  },

  // ── Companies ─────────────────────────────────────────────────────────
  companies: {
    list: () =>
      withMockFallback(() => listCompaniesReal(), async () => ({
        success: true,
        data: mockCompanyList,
      })),
    create: (payload: any) =>
      withMockFallback(() => createCompanyReal(payload), async () => ({
        success: true,
        data: { id: Date.now(), ...payload },
      })),
    update: (id: string, payload: any) =>
      withMockFallback(() => updateCompanyReal(id, payload), async () => ({
        success: true,
        data: payload,
      })),
    delete: (id: string) =>
      withMockFallback(() => deleteCompanyReal(id), async () => ({
        success: true,
        data: { deleted: true },
      })),
  },

  // ── Notifications ─────────────────────────────────────────────────────
  notifications: {
    list: () =>
      withMockFallback(() => listNotificationsReal(), async () => ({
        success: true,
        data: mockAlerts,
        unread_count: mockAlerts.length,
      })),
    markRead: (id: string) =>
      withMockFallback(() => markNotificationReadReal(id), async () => ({
        success: true,
        data: { marked: true },
      })),
  },

  // ── Analytics ─────────────────────────────────────────────────────────
  analytics: {
    overview: () =>
      withMockFallback(() => analyticsOverviewReal(), async () => ({
        success: true,
        data: {
          total_views: 45230,
          avg_session: "3dk 42sn",
          bounce_rate: 38.2,
          unique_visitors: 12450,
        },
      })),
    traffic: () =>
      withMockFallback(() => analyticsTrafficReal(), async () => ({
        success: true,
        data: { visitorTrend: mockChartData, sources: mockRevenueBreakdown },
      })),
    audience: () =>
      withMockFallback(() => analyticsAudienceReal(), async () => ({
        success: true,
        data: { devices: mockRevenueBreakdown, locations: mockBestProducts },
      })),
    pages: () =>
      withMockFallback(() => analyticsPagesReal(), async () => ({
        success: true,
        data: mockBestProducts,
      })),
    sources: () =>
      withMockFallback(() => analyticsSourcesReal(), async () => ({
        success: true,
        data: mockRevenueBreakdown,
      })),
    devices: () =>
      withMockFallback(() => analyticsDevicesReal(), async () => ({
        success: true,
        data: mockRevenueBreakdown,
      })),
    locations: () =>
      withMockFallback(() => analyticsLocationsReal(), async () => ({
        success: true,
        data: mockBestProducts,
      })),
    customReport: (payload: any) =>
      withMockFallback(() => generateCustomReportReal(payload), async () => ({
        success: true,
        data: { report_id: Date.now() },
      })),
  },

  // ── Ads ───────────────────────────────────────────────────────────────
  ads: {
    overview: () =>
      withMockFallback(() => adsOverviewReal(), async () => ({
        success: true,
        data: {
          total_spent: 54600,
          avg_roas: 3.5,
          total_impressions: 62600,
          total_clicks: 4100,
        },
      })),
    campaigns: () =>
      withMockFallback(() => adsCampaignsReal(), async () => ({
        success: true,
        data: mockDigitalCampaigns,
      })),
    createCampaign: (payload: any) =>
      withMockFallback(() => adsCreateCampaignReal(payload), async () => ({
        success: true,
        data: { id: Date.now(), ...payload },
      })),
    updateCampaign: (id: string, payload: any) =>
      withMockFallback(() => adsUpdateCampaignReal(id, payload), async () => ({
        success: true,
        data: payload,
      })),
    deleteCampaign: (id: string) =>
      withMockFallback(() => adsDeleteCampaignReal(id), async () => ({
        success: true,
        data: { deleted: true },
      })),
    optimizationTips: () =>
      withMockFallback(() => adsOptimizationTipsReal(), async () => ({
        success: true,
        data: mockRecentOrders.slice(0, 4),
      })),
    spendTrend: () =>
      withMockFallback(() => adsSpendTrendReal(), async () => ({
        success: true,
        data: mockChartData,
      })),
    platformBreakdown: () =>
      withMockFallback(() => adsPlatformBreakdownReal(), async () => ({
        success: true,
        data: mockRevenueBreakdown,
      })),
  },

  // ── Social Media ──────────────────────────────────────────────────────
  social: {
    accounts: () =>
      withMockFallback(() => socialAccountsReal(), async () => ({
        success: true,
        data: mockSocialAccounts,
      })),
    posts: (status?: string) =>
      withMockFallback(() => socialPostsReal(status), async () => ({
        success: true,
        data: mockRecentOrders,
      })),
    createPost: (payload: any) =>
      withMockFallback(() => socialCreatePostReal(payload), async () => ({
        success: true,
        data: { id: Date.now(), ...payload },
      })),
    engagement: () =>
      withMockFallback(() => socialEngagementReal(), async () => ({
        success: true,
        data: mockChartData,
      })),
    competitors: () =>
      withMockFallback(() => socialCompetitorsReal(), async () => ({
        success: true,
        data: mockSocialAccounts,
      })),
    schedule: (payload: any) =>
      withMockFallback(() => socialSchedulePostReal(payload), async () => ({
        success: true,
        data: { id: Date.now(), ...payload },
      })),
  },

  // ── Users ─────────────────────────────────────────────────────────────
  users: {
    list: () =>
      withMockFallback(() => usersListReal(), async () => ({
        success: true,
        data: mockEmployeePerformance,
      })),
    create: (payload: any) =>
      withMockFallback(() => usersCreateReal(payload), async () => ({
        success: true,
        data: { id: Date.now(), ...payload },
      })),
    update: (id: string, payload: any) =>
      withMockFallback(() => usersUpdateReal(id, payload), async () => ({
        success: true,
        data: payload,
      })),
    delete: (id: string) =>
      withMockFallback(() => usersDeleteReal(id), async () => ({
        success: true,
        data: { deleted: true },
      })),
    invite: (payload: any) =>
      withMockFallback(() => usersInviteReal(payload), async () => ({
        success: true,
        data: { invited: true },
      })),
    roles: () =>
      withMockFallback(() => usersRolesReal(), async () => ({
        success: true,
        data: mockSystemHealth,
      })),
    permissions: () =>
      withMockFallback(() => usersPermissionsReal(), async () => ({
        success: true,
        data: mockAuditLogs,
      })),
  },

  // ── Support / Chat Inbox ──────────────────────────────────────────────
  support: {
    conversations: () =>
      withMockFallback(() => supportConversationsReal(), async () => ({
        success: true,
        data: mockRecentOrders,
      })),
    messages: (convId: string) =>
      withMockFallback(() => supportMessagesReal(convId), async () => ({
        success: true,
        data: mockRecentOrders,
      })),
    sendMessage: (convId: string, payload: any) =>
      withMockFallback(() => supportSendMessageReal(convId, payload), async () => ({
        success: true,
        data: { id: Date.now(), ...payload },
      })),
    closeConversation: (convId: string) =>
      withMockFallback(() => supportCloseConversationReal(convId), async () => ({
        success: true,
        data: { closed: true },
      })),
    assign: (convId: string, userId: string) =>
      withMockFallback(() => supportAssignReal(convId, userId), async () => ({
        success: true,
        data: { assigned: true },
      })),
  },

  // ── Creative Studio ───────────────────────────────────────────────────
  creative: {
    features: () =>
      withMockFallback(() => creativeFeaturesReal(), async () => ({
        success: true,
        data: mockSystemHealth,
      })),
    generatedContent: () =>
      withMockFallback(() => creativeGeneratedContentReal(), async () => ({
        success: true,
        data: mockRecentOrders,
      })),
    generate: (payload: any) =>
      withMockFallback(() => creativeGenerateReal(payload), async () => ({
        success: true,
        data: { id: Date.now(), ...payload },
      })),
    audit: () =>
      withMockFallback(() => creativeAuditReal(), async () => ({
        success: true,
        data: { score: 78 },
      })),
    calendar: () =>
      withMockFallback(() => creativeCalendarReal(), async () => ({
        success: true,
        data: mockChartData,
      })),
    formats: () =>
      withMockFallback(() => creativeFormatsReal(), async () => ({
        success: true,
        data: mockSystemHealth,
      })),
  },

  // ── AI Reports ────────────────────────────────────────────────────────
  aiReports: {
    overview: () =>
      withMockFallback(() => aiReportsOverviewReal(), async () => ({
        success: true,
        data: {
          active_insights: 23,
          revenue_forecast: "+18%",
          forecast_roas: "3.2x",
          pending_recommendations: 5,
        },
      })),
    trends: () =>
      withMockFallback(() => aiReportsTrendsReal(), async () => ({
        success: true,
        data: mockBestProducts,
      })),
    recommendations: () =>
      withMockFallback(() => aiReportsRecommendationsReal(), async () => ({
        success: true,
        data: mockRecentOrders.slice(0, 3),
      })),
    forecast: () =>
      withMockFallback(() => aiReportsForecastReal(), async () => ({
        success: true,
        data: mockChartData,
      })),
    history: () =>
      withMockFallback(() => aiReportsHistoryReal(), async () => ({
        success: true,
        data: mockSavedReports,
      })),
    generate: (payload: any) =>
      withMockFallback(() => aiReportsGenerateReal(payload), async () => ({
        success: true,
        data: { report_id: Date.now() },
      })),
  },

  // ── Settings ──────────────────────────────────────────────────────────
  settings: {
    get: () =>
      withMockFallback(() => settingsGetReal(), async () => ({
        success: true,
        data: mockSystemHealth,
      })),
    update: (payload: any) =>
      withMockFallback(() => settingsUpdateReal(payload), async () => ({
        success: true,
        data: payload,
      })),
    integrations: () =>
      withMockFallback(() => settingsIntegrationsReal(), async () => ({
        success: true,
        data: mockSystemHealth,
      })),
    toggleIntegration: (id: string) =>
      withMockFallback(() => settingsToggleIntegrationReal(id), async () => ({
        success: true,
        data: { toggled: true },
      })),
    apiKeys: () =>
      withMockFallback(() => settingsApiKeysReal(), async () => ({
        success: true,
        data: mockSystemHealth,
      })),
    sessions: () =>
      withMockFallback(() => settingsSessionsReal(), async () => ({
        success: true,
        data: mockSystemHealth,
      })),
    terminateSession: (id: string) =>
      withMockFallback(() => settingsTerminateSessionReal(id), async () => ({
        success: true,
        data: { terminated: true },
      })),
  },
};
