import { createRoot } from 'react-dom/client'
import { StrictMode, useEffect } from 'react'
import { toast } from 'sonner'
import './index.css'
import App from './App.tsx'

/**
 * NetworkStatusManager - Monitors online/offline state and shows
 * toast notifications when connectivity changes.
 */
function NetworkStatusManager() {
  useEffect(() => {
    let offlineToastId: string | number | null = null;

    const handleOnline = () => {
      if (offlineToastId !== null) {
        toast.dismiss(offlineToastId);
        offlineToastId = null;
      }
      toast.success("İnternet bağlantısı geri geldi", {
        description: "Veriler otomatik olarak senkronize ediliyor...",
        duration: 3000,
      });
      window.dispatchEvent(new CustomEvent("network-online"));
    };

    const handleOffline = () => {
      offlineToastId = toast.error("İnternet bağlantısı kesildi", {
        description: "Çevrimdışı moddasınız. Bazı özellikler sınırlı olabilir.",
        duration: Infinity,
      });
      window.dispatchEvent(new CustomEvent("network-offline"));
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    if (!navigator.onLine) {
      handleOffline();
    }

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return null;
}

/**
 * Global shimmer animation styles for skeleton loaders.
 */
function SkeletonStyles() {
  useEffect(() => {
    if (document.getElementById("skeleton-animations")) return;
    const style = document.createElement("style");
    style.id = "skeleton-animations";
    style.textContent = `
      @keyframes shimmer {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
      }
      .animate-shimmer {
        animation: shimmer 1.5s ease-in-out infinite;
      }
      @keyframes fadeInSkeleton {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }
      .animate-fade-in-skeleton {
        animation: fadeInSkeleton 0.3s ease-out;
      }
    `;
    document.head.appendChild(style);
    return () => {
      const existing = document.getElementById("skeleton-animations");
      if (existing) document.head.removeChild(existing);
    };
  }, []);

  return null;
}

// ═── Global CSS Animations ─────────────────────────────────
const globalAnimations = `
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(16px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes slideInRight {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .animate-fade-in {
    animation: fadeIn 0.5s ease-out;
  }
  .animate-fade-in-up {
    animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .animate-slide-in-right {
    animation: slideInRight 0.3s ease-out;
  }
`;

if (typeof document !== "undefined" && !document.getElementById("global-animations")) {
  const styleEl = document.createElement("style");
  styleEl.id = "global-animations";
  styleEl.textContent = globalAnimations;
  document.head.appendChild(styleEl);
}

// ═── Render ────────────────────────────────────────────────

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SkeletonStyles />
    <NetworkStatusManager />
    <App />
  </StrictMode>,
)
