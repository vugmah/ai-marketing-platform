/**
 * Real API Client - AI Marketing Platform v2.0
 * Connects to FastAPI backend with JWT auth, RBAC, tenant isolation
 */

import { mockApi } from './mockApi';

// ─── Configuration ────────────────────────────────────────────────

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true' || false;

// ─── Types ────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  total?: number;
  page?: number;
  page_size?: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'super_admin' | 'company_admin' | 'branch_manager' | 'marketing_manager' | 'support_agent' | 'analyst';
  status: 'active' | 'inactive' | 'pending';
  company_id?: number;
  branch_id?: number;
  avatar_url?: string;
  created_at: string;
}

export interface Company {
  id: number;
  name: string;
  slug: string;
  industry: string;
  status: 'active' | 'inactive' | 'suspended';
  subscription_tier: 'starter' | 'pro' | 'enterprise' | 'custom';
  max_branches: number;
  max_users: number;
  contact_email: string;
  created_at: string;
  updated_at: string;
}

export interface Branch {
  id: number;
  name: string;
  company_id: number;
  city: string;
  address: string;
  phone: string;
  status: 'active' | 'inactive';
  manager_name: string;
  created_at: string;
  updated_at: string;
}

// ─── HTTP Client ──────────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  if (USE_MOCK) {
    console.warn(`[MOCK] ${options.method || 'GET'} ${endpoint}`);
    return mockRequest<T>(endpoint, options);
  }

  const url = `${API_BASE_URL}${endpoint}`;
  const token = localStorage.getItem('access_token');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...((options.headers as Record<string, string>) || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      error.detail || error.message || `HTTP ${response.status}`,
      error.code
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as T;
}

// ─── Mock Fallback ────────────────────────────────────────────────

async function mockRequest<T>(endpoint: string, options: RequestInit): Promise<T> {
  await new Promise((r) => setTimeout(r, 300));

  const method = options.method || 'GET';
  const body = options.body ? JSON.parse(options.body as string) : {};

  // Auth endpoints
  if (endpoint === '/api/v1/auth/login' && method === 'POST') {
    return mockApi.login(body.email, body.password) as unknown as T;
  }
  if (endpoint === '/api/v1/auth/register' && method === 'POST') {
    return mockApi.register(body) as unknown as T;
  }
  if (endpoint === '/api/v1/auth/refresh' && method === 'POST') {
    return mockApi.refreshToken(body.refresh_token) as unknown as T;
  }
  if (endpoint === '/api/v1/auth/me' && method === 'GET') {
    return mockApi.me() as unknown as T;
  }
  if (endpoint === '/api/v1/auth/logout' && method === 'POST') {
    return mockApi.logout() as unknown as T;
  }

  // Company endpoints
  if (endpoint === '/api/v1/companies' && method === 'GET') {
    return mockApi.getCompanies() as unknown as T;
  }
  if (endpoint === '/api/v1/companies' && method === 'POST') {
    return mockApi.createCompany(body) as unknown as T;
  }
  if (endpoint.match(/\/api\/v1\/companies\/\d+$/) && method === 'GET') {
    const id = parseInt(endpoint.split('/').pop()!);
    return mockApi.getCompany(id) as unknown as T;
  }

  // Branch endpoints
  if (endpoint === '/api/v1/branches' && method === 'GET') {
    return mockApi.getBranches() as unknown as T;
  }
  if (endpoint === '/api/v1/branches' && method === 'POST') {
    return mockApi.createBranch(body) as unknown as T;
  }

  // Health endpoints
  if (endpoint === '/api/health') {
    return { status: 'ok', version: '2.0.0-mock' } as T;
  }
  if (endpoint === '/api/health/db') {
    return { status: 'ok', db: 'connected (mock)' } as T;
  }
  if (endpoint === '/api/health/redis') {
    return { status: 'ok', redis: 'connected (mock)' } as T;
  }

  throw new ApiError(404, `Mock endpoint not found: ${method} ${endpoint}`);
}

// ─── API Methods ──────────────────────────────────────────────────

