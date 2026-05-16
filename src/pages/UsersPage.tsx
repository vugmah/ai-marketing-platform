import { useState, useEffect, useMemo } from "react";
import {
  Users,
  Shield,
  Store,
  Megaphone,
  HeadphonesIcon,
  BarChart3,
  Crown,
  Search,
  MoreHorizontal,
  UserCheck,
  KeyRound,
  Lock,
  UserX,
  Trash2,
  Mail,
  Clock,
  Check,
  X,
  ChevronDown,
  UserPlus,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

// ─── Inline Mock Data ────────────────────────────────────

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  branch: string;
  status: "active" | "inactive";
  lastActive: string;
  avatar: string | null;
}

const allUsers: User[] = [
  { id: "u1", name: "Vüqar Məmmədov", email: "vuqar@foodflow.az", role: "super_admin", branch: "Tüm Şubeler", status: "active", lastActive: "2 dk önce", avatar: null },
  { id: "u2", name: "Elçin Əliyev", email: "elchin@foodflow.az", role: "company_admin", branch: "Tüm Şubeler", status: "active", lastActive: "15 dk önce", avatar: null },
  { id: "u3", name: "Leyla Həsənova", email: "leyla@foodflow.az", role: "branch_manager", branch: "Nizami Şubesi", status: "active", lastActive: "1 saat önce", avatar: null },
  { id: "u4", name: "Nigar İsmayılova", email: "nigar@foodflow.az", role: "branch_manager", branch: "28 May Şubesi", status: "active", lastActive: "30 dk önce", avatar: null },
  { id: "u5", name: "Rəşad Məmmədov", email: "reshad@foodflow.az", role: "marketing_manager", branch: "Tüm Şubeler", status: "active", lastActive: "5 dk önce", avatar: null },
  { id: "u6", name: "Aysel Quliyeva", email: "aysel@foodflow.az", role: "support_agent", branch: "Gəncə Lounge", status: "active", lastActive: "3 saat önce", avatar: null },
  { id: "u7", name: "Tural Əhmədov", email: "tural@foodflow.az", role: "analyst", branch: "Mingəçevir Park", status: "inactive", lastActive: "2 gün önce", avatar: null },
  { id: "u8", name: "Zərnəgər Rəhimova", email: "zarnegar@foodflow.az", role: "analyst", branch: "Şəki Bahçe", status: "active", lastActive: "45 dk önce", avatar: null },
];

// ─── Role Config ─────────────────────────────────────────

const roleConfig: Record<string, { label: string; color: string; bg: string; icon: React.ElementType }> = {
  super_admin: { label: "Süper Admin", color: "text-[#DC2626]", bg: "bg-[#FEE2E2]", icon: Crown },
  company_admin: { label: "Şirket Admin", color: "text-[#7C3AED]", bg: "bg-[#EDE9FE]", icon: Shield },
  branch_manager: { label: "Şube Müdürü", color: "text-[#059669]", bg: "bg-[#D1FAE5]", icon: Store },
  marketing_manager: { label: "Pazarlama Müdürü", color: "text-[#D97706]", bg: "bg-[#FEF3C7]", icon: Megaphone },
  support_agent: { label: "Destek Temsilcisi", color: "text-[#2563EB]", bg: "bg-[#DBEAFE]", icon: HeadphonesIcon },
  analyst: { label: "Analist", color: "text-[#64748B]", bg: "bg-[#F1F5F9]", icon: BarChart3 },
};

