import { useState } from "react";
import {
  Eye,
  Clock,
  LogOut,
  Users,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Download,
  FileText,
  Image,
  Monitor,
  Smartphone,
  Tablet,
  MapPin,
  BarChart3,
  PieChartIcon,
  Activity,
  ChevronDown,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────

interface PagePerformance {
  id: string;
  page: string;
  views: number;
  avgTime: string;
  bounceRate: string;
  trend: "up" | "down" | "stable";
}

// ─── Mock Data ───────────────────────────────────────────

const visitorTrendData = Array.from({ length: 30 }, (_, i) => {
  const day = i + 1;
  const baseTotal = 1200 + Math.sin(i * 0.4) * 300 + i * 15;
  const baseUnique = baseTotal * 0.65;
  const baseConversion = baseTotal * 0.08;
  return {
    day: `${day} Haz`,
    toplam: Math.round(baseTotal),
    tekil: Math.round(baseUnique),
    donusum: Math.round(baseConversion),
  };
});

const sourceData = [
  { name: "Doğrudan", value: 45, color: "#2563EB", bgClass: "bg-[#2563EB]" },
  { name: "Sosyal Medya", value: 25, color: "#DB2777", bgClass: "bg-[#DB2777]" },
  { name: "Organik", value: 18, color: "#059669", bgClass: "bg-[#059669]" },
  { name: "Paid", value: 8, color: "#D97706", bgClass: "bg-[#D97706]" },
  { name: "Referral", value: 4, color: "#94A3B8", bgClass: "bg-[#94A3B8]" },
];

const deviceData = [
  { name: "Mobil", value: 62, color: "#059669" },
  { name: "Masaüstü", value: 30, color: "#2563EB" },
  { name: "Tablet", value: 8, color: "#D97706" },
];

const locationData = [
  { city: "Bakı", percentage: 52 },
  { city: "Sumqayıt", percentage: 18 },
  { city: "Gəncə", percentage: 14 },
  { city: "Mingəçevir", percentage: 10 },
  { city: "Şəki", percentage: 6 },
];

const pagePerformanceData: PagePerformance[] = [
  { id: "p1", page: "/anasayfa", views: 12450, avgTime: "2dk 14sn", bounceRate: "%32.5", trend: "up" },
  { id: "p2", page: "/menu", views: 8320, avgTime: "3dk 42sn", bounceRate: "%28.1", trend: "up" },
  { id: "p3", page: "/hakkimizda", views: 4100, avgTime: "1dk 58sn", bounceRate: "%45.3", trend: "down" },
  { id: "p4", page: "/subeler", views: 3650, avgTime: "2dk 35sn", bounceRate: "%38.7", trend: "stable" },
  { id: "p5", page: "/iletisim", views: 2180, avgTime: "1dk 22sn", bounceRate: "%52.1", trend: "down" },
];

// ─── Helpers ─────────────────────────────────────────────

function getTrendIcon(trend: PagePerformance["trend"]) {
  switch (trend) {
    case "up": return <ArrowUpRight className="w-4 h-4 text-[#059669]" />;
    case "down": return <ArrowDownRight className="w-4 h-4 text-[#DC2626]" />;
    case "stable": return <Minus className="w-4 h-4 text-[#94A3B8]" />;
  }
}

// ─── Custom Tooltip ──────────────────────────────────────

function VisitorTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  if (!active || !payload) return null;
  const nameMap: Record<string, string> = { toplam: "Toplam Ziyaretçi", tekil: "Tekil Ziyaretçi", donusum: "Dönüşüm" };
  return (
    <div className="bg-white rounded-lg border border-[#E2E8F0] shadow-lg p-3">
      <p className="text-sm font-semibold text-[#0F172A] mb-2">{label}</p>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 text-sm">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-[#475569]">{nameMap[entry.name] || entry.name}:</span>
          <span className="font-semibold text-[#0F172A]">{entry.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

function DeviceTooltip({ active, payload }: { active?: boolean; payload?: Array<{ name: string; value: number; payload: { color: string } }> }) {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0];
  return (
    <div className="bg-white rounded-lg border border-[#E2E8F0] shadow-lg p-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: data.payload.color }} />
        <span className="text-sm font-semibold text-[#0F172A]">{data.name}</span>
      </div>
      <p className="text-sm font-bold text-[#0F172A]">%{data.value}</p>
    </div>
  );
}

// ─── KPI Card Component ──────────────────────────────────

interface KPICardProps {
  title: string;
  value: string;
  change: string;
  changeType: "up" | "down" | "neutral";
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  delay: number;
}

function KPICard({ title, value, change, changeType, icon: Icon, iconBg, iconColor, delay }: KPICardProps) {
  const TrendIcon = changeType === "up" ? TrendingUp : changeType === "down" ? TrendingDown : Minus;
  const trendColor = changeType === "up" ? "text-[#059669] bg-[#D1FAE5]" : changeType === "down" ? "text-[#059669] bg-[#D1FAE5]" : "text-[#94A3B8] bg-[#F1F5F9]";

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
          <div className={cn("flex items-center gap-1 text-xs font-semibold rounded-full px-2 py-0.5", trendColor)}>
            <TrendIcon className="w-3 h-3" />
            {change}
          </div>
        </div>
        <p className="text-[28px] font-bold text-[#0F172A] leading-tight tracking-tight">{value}</p>
        <p className="text-[13px] text-[#94A3B8] mt-1">Geçen aya göre</p>
      </CardContent>
    </Card>
  );
}

// ─── Export Dropdown Component ───────────────────────────

function ExportDropdown() {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <Button variant="outline" size="sm" className="h-8 gap-2" onClick={() => setOpen(!open)}>
        <Download className="w-3.5 h-3.5" />
        Dışa Aktar
        <ChevronDown className={cn("w-3 h-3 transition-transform", open && "rotate-180")} />
      </Button>
      {open && (
        <div className="absolute right-0 top-9 w-[140px] bg-white rounded-lg border border-[#E2E8F0] shadow-lg z-50 overflow-hidden">
          <button className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[#F8FAFC] transition-colors text-[#0F172A]">
            <FileText className="w-4 h-4 text-[#DC2626]" /> PDF
          </button>
          <button className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[#F8FAFC] transition-colors text-[#0F172A]">
            <BarChart3 className="w-4 h-4 text-[#059669]" /> Excel
          </button>
          <button className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[#F8FAFC] transition-colors text-[#0F172A]">
            <Image className="w-4 h-4 text-[#2563EB]" /> PNG
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState("overview");

  return (
    <div className="space-y-6">
      {/* ═══ Page Header ════════════════════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Analitik Raporlar</h1>
          <p className="text-sm text-[#475569] mt-0.5">Web sitesi ve dijital performans metrikleri</p>
        </div>
        <ExportDropdown />
      </div>

      {/* ═══ KPI Cards ══════════════════════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        <KPICard title="Toplam Görüntüleme" value="45.230" change="+18.5%" changeType="up" icon={Eye} iconBg="bg-[#DBEAFE]" iconColor="#2563EB" delay={0} />
        <KPICard title="Ortalama Oturum" value="3dk 42sn" change="+5.2%" changeType="up" icon={Clock} iconBg="bg-[#FEF3C7]" iconColor="#D97706" delay={80} />
        <KPICard title="Hemen Çıkma Oranı" value="%38.2" change="-2.1%" changeType="down" icon={LogOut} iconBg="bg-[#D1FAE5]" iconColor="#059669" delay={160} />
        <KPICard title="Tekil Ziyaretçi" value="12.450" change="+22.1%" changeType="up" icon={Users} iconBg="bg-[#EDE9FE]" iconColor="#7C3AED" delay={240} />
      </div>

      {/* ═══ Tabs ═══════════════════════════════════════════ */}
      <Tabs defaultValue="overview" onValueChange={setActiveTab}>
        <TabsList className="bg-[#F1F5F9]">
          <TabsTrigger value="overview" className="text-sm data-[state=active]:bg-white data-[state=active]:text-[#0F172A]">Genel Bakış</TabsTrigger>
          <TabsTrigger value="traffic" className="text-sm data-[state=active]:bg-white data-[state=active]:text-[#0F172A]">Trafik</TabsTrigger>
          <TabsTrigger value="audience" className="text-sm data-[state=active]:bg-white data-[state=active]:text-[#0F172A]">Kitle</TabsTrigger>
          <TabsTrigger value="custom" className="text-sm data-[state=active]:bg-white data-[state=active]:text-[#0F172A]">Özel Raporlar</TabsTrigger>
        </TabsList>

        {/* ─── Genel Bakış Tab ────────────────────────────── */}
        <TabsContent value="overview" className="mt-5 space-y-5">
          {/* Ziyaretçi Trendi */}
          <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "200ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
                <Activity className="w-5 h-5 text-[#475569]" />
                Ziyaretçi Trendi (30 Gün)
              </CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Günlük ziyaretçi ve dönüşüm istatistikleri</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={visitorTrendData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="totalGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#2563EB" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="uniqueGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#7C3AED" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="conversionGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#059669" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#059669" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                    <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} interval={4} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} />
                    <Tooltip content={<VisitorTooltip />} />
                    <Legend formatter={(v: string) => ({ toplam: "Toplam", tekil: "Tekil", donusum: "Dönüşüm" }[v] || v)} iconType="circle" iconSize={8} />
                    <Area type="monotone" dataKey="toplam" stroke="#2563EB" strokeWidth={2} fill="url(#totalGradient)" />
                    <Area type="monotone" dataKey="tekil" stroke="#7C3AED" strokeWidth={2} fill="url(#uniqueGradient)" />
                    <Area type="monotone" dataKey="donusum" stroke="#059669" strokeWidth={2} fill="url(#conversionGradient)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* İkili Kart: Kaynak + Cihaz */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Kaynak Dağılımı */}
            <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "300ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-[#0F172A]">Kaynak Dağılımı</CardTitle>
                <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Trafik kaynaklarına göre dağılım</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {sourceData.map((source) => (
                    <div key={source.name}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-sm text-[#0F172A] font-medium">{source.name}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-[#0F172A]">%{source.value}</span>
                        </div>
                      </div>
                      <div className="h-2.5 bg-[#F1F5F9] rounded-full overflow-hidden">
                        <div
                          className={cn("h-full rounded-full transition-all duration-700", source.bgClass)}
                          style={{ width: `${source.value}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Cihaz Pasta Grafiği */}
            <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "400ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
                  <PieChartIcon className="w-5 h-5 text-[#475569]" />
                  Cihaz Dağılımı
                </CardTitle>
                <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Ziyaretçi cihaz türleri</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[220px] relative">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={deviceData}
                        cx="50%"
                        cy="50%"
                        innerRadius="55%"
                        outerRadius="75%"
                        paddingAngle={3}
                        dataKey="value"
                        stroke="none"
                      >
                        {deviceData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip content={<DeviceTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-xl font-bold text-[#0F172A]">100%</span>
                  </div>
                </div>
                <div className="flex items-center justify-center gap-5 mt-2">
                  {deviceData.map((device) => (
                    <div key={device.name} className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: device.color }} />
                      <span className="text-xs text-[#475569]">{device.name}</span>
                      <span className="text-xs font-semibold text-[#0F172A]">%{device.value}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sayfa Performansı + Lokasyon */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Sayfa Performansı Tablosu */}
            <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "500ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-[#0F172A]">Sayfa Performansı</CardTitle>
                <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">En çok görüntülenen sayfalar</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[#E2E8F0]">
                        <th className="text-left font-semibold text-[#475569] px-3 py-2">Sayfa</th>
                        <th className="text-right font-semibold text-[#475569] px-3 py-2">Görüntüleme</th>
                        <th className="text-right font-semibold text-[#475569] px-3 py-2">Ort. Süre</th>
                        <th className="text-right font-semibold text-[#475569] px-3 py-2">Hemen Çıkma</th>
                        <th className="text-center font-semibold text-[#475569] px-3 py-2">Trend</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagePerformanceData.map((page) => (
                        <tr key={page.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                          <td className="px-3 py-2.5 font-medium text-[#0F172A]">{page.page}</td>
                          <td className="text-right px-3 py-2.5 text-[#475569]">{page.views.toLocaleString()}</td>
                          <td className="text-right px-3 py-2.5 text-[#475569]">{page.avgTime}</td>
                          <td className="text-right px-3 py-2.5 text-[#475569]">{page.bounceRate}</td>
                          <td className="text-center px-3 py-2.5">{getTrendIcon(page.trend)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Lokasyon Dağılımı */}
            <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "550ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-[#475569]" />
                  Lokasyon Dağılımı
                </CardTitle>
                <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Şehir bazlı ziyaretçi dağılımı</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {locationData.map((loc, index) => {
                    const colors = ["bg-[#2563EB]", "bg-[#7C3AED]", "bg-[#059669]", "bg-[#D97706]", "bg-[#DB2777]"];
                    return (
                      <div key={loc.city}>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-sm font-medium text-[#0F172A]">{loc.city}</span>
                          <span className="text-sm font-bold text-[#0F172A]">%{loc.percentage}</span>
                        </div>
                        <div className="h-2.5 bg-[#F1F5F9] rounded-full overflow-hidden">
                          <div
                            className={cn("h-full rounded-full transition-all duration-700", colors[index])}
                            style={{ width: `${loc.percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-5 p-3 bg-[#F8FAFC] rounded-lg">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-[#2563EB]" />
                    <span className="text-xs text-[#475569]">
                      En çok ziyaretçi <strong className="text-[#0F172A]">Bakı</strong> şehrinden. Toplam ziyaretçilerin <strong className="text-[#0F172A]">%52'si</strong> bu bölgeden.
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ─── Trafik Tab ─────────────────────────────────── */}
        <TabsContent value="traffic" className="mt-5 space-y-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-[#0F172A]">Trafik Kaynakları Detayı</CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Kanal bazlı trafik analizi</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {sourceData.map((source) => (
                  <div key={source.name} className="flex items-center gap-4">
                    <div className={cn("w-3 h-3 rounded-full shrink-0", source.bgClass)} />
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-[#0F172A]">{source.name}</span>
                        <span className="text-sm font-bold text-[#0F172A]">%{source.value}</span>
                      </div>
                      <div className="h-3 bg-[#F1F5F9] rounded-full overflow-hidden">
                        <div className={cn("h-full rounded-full transition-all duration-700", source.bgClass)} style={{ width: `${source.value}%` }} />
                      </div>
                    </div>
                    <span className="text-xs text-[#94A3B8] w-16 text-right">{(source.value * 324).toFixed(0)} ziyaret</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Kitle Tab ──────────────────────────────────── */}
        <TabsContent value="audience" className="mt-5 space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-[#0F172A]">Cihaz Dağılımı</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[250px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={deviceData} cx="50%" cy="50%" innerRadius="50%" outerRadius="70%" paddingAngle={3} dataKey="value" stroke="none">
                        {deviceData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip content={<DeviceTooltip />} />
                      <Legend formatter={(v: string) => v} iconType="circle" iconSize={8} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-[#0F172A]">Coğrafi Dağılım</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {locationData.map((loc, index) => {
                    const colors = ["bg-[#2563EB]", "bg-[#7C3AED]", "bg-[#059669]", "bg-[#D97706]", "bg-[#DB2777]"];
                    return (
                      <div key={loc.city}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-[#0F172A]">{loc.city}</span>
                          <span className="text-sm font-bold text-[#0F172A]">%{loc.percentage}</span>
                        </div>
                        <div className="h-2.5 bg-[#F1F5F9] rounded-full overflow-hidden">
                          <div className={cn("h-full rounded-full transition-all duration-700", colors[index])} style={{ width: `${loc.percentage}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ─── Özel Raporlar Tab ──────────────────────────── */}
        <TabsContent value="custom" className="mt-5 space-y-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-[#0F172A]">Özel Rapor Oluştur</CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">İhtiyaçlarınıza özel raporlar oluşturun</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  { title: "Gelir Karşılaştırma", desc: "Şubeler arası gelir karşılaştırma raporu", icon: BarChart3 },
                  { title: "Müşteri Davranışı", desc: "Müşteri segmentasyon ve davranış analizi", icon: Users },
                  { title: "Kampanya ROI", desc: "Reklam kampanyaları getiri analizi", icon: TrendingUp },
                  { title: "İçerik Performansı", desc: "Sosyal medya içerik performans raporu", icon: Eye },
                  { title: "Konversiyon Hunisi", desc: "Satış hunisi adım adım analizi", icon: Activity },
                  { title: "Haftalık Özet", desc: "Otomatik haftalık performans özeti", icon: Clock },
                ].map((report) => (
                  <button
                    key={report.title}
                    className="flex flex-col items-start gap-3 p-5 rounded-xl border border-[#E2E8F0] bg-white hover:border-[#7C3AED] hover:shadow-[0_4px_12px_rgba(124,58,237,0.10)] transition-all text-left"
                  >
                    <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-[#EDE9FE]">
                      <report.icon className="w-5 h-5 text-[#7C3AED]" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-[#0F172A]">{report.title}</h3>
                      <p className="text-xs text-[#475569] mt-0.5">{report.desc}</p>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

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
