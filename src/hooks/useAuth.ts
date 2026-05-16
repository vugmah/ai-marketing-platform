/**
 * useAuth - Authentication hook with token refresh, session management,
 * and automatic logout on token expiry.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api, token } from "@/lib/api";
import type { User } from "@/lib/api";

// ─── Types ───────────────────────────────────────────────

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  full_name: string;
  role?: string;
  company_id?: number;
  branch_id?: number;
}

const AUTH_STATE_KEY = "auth_state";
const SESSION_EXPIRY_BUFFER = 5 * 60 * 1000; // 5 min buffer

// ─── Helper Functions ────────────────────────────────────

function getTokenExpiry(tokenStr: string): number | null {
  try {
    const payload = JSON.parse(atob(tokenStr.split(".")[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

function scheduleTokenRefresh(expiryMs: number, callback: () => void): number {
  const refreshTime = expiryMs - Date.now() - SESSION_EXPIRY_BUFFER;
  const delayMs = Math.max(refreshTime, 1000);
  return window.setTimeout(callback, delayMs);
}

// ─── Main Hook ───────────────────────────────────────────

export function useAuth() {
  const navigate = useNavigate();
  const refreshTimerRef = useRef<number | null>(null);

  const [state, setState] = useState<AuthState>(() => {
    try {
      const saved = sessionStorage.getItem(AUTH_STATE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return {
          user: parsed.user || null,
          isAuthenticated: !!parsed.user && token.isValid(),
          isLoading: false,
          error: null,
        };
      }
    } catch {
      // ignore parse errors
    }
    return {
      user: null,
      isAuthenticated: false,
      isLoading: true,
      error: null,
    };
  });

  // Persist auth state
  useEffect(() => {
    if (state.user) {
      sessionStorage.setItem(
        AUTH_STATE_KEY,
        JSON.stringify({ user: state.user })
      );
    } else {
      sessionStorage.removeItem(AUTH_STATE_KEY);
    }
  }, [state.user]);

  // Check token validity on mount & schedule refresh
  useEffect(() => {
    const tokenStr = token.get();
    if (!tokenStr) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        isAuthenticated: false,
      }));
      return;
    }

    const expiry = getTokenExpiry(tokenStr);
    if (expiry && expiry <= Date.now()) {
      token.remove();
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
      return;
    }

    // Schedule token refresh
    if (expiry) {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
      refreshTimerRef.current = scheduleTokenRefresh(expiry, () => {
        handleRefresh();
      });
    }

    // Fetch current user
    fetchUser();

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchUser = useCallback(async () => {
    try {
      const response = await api.auth.me();
      if (response.success) {
        setState({
          user: response.data,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
      } else {
        throw new Error("Session expired");
      }
    } catch {
      token.remove();
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  }, []);

  const handleRefresh = useCallback(async (): Promise<boolean> => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) {
      logout();
      return false;
    }

    try {
      const response = await api.auth.refresh(refreshToken);
      if (response.access_token) {
        token.set(response.access_token);
        localStorage.setItem("refresh_token", response.refresh_token);

        // Re-schedule next refresh
        const expiry = getTokenExpiry(response.access_token);
        if (expiry && refreshTimerRef.current) {
          clearTimeout(refreshTimerRef.current);
          refreshTimerRef.current = scheduleTokenRefresh(expiry, () => {
            handleRefresh();
          });
        }

        setState((prev) => ({ ...prev, isAuthenticated: true }));
        return true;
      }
    } catch {
      // refresh failed
    }

    logout();
    return false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    async (credentials: LoginCredentials): Promise<boolean> => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const response = await api.auth.login(credentials);
        if (response.access_token) {
          token.set(response.access_token);
          localStorage.setItem("refresh_token", response.refresh_token);

          // Schedule token refresh
          const expiry = getTokenExpiry(response.access_token);
          if (expiry) {
            if (refreshTimerRef.current) {
              clearTimeout(refreshTimerRef.current);
            }
            refreshTimerRef.current = scheduleTokenRefresh(expiry, () => {
              handleRefresh();
            });
          }

          setState({
            user: response.user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
          return true;
        }
        throw new Error("Invalid response from server");
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Login failed";
        setState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: message,
        });
        return false;
      }
    },
    [handleRefresh]
  );

  const register = useCallback(
    async (data: RegisterData): Promise<boolean> => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const response = await api.auth.register(data);
        if (response.success) {
          setState((prev) => ({ ...prev, isLoading: false }));
          return true;
        }
        throw new Error("Registration failed");
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Registration failed";
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: message,
        }));
        return false;
      }
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // ignore logout errors
    } finally {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
      token.remove();
      sessionStorage.removeItem(AUTH_STATE_KEY);
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
      navigate("/login");
    }
  }, [navigate]);

  const updateUser = useCallback((user: Partial<User>) => {
    setState((prev) => ({
      ...prev,
      user: prev.user ? { ...prev.user, ...user } : null,
    }));
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    login,
    register,
    logout,
    refresh: handleRefresh,
    updateUser,
    clearError,
  };
}

// ─── Auth Context ─────────────────────────────────────────

import { createContext, useContext } from "react";

export interface AuthContextValue extends ReturnType<typeof useAuth> {}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuthContext must be used within AuthProvider");
  }
  return ctx;
}