const roleMatrix = [
  { permission: "Dashboard Görüntüleme", super_admin: true, company_admin: true, branch_manager: true, marketing_manager: true, support_agent: true, analyst: true },
  { permission: "Şube Yönetimi", super_admin: true, company_admin: true, branch_manager: false, marketing_manager: false, support_agent: false, analyst: false },
  { permission: "Kullanıcı Yönetimi", super_admin: true, company_admin: true, branch_manager: false, marketing_manager: false, support_agent: false, analyst: false },
  { permission: "Reklam Yönetimi", super_admin: true, company_admin: true, branch_manager: false, marketing_manager: true, support_agent: false, analyst: false },
  { permission: "Sosyal Medya", super_admin: true, company_admin: true, branch_manager: false, marketing_manager: true, support_agent: true, analyst: true },
  { permission: "AI Raporları", super_admin: true, company_admin: true, branch_manager: true, marketing_manager: true, support_agent: false, analyst: true },
  { permission: "Gelen Kutusu", super_admin: true, company_admin: true, branch_manager: true, marketing_manager: false, support_agent: true, analyst: false },
  { permission: "Ayarlar", super_admin: true, company_admin: true, branch_manager: false, marketing_manager: false, support_agent: false, analyst: false },
  { permission: "Finansal Raporlar", super_admin: true, company_admin: true, branch_manager: true, marketing_manager: true, support_agent: false, analyst: true },
  { permission: "API Erişimi", super_admin: true, company_admin: false, branch_manager: false, marketing_manager: false, support_agent: false, analyst: false },
];

const roleKeys = ["super_admin", "company_admin", "branch_manager", "marketing_manager", "support_agent", "analyst"] as const;

// ─── KPI Card ────────────────────────────────────────────

function UserKPICard({
  title,
  value,
  icon: Icon,
  accent,
  delay,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  accent: string;
  delay: number;
}) {
  return (
    <Card
      className="opacity-0 animate-fade-in transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "forwards" }}
    >
      <CardContent className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-full" style={{ backgroundColor: `${accent}1A` }}>
            <Icon className="w-5 h-5" style={{ color: accent }} />
          </div>
          <span className="text-[13px] font-medium text-[#94A3B8] uppercase tracking-wide">{title}</span>
        </div>
        <p className="text-[32px] font-bold text-[#0F172A] leading-tight tracking-tight">{value}</p>
      </CardContent>
    </Card>
  );
}

// ─── Main Component ──────────────────────────────────────

