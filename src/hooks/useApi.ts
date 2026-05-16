/**
 * useApi - Production-ready API hook with retry, offline detection,
 * loading states, and exponential backoff.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import { api, token } from "@/lib/api";

// ─── Types ───────────────────────────────────────────────

export interface UseApiOptions {
  retries?: number;
  retryDelayMs?: number;
  retryCondition?: (error: unknown) => boolean;
  onError?: (error: unknown) => void;
  onSuccess?: (data: unknown) => void;
}

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  retryCount: number;
  isOffline: boolean;
  isRetrying: boolean;
}

// ─── Offline Detection ───────────────────────────────────

let globalOffline = false;
const offlineListeners = new Set<(offline: boolean) => void>();

function notifyOfflineListeners(offline: boolean) {
  globalOffline = offline;
  offlineListeners.forEach((fn) => fn(offline));
}

function setupOfflineListeners() {
  const handleOnline = () => notifyOfflineListeners(false);
  const handleOffline = () => notifyOfflineListeners(true);

  window.addEventListener("online", handleOnline);
  window.addEventListener("offline", handleOffline);

  return () => {
    window.removeEventListener("online", handleOnline);
    window.removeEventListener("offline", handleOffline);
  };
}

let cleanupOfflineListeners: (() => void) | null = null;

function getCleanup() {
  if (!cleanupOfflineListeners) {
    cleanupOfflineListeners = setupOfflineListeners();
  }
  return cleanupOfflineListeners;
}

// ─── Retry Logic ─────────────────────────────────────────

const DEFAULT_RETRY_COUNT = 3;
const DEFAULT_RETRY_DELAY_MS = 1000;

function isRetryableError(error: unknown): boolean {
  if (error instanceof Response) {
    return error.status >= 500 || error.status === 429 || error.status === 408;
  }
  if (error instanceof Error) {
    return (
      error.message.includes("network") ||
      error.message.includes("fetch") ||
      error.message.includes("timeout") ||
      error.message.includes("abort")
    );
  }
  return true;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─── Main Hook ───────────────────────────────────────────

export function useApi<T>(
  fetchFn: () => Promise<T>,
  options: UseApiOptions = {}
): ApiState<T> & {
  refetch: () => Promise<void>;
  execute: <R>(fn: () => Promise<R>) => Promise<R | null>;
} {
  const {
    retries = DEFAULT_RETRY_COUNT,
    retryDelayMs = DEFAULT_RETRY_DELAY_MS,
    retryCondition = isRetryableError,
    onError,
    onSuccess,
  } = options;

  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: true,
    error: null,
    retryCount: 0,
    isOffline: !navigator.onLine,
    isRetrying: false,
  });

  const abortRef = useRef<AbortController | null>(null);
  const isMounted = useRef(true);

  // Offline detection
  useEffect(() => {
    getCleanup();
    const handler = (offline: boolean) => {
      if (isMounted.current) {
        setState((prev) => ({ ...prev, isOffline: offline }));
      }
    };
    offlineListeners.add(handler);
    return () => {
      offlineListeners.delete(handler);
    };
  }, []);

  // Mount tracking
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
  }, []);

  // Execute any API call with retry logic
  const execute = useCallback(
    async <R,>(fn: () => Promise<R>): Promise<R | null> => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
      const controller = new AbortController();
      abortRef.current = controller;

      setState((prev) => ({
        ...prev,
        loading: true,
        error: null,
        retryCount: 0,
        isRetrying: false,
      }));

      let lastError: unknown;
      for (let attempt = 0; attempt <= retries; attempt++) {
        if (controller.signal.aborted) return null;

        try {
          const result = await fn();
          if (isMounted.current && !controller.signal.aborted) {
            setState((prev) => ({
              ...prev,
              data: result as unknown as T,
              loading: false,
              error: null,
              isRetrying: false,
            }));
            onSuccess?.(result);
          }
          return result;
        } catch (err) {
          lastError = err;

          const shouldRetry =
            attempt < retries &&
            retryCondition(err) &&
            !controller.signal.aborted;

          if (shouldRetry) {
            const backoffDelay = retryDelayMs * Math.pow(2, attempt);
            if (isMounted.current) {
              setState((prev) => ({
                ...prev,
                isRetrying: true,
                retryCount: attempt + 1,
              }));
            }
            await delay(backoffDelay);
            continue;
          }

          break;
        }
      }

      if (isMounted.current && !controller.signal.aborted) {
        const message =
          lastError instanceof Error
            ? lastError.message
            : "An unexpected error occurred";
        setState((prev) => ({
          ...prev,
          loading: false,
          error: message,
          isRetrying: false,
          retryCount: 0,
        }));
        onError?.(lastError);
      }
      return null;
    },
    [retries, retryDelayMs, retryCondition, onError, onSuccess]
  );

  // Initial fetch
  useEffect(() => {
    execute(fetchFn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refetch function
  const refetch = useCallback(async () => {
    await execute(fetchFn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [execute]);

  return {
    ...state,
    refetch,
    execute,
  };
}

// ─── Mutation Hook ───────────────────────────────────────

export function useApiMutation<T, R>(
  mutateFn: (data: T) => Promise<R>,
  options: UseApiOptions = {}
) {
  const [state, setState] = useState<{
    data: R | null;
    loading: boolean;
    error: string | null;
  }>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (data: T): Promise<R | null> => {
      setState({ data: null, loading: true, error: null });
      try {
        const result = await mutateFn(data);
        setState({ data: result, loading: false, error: null });
        options.onSuccess?.(result);
        return result;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "An unexpected error occurred";
        setState({ data: null, loading: false, error: message });
        options.onError?.(err);
        return null;
      }
    },
    [mutateFn, options]
  );

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
  }, []);

  return { ...state, execute, reset };
}

// ─── Token Refresh Hook ──────────────────────────────────

export function useTokenRefresh() {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refresh = useCallback(async (): Promise<boolean> => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) {
      token.remove();
      return false;
    }

    setIsRefreshing(true);
    try {
      const response = await api.auth.refresh(refreshToken);
      if (response.access_token) {
        token.set(response.access_token);
        localStorage.setItem("refresh_token", response.refresh_token);
        setIsRefreshing(false);
        return true;
      }
      token.remove();
      setIsRefreshing(false);
      return false;
    } catch {
      token.remove();
      setIsRefreshing(false);
      return false;
    }
  }, []);

  return { refresh, isRefreshing };
}

// ─── Auto Refresh on Focus ───────────────────────────────

export function useRefreshOnFocus(refetch: () => Promise<void>) {
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refetch();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [refetch]);
}