export const api = {
  // ── Auth ──────────────────────────────────────────────────────
  auth: {
    login: (data: LoginRequest) =>
      request<LoginResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    register: (data: {
      email: string;
      password: string;
      full_name: string;
      role?: string;
      company_id?: number;
      branch_id?: number;
    }) =>
      request<ApiResponse<User>>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    refresh: (refresh_token: string) =>
      request<LoginResponse>('/api/v1/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token }),
      }),

    me: () => request<ApiResponse<User>>('/api/v1/auth/me'),

    logout: () =>
      request<void>('/api/v1/auth/logout', {
        method: 'POST',
      }),
  },

  // ── Companies ─────────────────────────────────────────────────
  companies: {
    list: (params?: { page?: number; page_size?: number; search?: string }) => {
      const query = params
        ? '?' +
          Object.entries(params)
            .filter(([, v]) => v !== undefined)
            .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
            .join('&')
        : '';
      return request<ApiResponse<Company[]>>(`/api/v1/companies${query}`);
    },

    get: (id: number) => request<ApiResponse<Company>>(`/api/v1/companies/${id}`),

    create: (data: Partial<Company>) =>
      request<ApiResponse<Company>>('/api/v1/companies', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    update: (id: number, data: Partial<Company>) =>
      request<ApiResponse<Company>>(`/api/v1/companies/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    delete: (id: number) =>
      request<void>(`/api/v1/companies/${id}`, {
        method: 'DELETE',
      }),
  },

  // ── Branches ──────────────────────────────────────────────────
  branches: {
    list: (params?: { company_id?: number; page?: number; page_size?: number }) => {
      const query = params
        ? '?' +
          Object.entries(params)
            .filter(([, v]) => v !== undefined)
            .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
            .join('&')
        : '';
      return request<ApiResponse<Branch[]>>(`/api/v1/branches${query}`);
    },

    get: (id: number) => request<ApiResponse<Branch>>(`/api/v1/branches/${id}`),

    create: (data: Partial<Branch>) =>
      request<ApiResponse<Branch>>('/api/v1/branches', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    update: (id: number, data: Partial<Branch>) =>
      request<ApiResponse<Branch>>(`/api/v1/branches/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    delete: (id: number) =>
      request<void>(`/api/v1/branches/${id}`, {
        method: 'DELETE',
      }),
  },

  // ── Health ────────────────────────────────────────────────────
  health: {
    check: () => request<{ status: string; version?: string }>('/api/health'),
    db: () => request<{ status: string; db?: string }>('/api/health/db'),
    redis: () => request<{ status: string; redis?: string }>('/api/health/redis'),
  },

  // ── Users ─────────────────────────────────────────────────────
  users: {
    list: (params?: { page?: number; page_size?: number; role?: string; status?: string }) => {
      const query = params
        ? '?' +
          Object.entries(params)
            .filter(([, v]) => v !== undefined)
            .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
            .join('&')
        : '';
      return request<ApiResponse<User[]>>(`/api/v1/users${query}`);
    },

    get: (id: number) => request<ApiResponse<User>>(`/api/v1/users/${id}`),

    create: (data: Partial<User> & { password: string }) =>
      request<ApiResponse<User>>('/api/v1/users', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    update: (id: number, data: Partial<User>) =>
      request<ApiResponse<User>>(`/api/v1/users/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    updateRole: (id: number, role: string) =>
      request<ApiResponse<User>>(`/api/v1/users/${id}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      }),

    delete: (id: number) =>
      request<void>(`/api/v1/users/${id}`, {
        method: 'DELETE',
      }),
  },

  // ── Dashboard ─────────────────────────────────────────────────
  dashboard: {
    stats: () =>
      request<ApiResponse<{
        total_companies: number;
        total_branches: number;
        total_users: number;
        active_campaigns: number;
        revenue_this_month: number;
        engagement_rate: number;
      }>>('/api/v1/dashboard/stats'),

    chart: () =>
      request<ApiResponse<{
        labels: string[];
        revenue: number[];
        orders: number[];
        engagement: number[];
        roas: number[];
      }>>('/api/v1/dashboard/chart'),

    alerts: () =>
      request<ApiResponse<Array<{
        id: string;
        type: 'warning' | 'error' | 'info' | 'success';
        title: string;
        message: string;
        created_at: string;
      }>>>('/api/v1/dashboard/alerts'),
  },
};

// ─── Token Helpers ────────────────────────────────────────────────

export const token = {
  get: () => localStorage.getItem('access_token'),
  set: (t: string) => localStorage.setItem('access_token', t),
  remove: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },
  isValid: () => {
    const t = localStorage.getItem('access_token');
    if (!t) return false;
    try {
      const payload = JSON.parse(atob(t.split('.')[1]));
      return payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  },
};

// ─── Export ───────────────────────────────────────────────────────

export default api;
