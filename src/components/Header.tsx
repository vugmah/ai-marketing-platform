import { useState, useRef, useEffect } from "react";
import {
  Search,
  Bell,
  ChevronDown,
  X,
  Check,
  AlertTriangle,
  MessageSquare,
  Info,
  Sparkles,
  Building2,
  Settings,
  LogOut,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mockNotificationCount, mockAlerts } from "@/lib/mockApi";
import type { AlertData } from "@/lib/mockApi";

// ─── Types ───────────────────────────────────────────────

interface HeaderProps {
  pageTitle: string;
  pageSubtitle?: string;
  onMenuToggle: () => void;
}

// ─── Branch Data ─────────────────────────────────────────

const branches = [
  { id: "all", name: "Tüm Şubeler", icon: Building2 },
  { id: "nizami", name: "Nizami Şubesi", icon: Building2 },
  { id: "gencik", name: "Gənclik Şubesi", icon: Building2 },
  { id: "28may", name: "28 May Şubesi", icon: Building2 },
];

// ─── Alert Icon Map ──────────────────────────────────────

const alertIconMap = {
  critical: AlertTriangle,
  warning: MessageSquare,
  info: Info,
  ai: Sparkles,
};

const alertColorMap = {
  critical: "text-[#DC2626]",
  warning: "text-[#D97706]",
  info: "text-[#2563EB]",
  ai: "text-[#7C3AED]",
};

const alertBorderMap = {
  critical: "border-l-[#DC2626]",
  warning: "border-l-[#D97706]",
  info: "border-l-[#2563EB]",
  ai: "border-l-[#7C3AED]",
};

// ─── Component ───────────────────────────────────────────

