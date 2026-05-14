import { useState, useMemo } from "react";
import {
  Building2,
  Store,
  MapPin,
  Star,
  TrendingUp,
  TrendingDown,
  MoreHorizontal,
  Search,
  Filter,
  ChevronDown,
  Edit3,
  Eye,
  Power,
  Trash2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { mockBranches, mockBranchPerformance } from "@/lib/mockApi";

// ─── Inline Mock Data ────────────────────────────────────

interface Branch {
  id: string;
  name: string;
  city: string;
  type: string;
  revenue: number;
  orders: number;
  rating: number;
  status: "active" | "inactive" | "pending";
  manager: string;
  phone: string;
}

const allBranches: Branch[] = [
  { id: "b1", name: "Nizami Şubesi", city: "Bakü", type: "Restoran", revenue: 18500, orders: 420, rating: 4.2, status: "active", manager: "Elçin Əliyev", phone: "+994 50 123 45 67" },
  { id: "b2", name: "Gənclik Şubesi", city: "Bakü", type: "Restoran", revenue: 15200, orders: 380, rating: 4.0, status: "active", manager: "Leyla Həsənova", phone: "+994 50 234 56 78" },
  { id: "b3", name: "28 May Şubesi", city: "Bakü", type: "Kafe", revenue: 11200, orders: 320, rating: 4.5, status: "active", manager: "Nigar İsmayılova", phone: "+994 50 345 67 89" },
  { id: "b4", name: "Sumqayıt Merkez", city: "Sumqayıt", type: "Restoran", revenue: 9800, orders: 290, rating: 4.1, status: "active", manager: "Rəşad Məmmədov", phone: "+994 50 456 78 90" },
  { id: "b5", name: "Gəncə Lounge", city: "Gəncə", type: "Kafe", revenue: 8200, orders: 240, rating: 4.3, status: "active", manager: "Aysel Quliyeva", phone: "+994 50 567 89 01" },
  { id: "b6", name: "Mingəçevir Park", city: "Mingəçevir", type: "Restoran", revenue: 6500, orders: 195, rating: 3.9, status: "inactive", manager: "Tural Əhmədov", phone: "+994 50 678 90 12" },
  { id: "b7", name: "Şəki Bahçe", city: "Şəki", type: "Kafe", revenue: 5400, orders: 160, rating: 4.6, status: "active", manager: "Zərnəgər Rəhimova", phone: "+994 50 789 01 23" },
  { id: "b8", name: "Lənkəran Sahil", city: "Lənkəran", type: "Restoran", revenue: 7200, orders: 210, rating: 4.0, status: "pending", manager: "Vüsal Kərimov", phone: "+994 50 890 12 34" },
  { id: "b9", name: "Quba Dağ", city: "Quba", type: "Kafe", revenue: 4800, orders: 145, rating: 4.4, status: "active", manager: "Günay Nəsirova", phone: "+994 50 901 23 45" },
  { id: "b10", name: "Xırdalan Fast", city: "Xırdalan", type: "Restoran", revenue: 9100, orders: 275, rating: 3.8, status: "active", manager: "Orxan Səfərov", phone: "+994 50 012 34 56" },
  { id: "b11", name: "Nəsimi Bulvar", city: "Bakü", type: "Kafe", revenue: 13500, orders: 350, rating: 4.7, status: "active", manager: "Dilarə Əliyeva", phone: "+994 50 135 79 13" },
  { id: "b12", name: "Şirvan Marina", city: "Şirvan", type: "Restoran", revenue: 6100, orders: 185, rating: 3.7, status: "inactive", manager: "Fuad İbrahimov", phone: "+994 50 246 80 24" },
];

const chartData = [
  { name: "Nizami", gelir: 18500 },
  { name: "Gənclik", gelir: 15200 },
  { name: "28 May", gelir: 11200 },
  { name: "Sumqayıt", gelir: 9800 },
  { name: "Gəncə", gelir: 8200 },
  { name: "Mingəçevir", gelir: 6500 },
  { name: "Şəki", gelir: 5400 },
  { name: "Lənkəran", gelir: 7200 },
  { name: "Quba", gelir: 4800 },
  { name: "Xırdalan", gelir: 9100 },
  { name: "Nəsimi", gelir: 13500 },
  { name: "Şirvan", gelir: 6100 },
];

// ─── Status Config ───────────────────────────────────────

const statusConfig = {
  active: { label: "Aktif", color: "bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5]", dot: "bg-[#059669]" },
  inactive: { label: "Pasif", color: "bg-[#F1F5F9] text-[#94A3B8] hover:bg-[#F1F5F9]", dot: "bg-[#94A3B8]" },
  pending: { label: "Onay Bekleyen", color: "bg-[#FEF3C7] text-[#D97706] hover:bg-[#FEF3C7]", dot: "bg-[#D97706]" },
};

const cities = ["Tümü", "Bakü", "Sumqayıt", "Gəncə", "Mingəçevir", "Şəki", "Lənkəran", "Quba", "Xırdalan", "Şirvan"];
const types = ["Tümü", "Restoran", "Kafe"];
const statuses = ["Tümü", "Aktif", "Pasif", "Onay Bekleyen"];

// ─── Chart Tooltip ───────────────────────────────────────

function BranchTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload) return null;
  return (
    <div className="bg-white rounded-lg border border-[#E2E8F0] shadow-lg p-3">
      <p className="text-sm font-semibold text-[#0F172A] mb-1">{label}</p>
      <p className="text-sm text-[#475569]">Gelir: <span className="font-semibold text-[#0F172A]">₼{payload[0]?.value?.toLocaleString()}</span></p>
    </div>
  );
}

