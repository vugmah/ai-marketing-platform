import { useState, useCallback, useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Building2,
  Share2,
  Megaphone,
  Palette,
  Sparkles,
  BarChart3,
  Settings,
} from "lucide-react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import { cn } from "@/lib/utils";

// ─── Page Metadata ───────────────────────────────────────

const pageMeta: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard", subtitle: "İşletmenizin performansına genel bakış" },
  "/": { title: "Dashboard", subtitle: "İşletmenizin performansına genel bakış" },
  "/branches": { title: "Şube Yönetimi", subtitle: "Şubelerinizi yönetin ve karşılaştırın" },
  "/social-media": { title: "Sosyal Medya", subtitle: "Sosyal medya hesaplarınızı yönetin" },
  "/ads": { title: "Reklam Yönetimi", subtitle: "Kampanyalarınızı izleyin ve optimize edin" },
  "/creative-studio": { title: "Yaratıcı Stüdyo", subtitle: "İçerik üretin ve planlayın" },
  "/chat-inbox": { title: "Gelen Kutusu", subtitle: "Müşteri mesajlarını yönetin" },
  "/ai-reports": { title: "AI Raporları", subtitle: "AI destekli analiz ve öneriler" },
  "/analytics": { title: "Analitik Raporlar", subtitle: "Detaylı performans raporları" },
  "/users": { title: "Kullanıcı Yönetimi", subtitle: "Ekip üyelerini ve rolleri yönetin" },
  "/settings": { title: "Ayarlar", subtitle: "Platform ayarlarını yapılandırın" },
};

// ─── Component ───────────────────────────────────────────

export default function Layout() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    return saved === "true";
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile viewport
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // Persist collapsed state
  useEffect(() => {
    localStorage.setItem("sidebar-collapsed", String(collapsed));
  }, [collapsed]);

  const handleToggle = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const handleMobileClose = useCallback(() => {
    setMobileOpen(false);
  }, []);

  const handleMobileToggle = useCallback(() => {
    setMobileOpen((prev) => !prev);
  }, []);

  const currentPath = location.pathname;
  const meta = pageMeta[currentPath] || { title: "Dashboard", subtitle: "" };

  // Determine sidebar width for CSS variable
  // Mobile (< md): sidebar hidden, content takes full width
  // Desktop: sidebar takes 72px (collapsed) or 260px (expanded)
  const sidebarWidth = isMobile ? 0 : collapsed && !mobileOpen ? 72 : 260;

  return (
    <div className="min-h-[100dvh]">
      {/* ── Sidebar ─────────────────────────────── */}
      <Sidebar
        collapsed={collapsed}
        onToggle={handleToggle}
        mobileOpen={mobileOpen}
        onMobileClose={handleMobileClose}
      />

      {/* ── Header ──────────────────────────────── */}
      <div
        className={cn(isMobile && "md:ml-0")}
        style={
          {
            "--sidebar-offset": `${sidebarWidth}px`,
          } as React.CSSProperties
        }
      >
        <Header
          pageTitle={meta.title}
          pageSubtitle={meta.subtitle}
          onMenuToggle={handleMobileToggle}
        />
      </div>

      {/* ── Main Content ────────────────────────── */}
      <main
        className={cn(
          "min-h-[100dvh] pt-16 pb-20 md:pb-0 transition-all duration-300",
          "bg-[#F1F5F9]",
          // Mobile: no margin (sidebar hidden), Desktop: sidebar offset
          isMobile ? "ml-0" : undefined
        )}
        style={{
          marginLeft: isMobile ? 0 : sidebarWidth,
        }}
      >
        {/* Mobile: full-width padding, larger screens: comfortable padding */}
        <div className="p-3 sm:p-4 md:p-6 lg:p-8 max-w-[1440px] mx-auto">
          <Outlet />
        </div>
      </main>

      {/* ── Mobile Bottom Navigation ────────────── */}
      <MobileBottomNav />
    </div>
  );
}

// ═── Mobile Bottom Navigation ────────────────────────────

const mobileNavItems = [
  { label: "Dashboard", icon: LayoutDashboard, route: "/dashboard" },
  { label: "Şubeler", icon: Building2, route: "/branches" },
  { label: "Sosyal", icon: Share2, route: "/social-media" },
  { label: "Reklam", icon: Megaphone, route: "/ads" },
  { label: "AI", icon: Sparkles, route: "/ai-reports" },
  { label: "Ayarlar", icon: Settings, route: "/settings" },
];

function MobileBottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-[#E2E8F0] md:hidden">
      <div className="flex items-center justify-around h-16 pb-safe">
        {mobileNavItems.map((item) => {
          const isActive =
            location.pathname === item.route ||
            location.pathname === `${item.route}/`;
          const Icon = item.icon;
          return (
            <button
              key={item.route}
              onClick={() => navigate(item.route)}
              className={cn(
                "flex flex-col items-center justify-center gap-0.5 w-full h-full transition-colors",
                isActive ? "text-[#2563EB]" : "text-[#94A3B8]"
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{item.label}</span>
              {isActive && (
                <span className="absolute bottom-0 w-10 h-0.5 bg-[#2563EB] rounded-full" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