export default function Header({ pageTitle, pageSubtitle, onMenuToggle }: HeaderProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const [branchOpen, setBranchOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [selectedBranch, setSelectedBranch] = useState(branches[0]);

  const searchRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const branchRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setSearchOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
        setNotifOpen(false);
      }
      if (branchRef.current && !branchRef.current.contains(event.target as Node)) {
        setBranchOpen(false);
      }
      if (userRef.current && !userRef.current.contains(event.target as Node)) {
        setUserOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const userName = "Vüqar Məmmədov";
  const initials = userName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2);

  return (
    <header
      className={cn(
        "fixed top-0 right-0 z-30 h-16 bg-white border-b border-[#E2E8F0]",
        "flex items-center justify-between px-6 transition-all duration-300"
      )}
      style={{
        left: "var(--sidebar-offset, 260px)",
      }}
    >
      {/* ── Left: Title ───────────────────────────── */}
      <div className="flex items-center gap-3">
        {/* Mobile menu button */}
        <button
          onClick={onMenuToggle}
          className="lg:hidden flex items-center justify-center w-9 h-9 rounded-lg hover:bg-[#F1F5F9] transition-colors"
        >
          <svg className="w-5 h-5 text-[#475569]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div>
          <h1 className="text-xl font-bold text-[#0F172A]">{pageTitle}</h1>
          {pageSubtitle && (
            <p className="text-xs text-[#94A3B8] hidden sm:block">{pageSubtitle}</p>
          )}
        </div>
      </div>

      {/* ── Right: Actions ────────────────────────── */}
      <div className="flex items-center gap-2">
        {/* Search */}
        <div ref={searchRef} className="relative">
          {searchOpen ? (
            <div className="flex items-center gap-2 bg-[#F1F5F9] rounded-lg px-3 h-10 w-[280px]">
              <Search className="w-4 h-4 text-[#94A3B8] shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ara..."
                className="bg-transparent border-none outline-none text-sm text-[#0F172A] placeholder-[#94A3B8] flex-1"
                autoFocus
              />
              <button onClick={() => { setSearchOpen(false); setSearchQuery(""); }}>
                <X className="w-4 h-4 text-[#94A3B8] hover:text-[#0F172A]" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setSearchOpen(true)}
              className="flex items-center justify-center w-9 h-9 rounded-lg hover:bg-[#F1F5F9] transition-colors"
            >
              <Search className="w-[18px] h-[18px] text-[#475569]" />
            </button>
          )}
        </div>

        {/* Notification Bell */}
        <div ref={notifRef} className="relative">
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            className="flex items-center justify-center w-9 h-9 rounded-lg hover:bg-[#F1F5F9] transition-colors relative"
          >
            <Bell className="w-[18px] h-[18px] text-[#475569]" />
            {mockNotificationCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-[#DC2626] rounded-full border-2 border-white">
                {mockNotificationCount}
              </span>
            )}
          </button>

          {/* Notification dropdown */}
          {notifOpen && (
            <div className="absolute right-0 top-12 w-[360px] bg-white rounded-xl border border-[#E2E8F0] shadow-lg z-50 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-[#E2E8F0]">
                <h3 className="text-sm font-semibold text-[#0F172A]">Bildirimler</h3>
                <button className="text-xs text-[#2563EB] hover:underline">Tümünü Okundu İşaretle</button>
              </div>
              <div className="max-h-[320px] overflow-y-auto">
                {mockAlerts.map((alert: AlertData) => {
                  const Icon = alertIconMap[alert.type];
                  return (
                    <div
                      key={alert.id}
                      className={cn(
                        "flex gap-3 px-4 py-3 border-l-[3px] hover:bg-[#F8FAFC] transition-colors cursor-pointer",
                        alertBorderMap[alert.type]
                      )}
                    >
                      <Icon className={cn("w-5 h-5 shrink-0 mt-0.5", alertColorMap[alert.type])} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-[#0F172A]">{alert.title}</p>
                        <p className="text-xs text-[#475569] mt-0.5 line-clamp-2">{alert.description}</p>
                        <div className="flex items-center justify-between mt-1.5">
                          <span className="text-[11px] text-[#94A3B8]">{alert.meta}</span>
                          <span className="text-[11px] text-[#94A3B8]">{alert.timestamp}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="px-4 py-2.5 border-t border-[#E2E8F0]">
                <button className="text-xs text-[#2563EB] font-medium hover:underline">
                  Tüm Bildirimleri Gör →
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Branch Selector */}
        <div ref={branchRef} className="relative hidden md:block">
          <button
            onClick={() => setBranchOpen(!branchOpen)}
            className="flex items-center gap-2 px-3 h-9 rounded-lg border border-[#E2E8F0] hover:bg-[#F8FAFC] transition-colors"
          >
            <Building2 className="w-4 h-4 text-[#475569]" />
            <span className="text-sm text-[#0F172A] max-w-[140px] truncate">
              {selectedBranch.name}
            </span>
            <ChevronDown
              className={cn(
                "w-4 h-4 text-[#94A3B8] transition-transform",
                branchOpen && "rotate-180"
              )}
            />
          </button>

          {branchOpen && (
            <div className="absolute right-0 top-12 w-[200px] bg-white rounded-xl border border-[#E2E8F0] shadow-lg z-50 overflow-hidden">
              {branches.map((branch) => (
                <button
                  key={branch.id}
                  onClick={() => { setSelectedBranch(branch); setBranchOpen(false); }}
                  className={cn(
                    "flex items-center gap-2 w-full px-4 py-2.5 text-sm hover:bg-[#F8FAFC] transition-colors",
                    selectedBranch.id === branch.id && "bg-[#F1F5F9] text-[#2563EB] font-medium"
                  )}
                >
                  <branch.icon className="w-4 h-4" />
                  {branch.name}
                  {selectedBranch.id === branch.id && (
                    <Check className="w-4 h-4 ml-auto" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* User Avatar */}
        <div ref={userRef} className="relative">
          <button
            onClick={() => setUserOpen(!userOpen)}
            className="flex items-center gap-2 hover:bg-[#F1F5F9] rounded-lg p-1 pr-2 transition-colors"
          >
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#7C3AED] text-white text-xs font-semibold">
              {initials}
            </div>
            <ChevronDown
              className={cn(
                "w-4 h-4 text-[#94A3B8] hidden sm:block transition-transform",
                userOpen && "rotate-180"
              )}
            />
          </button>

          {userOpen && (
            <div className="absolute right-0 top-12 w-[220px] bg-white rounded-xl border border-[#E2E8F0] shadow-lg z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-[#E2E8F0]">
                <p className="text-sm font-semibold text-[#0F172A]">{userName}</p>
                <p className="text-xs text-[#94A3B8]">FoodFlow Azerbaijan</p>
              </div>
              <div className="py-1">
                <button className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-[#475569] hover:bg-[#F8FAFC] transition-colors">
                  <User className="w-4 h-4" />
                  Profil
                </button>
                <button className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-[#475569] hover:bg-[#F8FAFC] transition-colors">
                  <Settings className="w-4 h-4" />
                  Tercihler
                </button>
              </div>
              <div className="border-t border-[#E2E8F0] py-1">
                <button className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-[#DC2626] hover:bg-[#FEF2F2] transition-colors">
                  <LogOut className="w-4 h-4" />
                  Çıkış Yap
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
