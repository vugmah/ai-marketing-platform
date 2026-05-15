import { useState, useCallback, useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
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
  const sidebarWidth = collapsed && !mobileOpen ? 72 : 260;

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
          "min-h-[100dvh] pt-16 transition-all duration-300",
          "bg-[#F1F5F9]"
        )}
        style={{
          marginLeft: sidebarWidth,
        }}
      >
        <div className="p-6 lg:p-8 max-w-[1440px] mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
