import { useState, useEffect } from "react";
import {
  Wallet,
  Target,
  Eye,
  MousePointerClick,
  Plus,
  MoreHorizontal,
  Search,
  Filter,
  Sparkles,
  AlertTriangle,
  Lightbulb,
  Clock,
  Brain,
  ChevronRight,
  PauseCircle,
  PlayCircle,
  Edit3,
  Trash2,
  TrendingUp,
  BarChart3,
  RefreshCw,
  Download,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { KPICardsSkeleton, ChartSkeleton, AlertListSkeleton } from "@/components/LoadingSkeleton";

// ─── Types ───────────────────────────────────────────────

interface Campaign {
  id: string;
  name: string;
  platform: "Google" | "Meta" | "TikTok";
  budget: number;
  spent: number;
  roas: number;
  impressions: number;
  clicks: number;
  status: "active" | "paused";
}

interface OptimizationTip {
  id: string;
  title: string;
  description: string;
  priority: "high" | "medium" | "low" | "info";
  icon: string;
}

// ─── Mock Data ───────────────────────────────────────────

const campaigns: Campaign[] = [
  { id: "c1", name: "Yaz Kampanyası 2024", platform: "Google", budget: 15000, spent: 12500, roas: 4.2, impressions: 15200, clicks: 1200, status: "active" },
  { id: "c2", name: "Hafta Sonu Özel", platform: "Meta", budget: 8000, spent: 7200, roas: 3.5, impressions: 9800, clicks: 850, status: "active" },
  { id: "c3", name: "Genç Kitle Tanıtım", platform: "TikTok", budget: 5000, spent: 4800, roas: 2.8, impressions: 8200, clicks: 620, status: "active" },
  { id: "c4", name: "Ramazan Menüsü", platform: "Google", budget: 12000, spent: 11500, roas: 3.9, impressions: 6800, clicks: 540, status: "paused" },
  { id: "c5", name: "Yeni Şube Lansman", platform: "Meta", budget: 10000, spent: 3200, roas: 1.8, impressions: 3200, clicks: 180, status: "active" },
  { id: "c6", name: "Viral Video Kampanya", platform: "TikTok", budget: 6000, spent: 5900, roas: 4.8, impressions: 12400, clicks: 980, status: "active" },
  { id: "c7", name: "Sadakat Programı", platform: "Google", budget: 4000, spent: 3800, roas: 2.4, impressions: 4100, clicks: 310, status: "active" },
  { id: "c8", name: "Öğle Menüsü Tanıtım", platform: "Meta", budget: 7000, spent: 2100, roas: 3.2, impressions: 5700, clicks: 420, status: "paused" },
];

const spendTrendData = [
  { day: "Pzt", Google: 1800, Meta: 1200, TikTok: 800 },
  { day: "Sal", Google: 2200, Meta: 1400, TikTok: 950 },
  { day: "Çar", Google: 1900, Meta: 1100, TikTok: 700 },
  { day: "Per", Google: 2400, Meta: 1600, TikTok: 1100 },
  { day: "Cum", Google: 2100, Meta: 1300, TikTok: 900 },
  { day: "Cmt", Google: 1500, Meta: 1800, TikTok: 1200 },
  { day: "Paz", Google: 1200, Meta: 1500, TikTok: 1000 },
];

const optimizationTips: OptimizationTip[] = [
  { id: "o1", title: "ROAS Düşüşü Tespiti", description: "'Yeni Şube Lansman' kampanyasının ROAS değeri 1.8'e düştü. Bütçeyi azaltmanız veya hedef kitleyi daraltmanız önerilir.", priority: "high", icon: "alert" },
  { id: "o2", title: "Hedef Kitle Genişletme", description: "TikTok kampanyalarınız 18-24 yaş aralığında yüksek performans gösteriyor. Benzer kitleleri hedefleyerek erişimi artırabilirsiniz.", priority: "medium", icon: "lightbulb" },
  { id: "o3", title: "En İyi Zaman Aralığı", description: "Hafta sonu 18:00-21:00 arası dönüşüm oranlarınız %42 daha yüksek. Bütçenizin %60'ını bu zaman dilimine ayırın.", priority: "info", icon: "clock" },
  { id: "o4", title: "AI Otomatik Optimizasyon", description: "AI sistemi, Google Ads teklif stratejinizi Maksimize Dönüşüme geçirmenizin maliyetleri %18 azaltacağını öngörüyor.", priority: "medium", icon: "brain" },
];

// ─── Helper Functions ────────────────────────────────────

function getPlatformBadge(platform: Campaign["platform"]) {
  const styles = {
    Google: "bg-[#DBEAFE] text-[#2563EB] hover:bg-[#DBEAFE]",
    Meta: "bg-[#1E293B] text-white hover:bg-[#1E293B]",
    TikTok: "bg-[#0F172A] text-white hover:bg-[#0F172A]",
  };
  return styles[platform];
}

function getROASBadge(roas: number) {
  if (roas >= 4) return "bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5]";
  if (roas >= 3) return "bg-[#DBEAFE] text-[#2563EB] hover:bg-[#DBEAFE]";
  if (roas >= 2) return "bg-[#FEF3C7] text-[#D97706] hover:bg-[#FEF3C7]";
  return "bg-[#FEE2E2] text-[#DC2626] hover:bg-[#FEE2E2]";
}

function getStatusBadge(status: Campaign["status"]) {
  if (status === "active") return "bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5]";
  return "bg-[#E2E8F0] text-[#475569] hover:bg-[#E2E8F0]";
}

function getTipPriorityStyle(priority: OptimizationTip["priority"]) {
  switch (priority) {
    case "high": return { border: "border-l-[#DC2626]", bg: "bg-[#FEE2E2]", icon: "text-[#DC2626]" };
    case "medium": return { border: "border-l-[#D97706]", bg: "bg-[#FEF3C7]", icon: "text-[#D97706]" };
    case "low": return { border: "border-l-[#7C3AED]", bg: "bg-[#EDE9FE]", icon: "text-[#7C3AED]" };
    case "info": return { border: "border-l-[#2563EB]", bg: "bg-[#DBEAFE]", icon: "text-[#2563EB]" };
  }
}

function getTipIconComponent(icon: string) {
  switch (icon) {
    case "alert": return AlertTriangle;
    case "lightbulb": return Lightbulb;
    case "clock": return Clock;
    case "brain": return Brain;
    default: return Sparkles;
  }
}

// ─── Custom Tooltip ──────────────────────────────────────

function SpendTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload) return null;
  return (
    <div className="bg-white rounded-lg border border-[#E2E8F0] shadow-lg p-3">
      <p className="text-sm font-semibold text-[#0F172A] mb-2">{label}</p>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 text-sm">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-[#475569]">{entry.name}:</span>
          <span className="font-semibold text-[#0F172A]">₺{entry.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

// ─── KPI Card Component ──────────────────────────────────

interface KPICardProps {
  title: string;
  value: string;
  change: string;
  changeValue: string;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  delay: number;
}

function KPICard({ title, value, change, icon: Icon, iconBg, iconColor, delay }: KPICardProps) {
  return (
    <Card
      className="opacity-0 animate-fade-in transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "forwards" }}
    >
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={cn("flex items-center justify-center w-10 h-10 rounded-full", iconBg)}>
              <Icon className="w-5 h-5" style={{ color: iconColor }} />
            </div>
            <span className="text-[13px] font-medium text-[#94A3B8] uppercase tracking-wide">{title}</span>
          </div>
          <Badge className="bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5] text-xs">
            <TrendingUp className="w-3 h-3 mr-1" />
            {change}
          </Badge>
        </div>
        <p className="text-[32px] font-bold text-[#0F172A] leading-tight tracking-tight">{value}</p>
        <p className="text-[13px] text-[#94A3B8] mt-1">Geçen aya göre</p>
      </CardContent>
    </Card>
  );
}

// ─── Main Component ──────────────────────────────────────

export default function AdsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("all");
  const [overviewData, setOverviewData] = useState({
    total_spent: 54600,
    avg_roas: 3.5,
    total_impressions: 62600,
    total_clicks: 4100,
  });
  const [campaigns, setCampaigns] = useState(mockCampaigns);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Load overview and campaigns from API
  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [overviewRes, campaignsRes] = await Promise.all([
        api.ads.overview(),
        api.ads.campaigns(),
      ]);
      if (overviewRes.success && overviewRes.data) {
        setOverviewData(overviewRes.data as any);
      }
      if (campaignsRes.success && campaignsRes.data) {
        setCampaigns(campaignsRes.data as any[]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Veriler yüklenemedi");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }

  // Loading skeleton state
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Reklam Yönetimi</h1>
            <p className="text-sm text-[#475569] mt-0.5">Tüm reklam kampanyalarınızı tek yerden yönetin</p>
          </div>
          <Skeleton className="w-36 h-10 rounded-lg" />
        </div>
        <KPICardsSkeleton count={4} />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <ChartSkeleton />
          <AlertListSkeleton count={4} />
        </div>
        <style>{`@keyframes fadeIn{from{opacity:0}to{opacity:1}}@keyframes fadeInUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}.animate-fade-in{animation:fadeIn .5s ease-out}.animate-fade-in-up{animation:fadeInUp .5s cubic-bezier(.16,1,.3,1)}`}</style>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p className="text-red-500 font-medium">{error}</p>
        <Button onClick={handleRefresh} variant="outline" size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          Tekrar Dene
        </Button>
      </div>
    );
  }

  const filteredCampaigns = campaigns.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTab = activeTab === "all" || c.platform.toLowerCase() === activeTab;
    return matchesSearch && matchesTab;
  });

  const totalSpent = campaigns.reduce((sum, c) => sum + c.spent, 0);
  const avgROAS = (campaigns.reduce((sum, c) => sum + c.roas, 0) / campaigns.length).toFixed(1);
  const totalImpressions = campaigns.reduce((sum, c) => sum + c.impressions, 0);
  const totalClicks = campaigns.reduce((sum, c) => sum + c.clicks, 0);

  return (
    <div className="space-y-6">
      {/* ═══ Page Header ════════════════════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Reklam Yönetimi</h1>
          <p className="text-sm text-[#475569] mt-0.5">Tüm reklam kampanyalarınızı tek yerden yönetin</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-10 gap-2" onClick={handleRefresh}>
            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
            Yenile
          </Button>
          <Button variant="outline" size="sm" className="h-10 gap-2">
            <Download className="w-4 h-4" />
            Dışa Aktar
          </Button>
          <Button className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-10 px-4 gap-2">
            <Plus className="w-4 h-4" />
            Kampanya Oluştur
          </Button>
        </div>
      </div>

      {/* ═══ KPI Cards ══════════════════════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        <KPICard title="Toplam Harcama" value={`₺${totalSpent.toLocaleString()}`} change="+15%" changeValue="+15%" icon={Wallet} iconBg="bg-[#DBEAFE]" iconColor="#2563EB" delay={0} />
        <KPICard title="Ortalama ROAS" value={`${avgROAS}x`} change="+0.3x" changeValue="+0.3x" icon={Target} iconBg="bg-[#EDE9FE]" iconColor="#7C3AED" delay={80} />
        <KPICard title="Toplam Gösterim" value={totalImpressions.toLocaleString()} change="+22%" changeValue="+22%" icon={Eye} iconBg="bg-[#FEF3C7]" iconColor="#D97706" delay={160} />
        <KPICard title="Toplam Tıklama" value={totalClicks.toLocaleString()} change="+18%" changeValue="+18%" icon={MousePointerClick} iconBg="bg-[#D1FAE5]" iconColor="#059669" delay={240} />
      </div>

      {/* ═══ Platform Tabs + Campaign Table ═════════════════ */}
      <Tabs defaultValue="all" onValueChange={setActiveTab}>
        <Card
          className="opacity-0 animate-fade-in-up"
          style={{ animationDelay: "200ms", animationFillMode: "forwards", animationDuration: "500ms" }}
        >
          <CardHeader className="pb-0">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <CardTitle className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-[#475569]" />
                  Kampanyalar
                </CardTitle>
                <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">
                  {filteredCampaigns.length} kampanya listeleniyor
                </CardDescription>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
                  <Input
                    placeholder="Kampanya ara..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 h-9 w-[200px] text-sm"
                  />
                </div>
                <Button variant="outline" size="icon" className="h-9 w-9">
                  <Filter className="w-4 h-4 text-[#475569]" />
                </Button>
              </div>
            </div>
            <TabsList className="mt-4 bg-[#F1F5F9]">
              <TabsTrigger value="all" className="text-sm data-[state=active]:bg-white data-[state=active]:text-[#0F172A]">Tümü</TabsTrigger>
              <TabsTrigger value="google" className="text-sm data-[state=active]:bg-[#2563EB] data-[state=active]:text-white">Google</TabsTrigger>
              <TabsTrigger value="meta" className="text-sm data-[state=active]:bg-[#1E293B] data-[state=active]:text-white">Meta</TabsTrigger>
              <TabsTrigger value="tiktok" className="text-sm data-[state=active]:bg-[#0F172A] data-[state=active]:text-white">TikTok</TabsTrigger>
            </TabsList>
          </CardHeader>
          <CardContent className="pt-4">
            <TabsContent value={activeTab} className="mt-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#E2E8F0]">
                      <th className="text-left font-semibold text-[#475569] px-3 py-3">Kampanya Adı</th>
                      <th className="text-left font-semibold text-[#475569] px-3 py-3">Platform</th>
                      <th className="text-right font-semibold text-[#475569] px-3 py-3">Bütçe</th>
                      <th className="text-right font-semibold text-[#475569] px-3 py-3">Harcama</th>
                      <th className="text-right font-semibold text-[#475569] px-3 py-3">ROAS</th>
                      <th className="text-right font-semibold text-[#475569] px-3 py-3">Gösterim</th>
                      <th className="text-right font-semibold text-[#475569] px-3 py-3">Tıklama</th>
                      <th className="text-center font-semibold text-[#475569] px-3 py-3">Durum</th>
                      <th className="text-center font-semibold text-[#475569] px-3 py-3">Eylemler</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCampaigns.map((campaign) => (
                      <tr key={campaign.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                        <td className="px-3 py-3">
                          <span className="font-medium text-[#0F172A]">{campaign.name}</span>
                        </td>
                        <td className="px-3 py-3">
                          <Badge className={cn("text-[11px] font-semibold", getPlatformBadge(campaign.platform))}>
                            {campaign.platform}
                          </Badge>
                        </td>
                        <td className="text-right px-3 py-3 text-[#475569]">₺{campaign.budget.toLocaleString()}</td>
                        <td className="text-right px-3 py-3 text-[#475569]">₺{campaign.spent.toLocaleString()}</td>
                        <td className="text-right px-3 py-3">
                          <Badge className={cn("text-[11px] font-semibold", getROASBadge(campaign.roas))}>
                            {campaign.roas}x
                          </Badge>
                        </td>
                        <td className="text-right px-3 py-3 text-[#475569]">{campaign.impressions.toLocaleString()}</td>
                        <td className="text-right px-3 py-3 text-[#475569]">{campaign.clicks.toLocaleString()}</td>
                        <td className="text-center px-3 py-3">
                          <Badge className={cn("text-[11px] font-semibold", getStatusBadge(campaign.status))}>
                            {campaign.status === "active" ? "Aktif" : "Pasif"}
                          </Badge>
                        </td>
                        <td className="text-center px-3 py-3">
                          <div className="flex items-center justify-center gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7">
                              <Edit3 className="w-3.5 h-3.5 text-[#475569]" />
                            </Button>
                            {campaign.status === "active" ? (
                              <Button variant="ghost" size="icon" className="h-7 w-7">
                                <PauseCircle className="w-3.5 h-3.5 text-[#D97706]" />
                              </Button>
                            ) : (
                              <Button variant="ghost" size="icon" className="h-7 w-7">
                                <PlayCircle className="w-3.5 h-3.5 text-[#059669]" />
                              </Button>
                            )}
                            <Button variant="ghost" size="icon" className="h-7 w-7">
                              <Trash2 className="w-3.5 h-3.5 text-[#DC2626]" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {filteredCampaigns.length === 0 && (
                <div className="text-center py-12 text-[#94A3B8]">
                  <Search className="w-10 h-10 mx-auto mb-3 opacity-40" />
                  <p>Kampanya bulunamadı.</p>
                </div>
              )}
            </TabsContent>
          </CardContent>
        </Card>
      </Tabs>

      {/* ═══ Spend Trend + AI Audit ═════════════════════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ── Spend Trend Chart ────────────────────────── */}
        <Card
          className="opacity-0 animate-fade-in-up"
          style={{ animationDelay: "300ms", animationFillMode: "forwards", animationDuration: "500ms" }}
        >
          <CardHeader>
            <CardTitle className="text-base font-semibold text-[#0F172A]">Harcama Trendi</CardTitle>
            <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Son 7 gün platform bazlı harcama</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={spendTrendData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} tickFormatter={(v: number) => `₺${v}`} />
                  <Tooltip content={<SpendTooltip />} />
                  <Legend
                    formatter={(value: string) => <span className="text-xs text-[#475569]">{value}</span>}
                    iconType="circle"
                    iconSize={8}
                  />
                  <Bar dataKey="Google" stackId="a" fill="#2563EB" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="Meta" stackId="a" fill="#7C3AED" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="TikTok" stackId="a" fill="#0F172A" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* ── AI Audit Panel ───────────────────────────── */}
        <Card
          className="border-l-[3px] border-l-[#7C3AED] bg-[#F5F3FF] opacity-0 animate-fade-in-up"
          style={{ animationDelay: "400ms", animationFillMode: "forwards", animationDuration: "500ms" }}
        >
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#7C3AED]" />
              <CardTitle className="text-base font-semibold text-[#0F172A]">AI Denetim</CardTitle>
              <Badge className="bg-[#EDE9FE] text-[#7C3AED] hover:bg-[#EDE9FE] text-[11px] h-5 px-2 font-semibold">4 Yeni</Badge>
            </div>
            <CardDescription className="text-[13px] text-[#475569] mt-0.5">AI tarafından tespit edilen optimizasyon fırsatları</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {optimizationTips.map((tip, index) => {
                const styles = getTipPriorityStyle(tip.priority);
                const IconComponent = getTipIconComponent(tip.icon);
                return (
                  <div
                    key={tip.id}
                    className={cn(
                      "flex gap-3 p-3 border-l-[3px] rounded-r-lg bg-white",
                      styles.border,
                      "opacity-0 animate-slide-in-right"
                    )}
                    style={{
                      animationDelay: `${450 + index * 100}ms`,
                      animationFillMode: "forwards",
                      animationDuration: "300ms",
                    }}
                  >
                    <div className={cn("flex items-center justify-center w-8 h-8 rounded-full shrink-0", styles.bg)}>
                      <IconComponent className={cn("w-4 h-4", styles.icon)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="text-sm font-semibold text-[#0F172A]">{tip.title}</p>
                        <Badge
                          className={cn(
                            "text-[10px] h-4 px-1.5 font-semibold",
                            tip.priority === "high" && "bg-[#FEE2E2] text-[#DC2626] hover:bg-[#FEE2E2]",
                            tip.priority === "medium" && "bg-[#FEF3C7] text-[#D97706] hover:bg-[#FEF3C7]",
                            tip.priority === "info" && "bg-[#DBEAFE] text-[#2563EB] hover:bg-[#DBEAFE]",
                            tip.priority === "low" && "bg-[#EDE9FE] text-[#7C3AED] hover:bg-[#EDE9FE]",
                          )}
                        >
                          {tip.priority === "high" ? "Yüksek" : tip.priority === "medium" ? "Orta" : tip.priority === "info" ? "Bilgi" : "Düşük"}
                        </Badge>
                      </div>
                      <p className="text-xs text-[#475569] leading-relaxed">{tip.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            <button className="mt-3 text-xs font-medium text-[#7C3AED] hover:underline flex items-center gap-1">
              Tüm Önerileri Gör
              <ChevronRight className="w-3 h-3" />
            </button>
          </CardContent>
        </Card>
      </div>

      {/* ═══ CSS Animations ═════════════════════════════════ */}
      <style>{`
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
        .animate-fade-in {
          animation: fadeIn 0.5s ease-out;
        }
        .animate-fade-in-up {
          animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .animate-slide-in-right {
          animation: slideInRight 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}
