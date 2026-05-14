import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Building2,
  Share2,
  Megaphone,
  Palette,
  MessageSquare,
  BarChart3,
  Sparkles,
  Settings,
  Users,
  ChevronLeft,
  ChevronRight,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────

interface NavItem {
  label: string;
  icon: LucideIcon;
  route: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

// ─── Navigation Data ─────────────────────────────────────

const navSections: NavSection[] = [
  {
    title: "ANA MENÜ",
    items: [
      { label: "Dashboard", icon: LayoutDashboard, route: "/dashboard" },
      { label: "Şube Yönetimi", icon: Building2, route: "/branches" },
      { label: "Sosyal Medya", icon: Share2, route: "/social-media" },
      { label: "Reklam Yönetimi", icon: Megaphone, route: "/ads" },
    ],
  },
  {
    title: "İÇERİK & YAPAY ZEKA",
    items: [
      { label: "Yaratıcı Stüdyo", icon: Palette, route: "/creative-studio" },
      { label: "Gelen Kutusu", icon: MessageSquare, route: "/chat-inbox" },
      { label: "AI Raporları", icon: Sparkles, route: "/ai-reports" },
    ],
  },
  {
    title: "RAPORLAR & AYARLAR",
    items: [
      { label: "Analitik Raporlar", icon: BarChart3, route: "/analytics" },
      { label: "Kullanıcı Yönetimi", icon: Users, route: "/users" },
      { label: "Ayarlar", icon: Settings, route: "/settings" },
    ],
  },
];

// ─── Component ───────────────────────────────────────────

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

export default function Sidebar({
  collapsed,
  onToggle,
  mobileOpen,
  onMobileClose,
}: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();

  // Close mobile sidebar on route change
  useEffect(() => {
    onMobileClose();
  }, [location.pathname, onMobileClose]);

  const handleNav = useCallback(
    (route: string) => {
      navigate(route);
      onMobileClose();
    },
    [navigate, onMobileClose]
  );

  const isActive = useCallback(
    (route: string) => {
      return location.pathname === route || location.pathname === `${route}/`;
    },
    [location.pathname]
  );

  // Get user initials
  const userName = "Vüqar Məmmədov";
  const userRole = "Şirket Yöneticisi";
  const initials = userName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2);

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onMobileClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 h-full z-50 flex flex-col transition-all duration-300 ease-in-out",
          "bg-[#0F172A] text-white"
        )}
        style={{
          width: collapsed && !mobileOpen ? 72 : 260,
        }}
      >
        {/* ── Logo Area ─────────────────────────────── */}
        <div className="flex items-center h-16 px-4 border-b border-[#1E293B] shrink-0">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-[#7C3AED] shrink-0">
              <Zap className="w-5 h-5 text-white" />
            </div>
            {(!collapsed || mobileOpen) && (
              <span className="text-lg font-bold tracking-tight whitespace-nowrap">
                NexusAI
              </span>
            )}
          </div>
        </div>

        {/* ── Navigation ────────────────────────────── */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-6">
          {navSections.map((section) => (
            <div key={section.title}>
              {/* Section label */}
              {(!collapsed || mobileOpen) && (
                <p className="px-3 mb-2 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">
                  {section.title}
                </p>
              )}
              {(collapsed && !mobileOpen) && (
                <div className="mb-2 border-t border-[#1E293B]" />
              )}

              {/* Nav items */}
              <ul className="space-y-1">
                {section.items.map((item) => {
                  const active = isActive(item.route);
                  const Icon = item.icon;
                  return (
                    <li key={item.route}>
                      <button
                        onClick={() => handleNav(item.route)}
                        className={cn(
                          "flex items-center w-full rounded-lg transition-all duration-200 relative group",
                          "focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7C3AED] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0F172A]",
                          active
                            ? "bg-[#1E293B] text-white"
                            : "text-[#94A3B8] hover:bg-[#1E293B] hover:text-white",
                          collapsed && !mobileOpen
                            ? "justify-center h-10 w-10 mx-auto"
                            : "gap-3 px-3 h-10"
                        )}
                        aria-current={active ? "page" : undefined}
                        title={collapsed && !mobileOpen ? item.label : undefined}
                      >
                        {/* Active indicator bar */}
                        {active && (
                          <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full bg-[#2563EB]" />
                        )}

                        <Icon
                          className={cn(
                            "shrink-0",
                            active ? "text-white" : "text-[#94A3B8] group-hover:text-white"
                          )}
                          style={{ width: 20, height: 20 }}
                        />

                        {(!collapsed || mobileOpen) && (
                          <span className="text-sm font-medium whitespace-nowrap">
                            {item.label}
                          </span>
                        )}

                        {/* Tooltip for collapsed state */}
                        {collapsed && !mobileOpen && (
                          <div className="absolute left-full ml-2 px-2 py-1 bg-[#1E293B] text-white text-xs rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 border border-[#334155]">
                            {item.label}
                          </div>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* ── User Profile ──────────────────────────── */}
        <div className="shrink-0 border-t border-[#1E293B] p-3">
          <div
            className={cn(
              "flex items-center gap-3 rounded-lg p-2",
              collapsed && !mobileOpen ? "justify-center" : ""
            )}
          >
            {/* Avatar */}
            <div className="flex items-center justify-center w-9 h-9 rounded-full bg-[#7C3AED] text-white text-sm font-semibold shrink-0">
              {initials}
            </div>

            {(!collapsed || mobileOpen) && (
              <div className="overflow-hidden">
                <p className="text-sm font-medium text-white truncate">
                  {userName}
                </p>
                <p className="text-xs text-[#94A3B8] truncate">{userRole}</p>
              </div>
            )}
          </div>
        </div>

        {/* ── Collapse Toggle ───────────────────────── */}
        <button
          onClick={onToggle}
          className={cn(
            "absolute -right-3 top-20 flex items-center justify-center w-6 h-6 rounded-full",
            "bg-[#7C3AED] text-white shadow-lg hover:bg-[#6D28D9] transition-colors",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7C3AED]",
            "z-50 hidden lg:flex"
          )}
        >
          {collapsed ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <ChevronLeft className="w-3.5 h-3.5" />
          )}
        </button>
      </aside>
    </>
  );
}