// ─── KPI Card ────────────────────────────────────────────

function BranchKPICard({
  title,
  value,
  change,
  trend,
  icon: Icon,
  accent,
  delay,
}: {
  title: string;
  value: string;
  change: string;
  trend: "up" | "down";
  icon: React.ElementType;
  accent: string;
  delay: number;
}) {
  const TrendIcon = trend === "up" ? TrendingUp : TrendingDown;
  const trendColor = trend === "up" ? "text-[#059669] bg-[#D1FAE5]" : "text-[#DC2626] bg-[#FEE2E2]";
  return (
    <Card
      className="opacity-0 animate-fade-in transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "forwards" }}
    >
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-full" style={{ backgroundColor: `${accent}1A` }}>
              <Icon className="w-5 h-5" style={{ color: accent }} />
            </div>
            <span className="text-[13px] font-medium text-[#94A3B8] uppercase tracking-wide">{title}</span>
          </div>
          <div className={cn("flex items-center gap-1 text-xs font-semibold rounded-full px-2 py-0.5", trendColor)}>
            <TrendIcon className="w-3 h-3" />
            {change}
          </div>
        </div>
        <p className="text-[32px] font-bold text-[#0F172A] leading-tight tracking-tight">{value}</p>
        <p className="text-[13px] text-[#94A3B8] mt-1">Geçen aya göre</p>
      </CardContent>
    </Card>
  );
}

// ─── Main Component ──────────────────────────────────────

