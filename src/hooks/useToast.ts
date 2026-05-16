/**
 * useToast - Toast notification system built on sonner
 * Provides a typed, consistent interface for toast notifications.
 */
import { toast as sonnerToast } from "sonner";

// ─── Types ───────────────────────────────────────────────

export type ToastType = "success" | "error" | "warning" | "info" | "loading";

export interface ToastOptions {
  description?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
  id?: string;
}

export interface ToastPromiseOptions<T> {
  loading: string;
  success: (data: T) => string;
  error: (err: Error) => string;
}

// ─── Toast Helpers ───────────────────────────────────────

function createId(): string {
  return `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function normalizeOptions(
  options?: ToastOptions
): {
  description?: string;
  duration?: number;
  id?: string;
  action?: { label: string; onClick: () => void };
} {
  return {
    description: options?.description,
    duration: options?.duration ?? 4000,
    id: options?.id,
    action: options?.action,
  };
}

// ─── Toast API ───────────────────────────────────────────

export const toast = {
  success(message: string, options?: ToastOptions) {
    return sonnerToast.success(message, normalizeOptions(options));
  },

  error(message: string, options?: ToastOptions) {
    return sonnerToast.error(message, {
      ...normalizeOptions(options),
      duration: options?.duration ?? 6000,
    });
  },

  warning(message: string, options?: ToastOptions) {
    return sonnerToast.warning(message, normalizeOptions(options));
  },

  info(message: string, options?: ToastOptions) {
    return sonnerToast.info(message, normalizeOptions(options));
  },

  loading(message: string, options?: ToastOptions) {
    return sonnerToast.loading(message, normalizeOptions(options));
  },

  /** Show a toast that auto-dismisses after a promise resolves */
  promise<T>(
    promise: Promise<T>,
    options: ToastPromiseOptions<T>
  ) {
    return sonnerToast.promise(promise, {
      loading: options.loading,
      success: options.success,
      error: options.error,
    });
  },

  /** Custom toast with full control */
  custom(message: string, options?: ToastOptions & { type?: ToastType }) {
    return sonnerToast(message, {
      ...normalizeOptions(options),
    });
  },

  /** Dismiss all toasts or a specific one */
  dismiss(id?: string) {
    if (id) {
      sonnerToast.dismiss(id);
    } else {
      sonnerToast.dismiss();
    }
  },

  /** Update an existing toast */
  update(id: string, message: string, type: ToastType = "info", options?: ToastOptions) {
    sonnerToast.dismiss(id);
    const opts = normalizeOptions(options);
    switch (type) {
      case "success":
        return sonnerToast.success(message, opts);
      case "error":
        return sonnerToast.error(message, opts);
      case "warning":
        return sonnerToast.warning(message, opts);
      default:
        return sonnerToast.info(message, opts);
    }
  },

  /** Show a persistent toast that doesn't auto-dismiss */
  persistent(message: string, type: ToastType = "info", options?: Omit<ToastOptions, "duration">) {
    return sonnerToast(message, {
      ...normalizeOptions(options),
      duration: Infinity,
    });
  },
};

// ─── Convenience Hook ────────────────────────────────────

export function useToast() {
  return toast;
}

// ─── Pre-built patterns ──────────────────────────────────

export const notify = {
  /** Notify about a successful API operation */
  apiSuccess(message: string, description?: string) {
    return toast.success(message, { description, duration: 3000 });
  },

  /** Notify about an API error */
  apiError(message: string, description?: string) {
    return toast.error(message, {
      description,
      duration: 6000,
    });
  },

  /** Notify about validation errors */
  validation(errors: string[]) {
    errors.forEach((err, i) => {
      setTimeout(() => toast.warning(err, { duration: 5000 }), i * 100);
    });
  },

  /** Notify when going offline */
  offline() {
    return toast.warning("You are offline", {
      description: "Your changes will be synced when you are back online.",
      duration: Infinity,
      id: "offline-toast",
    });
  },

  /** Notify when coming back online */
  online() {
    toast.dismiss("offline-toast");
    return toast.success("You are back online", {
      description: "All changes have been synced.",
      duration: 3000,
    });
  },

  /** Notify about a session expiry */
  sessionExpired() {
    return toast.error("Session expired", {
      description: "Please log in again to continue.",
      duration: Infinity,
    });
  },
};
