/**
 * ErrorBoundary - Global React error boundary with recovery UI
 * Catches React rendering errors and displays a graceful fallback.
 */
import { Component, type ReactNode, type ErrorInfo } from "react";
import {
  RefreshCw,
  Home,
  Bug,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  showDetails: boolean;
}

// ─── Component ───────────────────────────────────────────

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      error,
      errorInfo: null,
      showDetails: false,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    this.props.onError?.(error, errorInfo);

    // Log to console in development
    if (import.meta.env.DEV) {
      console.error("[ErrorBoundary] Caught error:", error);
      console.error("[ErrorBoundary] Component stack:", errorInfo.componentStack);
    }
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    });
    this.props.onReset?.();
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.hash = "/";
    this.handleReset();
  };

  toggleDetails = () => {
    this.setState((prev) => ({ showDetails: !prev.showDetails }));
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback takes priority
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return <ErrorFallback {...this.state} onReset={this.handleReset} onReload={this.handleReload} onGoHome={this.handleGoHome} toggleDetails={this.toggleDetails} />;
    }

    return this.props.children;
  }
}

// ─── Error Fallback UI ───────────────────────────────────

interface ErrorFallbackProps {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  showDetails: boolean;
  onReset: () => void;
  onReload: () => void;
  onGoHome: () => void;
  toggleDetails: () => void;
}

function ErrorFallback({
  error,
  errorInfo,
  showDetails,
  onReset,
  onReload,
  onGoHome,
  toggleDetails,
}: ErrorFallbackProps) {
  return (
    <div className="min-h-screen bg-[#F1F5F9] flex items-center justify-center p-4">
      <div className="max-w-lg w-full bg-white rounded-2xl shadow-lg border border-[#E2E8F0] overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-8 pb-4 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#FEE2E2] mb-4">
            <Bug className="w-8 h-8 text-[#DC2626]" />
          </div>
          <h1 className="text-xl font-bold text-[#0F172A] mb-1">
            Bir Hata Oluştu
          </h1>
          <p className="text-sm text-[#94A3B8]">
            Uygulama beklenmedik bir hata ile karşılaştı.
          </p>
        </div>

        {/* Error message */}
        <div className="px-6 mb-4">
          <div className="bg-[#F8FAFC] rounded-lg p-4 border border-[#E2E8F0]">
            <p className="text-sm font-medium text-[#DC2626] mb-1">
              {error?.name || "Error"}
            </p>
            <p className="text-sm text-[#475569]">
              {error?.message || "An unknown error occurred."}
            </p>
          </div>
        </div>

        {/* Stack trace details */}
        {errorInfo?.componentStack && (
          <div className="px-6 mb-4">
            <button
              onClick={toggleDetails}
              className="flex items-center gap-1 text-xs text-[#94A3B8] hover:text-[#0F172A] transition-colors mb-2"
            >
              {showDetails ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
              Teknik Detaylar
            </button>
            {showDetails && (
              <pre className="text-[11px] text-[#64748B] bg-[#0F172A] p-3 rounded-lg overflow-x-auto max-h-[200px] overflow-y-auto">
                {errorInfo.componentStack}
              </pre>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="px-6 pb-6 flex flex-col sm:flex-row gap-3">
          <Button
            onClick={onReset}
            className="flex-1 h-10 bg-[#2563EB] hover:bg-[#1D4ED8] text-white"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Tekrar Dene
          </Button>
          <Button
            variant="outline"
            onClick={onReload}
            className="flex-1 h-10 border-[#E2E8F0]"
          >
            Sayfayı Yenile
          </Button>
          <Button
            variant="outline"
            onClick={onGoHome}
            className="flex-1 h-10 border-[#E2E8F0]"
          >
            <Home className="w-4 h-4 mr-2" />
            Ana Sayfa
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── WithErrorBoundary HOC ──────────────────────────────

export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  boundaryProps?: Omit<ErrorBoundaryProps, "children">
) {
  return function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary {...boundaryProps}>
        <Component {...props} />
      </ErrorBoundary>
    );
  };
}