export default function BranchesPage() {
  const [search, setSearch] = useState("");
  const [cityFilter, setCityFilter] = useState("Tümü");
  const [typeFilter, setTypeFilter] = useState("Tümü");
  const [statusFilter, setStatusFilter] = useState("Tümü");
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);

  const filteredBranches = useMemo(() => {
    return allBranches.filter((b) => {
      const matchSearch = b.name.toLowerCase().includes(search.toLowerCase()) || b.city.toLowerCase().includes(search.toLowerCase());
      const matchCity = cityFilter === "Tümü" || b.city === cityFilter;
      const matchType = typeFilter === "Tümü" || b.type === typeFilter;
      const matchStatus = statusFilter === "Tümü" || statusConfig[b.status].label === statusFilter;
      return matchSearch && matchCity && matchType && matchStatus;
    });
  }, [search, cityFilter, typeFilter, statusFilter]);

  const activeCount = allBranches.filter((b) => b.status === "active").length;
  const inactiveCount = allBranches.filter((b) => b.status === "inactive").length;
  const pendingCount = allBranches.filter((b) => b.status === "pending").length;

  return (
    <div className="space-y-6">
      {/* ═══ Page Header ════════════════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Şube Yönetimi</h1>
          <p className="text-sm text-[#475569] mt-0.5">Tüm şubelerinizi yönetin ve performanslarını izleyin</p>
        </div>
        <Button className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-9 gap-2">
          <Store className="w-4 h-4" />
          Yeni Şube Ekle
        </Button>
      </div>

      {/* ═══ KPI Cards ══════════════════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        <BranchKPICard title="Toplam Şube" value={String(allBranches.length)} change="+2" trend="up" icon={Building2} accent="#2563EB" delay={0} />
        <BranchKPICard title="Aktif Şube" value={String(activeCount)} change="+1" trend="up" icon={Store} accent="#059669" delay={80} />
        <BranchKPICard title="Pasif Şube" value={String(inactiveCount)} change="-1" trend="down" icon={Power} accent="#94A3B8" delay={160} />
        <BranchKPICard title="Onay Bekleyen" value={String(pendingCount)} change="+1" trend="up" icon={Star} accent="#D97706" delay={240} />
      </div>

      {/* ═══ Filters ════════════════════════════════════ */}
      <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "200ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
              <Input
                placeholder="Şube adı veya şehir ara..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-9 border-[#E2E8F0] text-sm"
              />
            </div>
            <div className="flex gap-3 flex-wrap">
              {/* City Filter */}
              <div className="relative">
                <select
                  value={cityFilter}
                  onChange={(e) => setCityFilter(e.target.value)}
                  className="h-9 px-3 pr-8 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors appearance-none cursor-pointer min-w-[130px]"
                >
                  {cities.map((c) => <option key={c} value={c}>{c === "Tümü" ? "Tüm Şehirler" : c}</option>)}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8] pointer-events-none" />
              </div>
              {/* Type Filter */}
              <div className="relative">
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="h-9 px-3 pr-8 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors appearance-none cursor-pointer min-w-[120px]"
                >
                  {types.map((t) => <option key={t} value={t}>{t === "Tümü" ? "Tüm Türler" : t}</option>)}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8] pointer-events-none" />
              </div>
              {/* Status Filter */}
              <div className="relative">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="h-9 px-3 pr-8 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors appearance-none cursor-pointer min-w-[140px]"
                >
                  {statuses.map((s) => <option key={s} value={s}>{s === "Tümü" ? "Tüm Durumlar" : s}</option>)}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8] pointer-events-none" />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ═══ Branch Table + Chart ═══════════════════════ */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* ── Branch Table ── */}
        <Card className="xl:col-span-2 opacity-0 animate-fade-in-up" style={{ animationDelay: "300ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div>
              <CardTitle className="text-base font-semibold text-[#0F172A]">Şube Listesi</CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">{filteredBranches.length} şube bulundu</CardDescription>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Filter className="w-4 h-4 text-[#94A3B8]" />
            </Button>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Şube</th>
                    <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Şehir</th>
                    <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Tür</th>
                    <th className="text-right text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Gelir</th>
                    <th className="text-right text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Sipariş</th>
                    <th className="text-center text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Puan</th>
                    <th className="text-center text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Durum</th>
                    <th className="text-right text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">Eylemler</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredBranches.map((branch, idx) => {
                    const st = statusConfig[branch.status];
                    return (
                      <tr
                        key={branch.id}
                        className={cn(
                          "border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors opacity-0 animate-fade-in",
                          idx % 2 === 0 ? "bg-white" : "bg-[#FAFBFC]"
                        )}
                        style={{ animationDelay: `${350 + idx * 40}ms`, animationFillMode: "forwards", animationDuration: "300ms" }}
                      >
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-3">
                            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[#DBEAFE] text-[#2563EB] text-xs font-bold shrink-0">
                              {branch.name.charAt(0)}
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-[#0F172A]">{branch.name}</p>
                              <p className="text-[11px] text-[#94A3B8]">{branch.manager}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-1.5">
                            <MapPin className="w-3.5 h-3.5 text-[#94A3B8]" />
                            <span className="text-sm text-[#475569]">{branch.city}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <span className="text-sm text-[#475569]">{branch.type}</span>
                        </td>
                        <td className="px-3 py-3 text-right">
                          <span className="text-sm font-semibold text-[#0F172A]">₼{branch.revenue.toLocaleString()}</span>
                        </td>
                        <td className="px-3 py-3 text-right">
                          <span className="text-sm text-[#475569]">{branch.orders}</span>
                        </td>
                        <td className="px-3 py-3 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <Star className="w-3.5 h-3.5 text-[#D97706] fill-[#D97706]" />
                            <span className="text-sm font-medium text-[#0F172A]">{branch.rating}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-center">
                          <Badge className={cn("text-[11px] h-5 px-2 font-medium", st.color)}>
                            <span className={cn("w-1.5 h-1.5 rounded-full mr-1.5", st.dot)} />
                            {st.label}
                          </Badge>
                        </td>
                        <td className="px-3 py-3 text-right relative">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setOpenDropdownId(openDropdownId === branch.id ? null : branch.id)}
                          >
                            <MoreHorizontal className="w-4 h-4 text-[#94A3B8]" />
                          </Button>
                          {openDropdownId === branch.id && (
                            <>
                              <div className="fixed inset-0 z-40" onClick={() => setOpenDropdownId(null)} />
                              <div className="absolute right-3 top-10 w-44 bg-white rounded-lg border border-[#E2E8F0] shadow-lg z-50 overflow-hidden">
                                <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors" onClick={() => setOpenDropdownId(null)}>
                                  <Eye className="w-3.5 h-3.5 text-[#475569]" /> Profil Gör
                                </button>
                                <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors" onClick={() => setOpenDropdownId(null)}>
                                  <Edit3 className="w-3.5 h-3.5 text-[#475569]" /> Düzenle
                                </button>
                                <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors" onClick={() => setOpenDropdownId(null)}>
                                  <Power className="w-3.5 h-3.5 text-[#475569]" /> Durum Değiştir
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

        {/* ── Bar Chart ── */}
        <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "400ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold text-[#0F172A]">Şube Karşılaştırma</CardTitle>
            <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Aylık gelir bazında şubeler</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[380px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 11 }} interval={0} angle={-30} textAnchor="end" height={60} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} tickFormatter={(v: number) => `₼${(v / 1000).toFixed(0)}K`} />
                  <Tooltip content={<BranchTooltip />} />
                  <Bar dataKey="gelir" fill="#2563EB" radius={[6, 6, 0, 0]} maxBarSize={36} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ═══ Branch Cards Grid ══════════════════════════ */}
      <div>
        <h2 className="text-lg font-semibold text-[#0F172A] mb-4 opacity-0 animate-fade-in" style={{ animationDelay: "450ms", animationFillMode: "forwards" }}>
          Şube Özeti
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {allBranches.slice(0, 8).map((branch, idx) => {
            const st = statusConfig[branch.status];
            const initials = branch.name.split(" ").map((w) => w[0]).join("").slice(0, 2);
            return (
              <Card
                key={branch.id}
                className="opacity-0 animate-fade-in-up transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5 cursor-pointer"
                style={{ animationDelay: `${500 + idx * 60}ms`, animationFillMode: "forwards", animationDuration: "400ms" }}
              >
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-10 h-10 rounded-full bg-[#DBEAFE] text-[#2563EB] text-sm font-bold">
                        {initials}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[#0F172A]">{branch.name}</p>
                        <p className="text-[11px] text-[#94A3B8]">{branch.manager}</p>
                      </div>
                    </div>
                    <Badge className={cn("text-[10px] h-4 px-1.5", st.color)}>
                      <span className={cn("w-1 h-1 rounded-full mr-1", st.dot)} />
                      {st.label}
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[#94A3B8]">Şehir</span>
                      <span className="text-xs font-medium text-[#475569]">{branch.city}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[#94A3B8]">Gelir (aylık)</span>
                      <span className="text-xs font-semibold text-[#0F172A]">₼{branch.revenue.toLocaleString()}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[#94A3B8]">Puan</span>
                      <div className="flex items-center gap-1">
                        <Star className="w-3 h-3 text-[#D97706] fill-[#D97706]" />
                        <span className="text-xs font-medium text-[#0F172A]">{branch.rating}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[#94A3B8]">Sipariş</span>
                      <span className="text-xs font-medium text-[#475569]">{branch.orders}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

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
