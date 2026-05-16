/**
 * useNetworkStatus - React hook for online/offline detection
 * Provides network state with auto-reconnect notifications.
 */
import { useState, useEffect, useCallback, useRef } from "react";

interface NetworkState {
  isOnline: boolean;
  wasOffline: boolean;
  isSlowConnection: boolean;
}

const listeners = new Set<(state: NetworkState) => void>();

let cachedState: NetworkState = {
  isOnline: navigator.onLine,
  wasOffline: false,
  isSlowConnection: false,
};

function notifyListeners() {
  listeners.forEach((cb) => cb({ ...cachedState }));
}

export function useNetworkStatus() {
  const [state, setState] = useState<NetworkState>({ ...cachedState });
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    listeners.add(setState);
    return () => {
      listeners.delete(setState);
    };
  }, []);

  // Listen for online/offline events
  useEffect(() => {
    const handleOnline = () => {
      cachedState = {
        ...cachedState,
        isOnline: true,
        wasOffline: !cachedState.isOnline,
        isSlowConnection: false,
      };
      notifyListeners();
    };

    const handleOffline = () => {
      cachedState = {
        ...cachedState,
        isOnline: false,
        wasOffline: false,
      };
      notifyListeners();
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
      }
    };
  }, []);

  // Auto-clear wasOffline flag after notification
  useEffect(() => {
    if (state.wasOffline) {
      retryTimerRef.current = setTimeout(() => {
        cachedState = { ...cachedState, wasOffline: false };
        setState({ ...cachedState });
      }, 5000);
      return () => {
        if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      };
    }
  }, [state.wasOffline]);

  const checkConnection = useCallback(async (): Promise<boolean> => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      await fetch("/api/v2/health", {
        method: "HEAD",
        signal: controller.signal,
        cache: "no-store",
      });
      clearTimeout(timeout);
      return true;
    } catch {
      // Fallback: just check navigator.onLine
      return navigator.onLine;
    }
  }, []);

  return {
    ...state,
    checkConnection,
  };
}

export { cachedState as currentNetworkState };
