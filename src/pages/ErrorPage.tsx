/**
 * ErrorPage - Reusable error pages for 403, 404, 500 errors
 * With consistent branding and navigation options.
 */
import {
  Lock,
  FileQuestion,
  ServerCrash,
  Home,
  ArrowLeft,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";

// ─── Types ───────────────────────────────────────────────

export type ErrorPageCode = 403 | 404 | 500;

interface ErrorPageConfig {
  icon: LucideIcon;
  iconBg: string;
  iconColor: string;
  title: string;
  subtitle: string;
  description: string;
}

// ─── Page Configurations ─────────────────────────────────

const errorConfigs: Record<ErrorPageCode, ErrorPageConfig> = {
  403: {
    icon: Lock,
    iconBg: "#FEE2E2",
    iconColor: "#DC2626",
    title: "Erişim Reddedildi",
    subtitle: "403 - Forbidden",
    description:
      "Bu sayfaya erişim izniniz bulunmamaktadır. Eğer bir hata olduğunu düşünüyorsanız, yöneticiniz ile iletişime geçin.",
  },
  404: {
    icon: FileQuestion,
    iconBg: "#FEF3C7",
    iconColor: "#D97706",
    title: "Sayfa Bulunamadı",
    subtitle: "404 - Not Found",
    description:
      "Aradığınız sayfa mevcut değil veya taşınmış olabilir. Lütfen URL'yi kontrol edin veya ana sayfaya dönün.",
  },
  500: {
    icon: ServerCrash,
    iconBg: "#FEE2E2",
    iconColor: "#DC2626",
    title: "Sunucu Hatası",
    subtitle: "500 - Internal Server Error",
    description:
      "Sunucuda bir hata oluştu. Lütfen daha sonra tekrar deneyin. Sorun devam ederse destek ekibi ile iletişime geçin.",
  },
};

// ─── Component ───────────────────────────────────────────

interface ErrorPageProps {
  code: ErrorPageCode;
  onBack?: () => void;
  onHome?: () => void;
  onRetry?: () => void;
}

export default function ErrorPage({
  code,
  onBack,
  onHome,
  onRetry,
}: ErrorPageProps) {
  const config = errorConfigs[code];
  const Icon = config.icon;

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      window.history.back();
    }
  };

  const handleHome = () => {
    if (onHome) {
      onHome();
    } else {
      window.location.hash = "/";
    }
  };

  const handleRetry = () => {
    if (onRetry) {
      onRetry();
    } else {
      window.location.reload();
    }
  };

  return (
    <div className="min-h-[calc(100vh-64px)] bg-[#F1F5F9] flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center">
        {/* Icon */}
        <div
          className="inline-flex items-center justify-center w-20 h-20 rounded-2xl mb-6"
          style={{ backgroundColor: config.iconBg }}
        >
          <Icon className="w-10 h-10" style={{ color: config.iconColor }} />
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-[#0F172A] mb-1">
          {config.title}
        </h1>
        <p className="text-sm font-medium text-[#94A3B8] mb-4">
          {config.subtitle}
        </p>

        {/* Description */}
        <p className="text-sm text-[#475569] leading-relaxed mb-8">
          {config.description}
        </p>

        {/* Error code visual */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="h-px flex-1 max-w-[60px] bg-[#E2E8F0]" />
          <span
            className="text-5xl font-extrabold tracking-tight"
            style={{ color: config.iconColor, opacity: 0.15 }}
          >
            {code}
          </span>
          <div className="h-px flex-1 max-w-[60px] bg-[#E2E8F0]" />
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          {code === 500 ? (
            <Button
              onClick={handleRetry}
              className="h-10 bg-[#2563EB] hover:bg-[#1D4ED8] text-white px-6"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Tekrar Dene
            </Button>
          ) : (
            <Button
              onClick={handleBack}
              variant="outline"
              className="h-10 border-[#E2E8F0] hover:bg-[#F8FAFC]"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Geri Dön
            </Button>
          )}
          <Button
            onClick={handleHome}
            className="h-10 bg-[#2563EB] hover:bg-[#1D4ED8] text-white px-6"
          >
            <Home className="w-4 h-4 mr-2" />
            Ana Sayfa
          </Button>
        </div>

        {/* Help text */}
        <p className="text-xs text-[#94A3B8] mt-8">
          Yardım mı gerekiyor?{" "}
          <a
            href="mailto:support@nexusai.com"
            className="text-[#2563EB] hover:underline"
          >
            Destek ekibine ulaşın
          </a>
        </p>
      </div>
    </div>
  );
}

// ─── Convenience Exports ─────────────────────────────────

export function ForbiddenPage(props: Omit<ErrorPageProps, "code">) {
  return <ErrorPage code={403} {...props} />;
}

export function NotFoundPage(props: Omit<ErrorPageProps, "code">) {
  return <ErrorPage code={404} {...props} />;
}

export function ServerErrorPage(props: Omit<ErrorPageProps, "code">) {
  return <ErrorPage code={500} {...props} />;
}