export default function UsersPage() {
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("Tümü");
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("branch_manager");
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);

  // Load users from API
  useEffect(() => {
    let mounted = true;
    async function loadUsers() {
      try {
        setUsersLoading(true);
        const res = await api.users.list();
        if (mounted && res.success && res.data) {
          const mapped = (res.data as any[]).map((u: any) => ({
            id: String(u.id),
            name: u.name || u.full_name || "Bilinmeyen",
            email: u.email || "",
            role: u.role || "analyst",
            branch: u.branch || "Tüm Şubeler",
            status: (u.status || "active") as "active" | "inactive",
            lastActive: u.last_active || u.lastActive || "Bilinmiyor",
            avatar: u.avatar || null,
          }));
          setAllUsers(mapped);
        }
      } catch (err) {
        if (mounted) console.error("Kullanıcılar yüklenemedi:", err);
      } finally {
        if (mounted) setUsersLoading(false);
      }
    }
    loadUsers();
    return () => { mounted = false; };
  }, []);

  const filteredUsers = useMemo(() => {
    if (usersLoading) return [];
    return allUsers.filter((u) => {
      const matchSearch = !search || u.name.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase());
      const matchRole = roleFilter === "Tümü" || roleConfig[u.role]?.label === roleFilter;
      return matchSearch && matchRole;
    });
  }, [search, roleFilter, allUsers, usersLoading]);

  const roleCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    allUsers.forEach((u) => {
      counts[u.role] = (counts[u.role] || 0) + 1;
    });
    return counts;
  }, []);

  const getInitials = (name: string) => name.split(" ").map((n) => n[0]).join("").slice(0, 2);

  return (
    <div className="space-y-6">
      {/* ═══ Page Header ════════════════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Kullanıcı Yönetimi</h1>
          <p className="text-sm text-[#475569] mt-0.5">Ekip üyelerinizi yönetin ve rollerini düzenleyin</p>
        </div>
        <Button className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-9 gap-2" onClick={() => setShowInvite(!showInvite)}>
          <UserPlus className="w-4 h-4" />
          Kullanıcı Davet Et
        </Button>
      </div>

      {/* ═══ Invite Card ════════════════════════════════ */}
      {showInvite && (
        <Card className="opacity-0 animate-fade-in-up border-l-[3px] border-l-[#2563EB]" style={{ animationFillMode: "forwards", animationDuration: "300ms" }}>
          <CardContent className="p-5">
            <div className="flex flex-col sm:flex-row gap-3 items-end">
              <div className="flex-1 w-full">
                <label className="text-xs font-medium text-[#475569] mb-1.5 block">E-posta Adresi</label>
                <Input
                  placeholder="ornek@foodflow.az"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="h-9 border-[#E2E8F0]"
                />
              </div>
              <div className="w-full sm:w-48">
                <label className="text-xs font-medium text-[#475569] mb-1.5 block">Rol</label>
                <div className="relative">
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="w-full h-9 px-3 pr-8 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] appearance-none cursor-pointer"
                  >
                    {Object.entries(roleConfig).map(([key, cfg]) => (
                      <option key={key} value={key}>{cfg.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8] pointer-events-none" />
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" className="h-9" onClick={() => setShowInvite(false)}>
                  <X className="w-4 h-4 mr-1" /> İptal
                </Button>
                <Button className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-9" onClick={() => { setInviteEmail(""); setShowInvite(false); }}>
                  <Mail className="w-4 h-4 mr-1" /> Davet Gönder
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ═══ KPI Cards ══════════════════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        <UserKPICard title="Toplam Kullanıcı" value={String(allUsers.length)} icon={Users} accent="#2563EB" delay={0} />
        <UserKPICard title="Admin" value={String((roleCounts["super_admin"] || 0) + (roleCounts["company_admin"] || 0))} icon={Shield} accent="#7C3AED" delay={80} />
        <UserKPICard title="Şube Müdürü" value={String(roleCounts["branch_manager"] || 0)} icon={Store} accent="#059669" delay={160} />
        <UserKPICard title="Pazarlama Müdürü" value={String(roleCounts["marketing_manager"] || 0)} icon={Megaphone} accent="#D97706" delay={240} />
      </div>

      {/* ═══ Filters ════════════════════════════════════ */}
      <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "200ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
              <Input
                placeholder="İsim veya e-posta ara..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-9 border-[#E2E8F0] text-sm"
              />
            </div>
            <div className="relative">
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="h-9 px-3 pr-8 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors appearance-none cursor-pointer min-w-[160px]"
              >
                <option value="Tümü">Tüm Roller</option>
                {Object.values(roleConfig).map((cfg) => (
                  <option key={cfg.label} value={cfg.label}>{cfg.label}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8] pointer-events-none" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ═══ Users Table ════════════════════════════════ */}
      <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "300ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base font-semibold text-[#0F172A]">Kullanıcı Listesi</CardTitle>
            <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">{filteredUsers.length} kullanıcı bulundu</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Kullanıcı</th>
                  <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Rol</th>
                  <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Şube</th>
                  <th className="text-center text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Durum</th>
                  <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Son Aktif</th>
                  <th className="text-right text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Eylemler</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((user, idx) => {
                  const rc = roleConfig[user.role];
                  const RoleIcon = rc?.icon || UserCheck;
                  return (
                    <tr
                      key={user.id}
                      className={cn(
                        "border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors opacity-0 animate-fade-in",
                        idx % 2 === 0 ? "bg-white" : "bg-[#FAFBFC]"
                      )}
                      style={{ animationDelay: `${350 + idx * 50}ms`, animationFillMode: "forwards", animationDuration: "300ms" }}
                    >
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex items-center justify-center w-9 h-9 rounded-full bg-[#DBEAFE] text-[#2563EB] text-xs font-bold shrink-0">
                            {getInitials(user.name)}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-[#0F172A]">{user.name}</p>
                            <p className="text-[11px] text-[#94A3B8]">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <Badge className={cn("text-[11px] h-5 px-2 font-medium gap-1", rc?.bg, rc?.color)}>
                          <RoleIcon className="w-3 h-3" />
                          {rc?.label}
                        </Badge>
                      </td>
                      <td className="px-3 py-3">
                        <span className="text-sm text-[#475569]">{user.branch}</span>
                      </td>
                      <td className="px-3 py-3 text-center">
                        <Badge
                          className={cn(
                            "text-[11px] h-5 px-2 font-medium",
                            user.status === "active"
                              ? "bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5]"
                              : "bg-[#F1F5F9] text-[#94A3B8] hover:bg-[#F1F5F9]"
                          )}
                        >
                          <span className={cn("w-1.5 h-1.5 rounded-full mr-1.5", user.status === "active" ? "bg-[#059669]" : "bg-[#94A3B8]")} />
                          {user.status === "active" ? "Aktif" : "Pasif"}
                        </Badge>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-[#94A3B8]" />
                          <span className="text-sm text-[#475569]">{user.lastActive}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right relative">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => setOpenDropdownId(openDropdownId === user.id ? null : user.id)}
                        >
                          <MoreHorizontal className="w-4 h-4 text-[#94A3B8]" />
                        </Button>
                        {openDropdownId === user.id && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={() => setOpenDropdownId(null)} />
                            <div className="absolute right-3 top-10 w-48 bg-white rounded-lg border border-[#E2E8F0] shadow-lg z-50 overflow-hidden">
                              <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors" onClick={() => setOpenDropdownId(null)}>
                                <UserCheck className="w-3.5 h-3.5 text-[#475569]" /> Profil Gör
                              </button>
                              <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors" onClick={() => setOpenDropdownId(null)}>
                                <Shield className="w-3.5 h-3.5 text-[#475569]" /> Rol Değiştir
                              </button>
                              <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors" onClick={() => setOpenDropdownId(null)}>
                                <KeyRound className="w-3.5 h-3.5 text-[#475569]" /> Şifre Sıfırla
                              </button>
                              <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors" onClick={() => setOpenDropdownId(null)}>
                                <Lock className="w-3.5 h-3.5 text-[#475569]" /> Pasifleştir
                              </button>
                              <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#DC2626] hover:bg-[#FEE2E2] transition-colors" onClick={() => setOpenDropdownId(null)}>
                                <Trash2 className="w-3.5 h-3.5" /> Sil
                              </button>
                            </div>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* ═══ Role Permission Matrix ═════════════════════ */}
      <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "400ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
        <CardHeader>
          <CardTitle className="text-base font-semibold text-[#0F172A]">Rol İzin Matrisi</CardTitle>
          <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Her rolün platform özelliklerine erişimi</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3 min-w-[200px]">İzin</th>
                  {roleKeys.map((rk) => {
                    const rc = roleConfig[rk];
                    const Icon = rc?.icon || UserCheck;
                    return (
                      <th key={rk} className="text-center text-[11px] font-semibold uppercase tracking-wider px-2 py-3 min-w-[100px]">
                        <div className={cn("flex flex-col items-center gap-1", rc?.color)}>
                          <Icon className="w-4 h-4" />
                          <span>{rc?.label}</span>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {roleMatrix.map((row, rIdx) => (
                  <tr key={rIdx} className={cn("border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors", rIdx % 2 === 0 ? "bg-white" : "bg-[#FAFBFC]")}>
                    <td className="px-3 py-2.5 text-sm font-medium text-[#0F172A]">{row.permission}</td>
                    {roleKeys.map((rk) => (
                      <td key={rk} className="px-2 py-2.5 text-center">
                        {row[rk] ? (
                          <div className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#D1FAE5]">
                            <Check className="w-3.5 h-3.5 text-[#059669]" />
                          </div>
                        ) : (
                          <div className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#F1F5F9]">
                            <X className="w-3.5 h-3.5 text-[#CBD5E1]" />
                          </div>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* ═══ CSS Animations ═════════════════════════════ */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fadeIn 0.5s ease-out;
        }
        .animate-fade-in-up {
          animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>
    </div>
  );
}
