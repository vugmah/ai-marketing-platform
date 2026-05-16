import { useState, useEffect } from "react";
import {
  Brain,
  TrendingUp,
  Target,
  Sparkles,
  Check,
  X,
  ArrowUpRight,
  BarChart3,
  Sun,
  Users,
  CloudRain,
  Store,
  Clock,
  ChevronRight,
  FileText,
  Download,
  Zap,
  Percent,
  Star,
  AlertTriangle,
  Lightbulb,
  RefreshCw,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { DashboardSkeleton } from "@/components/LoadingSkeleton";

// ─── Types ───────────────────────────────────────────────

interface TrendCard {
  id: string;
  title: string;
  value: string;
  description: string;
  confidence: number;
  icon: string;
  color: string;
  bg: string;
}

interface AIRecommendation {
  id: string;
  title: string;
  description: string;
  potentialRevenue: string;
  confidence: number;
  icon: string;
}

interface ReportHistoryItem {
  id: string;
  date: string;
  type: string;
  typeColor: string;
  summary: string;
  confidence: number;
  status: string;
}

// ─── Mock Data ───────────────────────────────────────────

const revenueForecastData = [
  { day: "1 Haz", actual: 18500, forecast: null, lower: null, upper: null },
  { day: "5 Haz", actual: 21200, forecast: null, lower: null, upper: null },
  { day: "10 Haz", actual: 24100, forecast: null, lower: null, upper: null },
  { day: "15 Haz", actual: 24800, forecast: null, lower: null, upper: null },
  { day: "20 Haz", actual: 24200, forecast: 25000, lower: 23500, upper: 26500 },
  { day: "21 Haz", actual: 26800, forecast: 26200, lower: 24800, upper: 27800 },
  { day: "22 Haz", actual: 28900, forecast: 27500, lower: 26000, upper: 29200 },
  { day: "23 Haz", actual: 27200, forecast: 26800, lower: 25200, upper: 28500 },
  { day: "24 Haz", actual: null, forecast: 28000, lower: 26200, upper: 29800 },
  { day: "25 Haz", actual: null, forecast: 29500, lower: 27500, upper: 31800 },
  { day: "26 Haz", actual: null, forecast: 31000, lower: 28800, upper: 33400 },
  { day: "27 Haz", actual: null, forecast: 32500, lower: 30000, upper: 35200 },
  { day: "28 Haz", actual: null, forecast: 34000, lower: 31200, upper: 37000 },
  { day: "29 Haz", actual: null, forecast: 35500, lower: 32500, upper: 38800 },
  { day: "30 Haz", actual: null, forecast: 37000, lower: 33800, upper: 40500 },
];

const trendCards: TrendCard[] = [
  { id: "t1", title: "Yaz Sezonu Etkisi", value: "+35%", description: "Sıcaklık artışı ile birlikte dış mekan kafe talebi artıyor. Buna göre stok ve personel planlaması yapın.", confidence: 94, icon: "sun", color: "text-[#059669]", bg: "bg-[#D1FAE5]" },
  { id: "t2", title: "Rakip Aktivitesi", value: "Yüksek", description: "Bölgedeki 3 yeni rakip işletme agresif kampanya yürütüyor. Fiyat stratejinizi gözden geçirin.", confidence: 88, icon: "users", color: "text-[#DC2626]", bg: "bg-[#FEE2E2]" },
  { id: "t3", title: "Hava Durumu Etkisi", value: "-8%", description: "Önümüzdeki hafta yağışlı hava nedeniyle ev teslimat siparişlerinde %12 artış bekleniyor.", confidence: 82, icon: "cloud", color: "text-[#D97706]", bg: "bg-[#FEF3C7]" },
  { id: "t4", title: "Yeni AVM Fırsatı", value: "Fırsat", description: "Yakınınızdaki yeni AVM açılışından faydalanmak için coğrafi hedefleme kampanyası başlatın.", confidence: 76, icon: "store", color: "text-[#2563EB]", bg: "bg-[#DBEAFE]" },
];

const aiRecommendations: AIRecommendation[] = [
  { id: "r1", title: "Akşam Story Serisi", description: "Instagram ve Facebook'ta 18:00-20:00 arası günlük story paylaşımı yapın. Video formatında menü tanıtımları en yüksek etkileşimi sağlar.", potentialRevenue: "+₺3.200/ay", confidence: 92, icon: "zap" },
  { id: "r2", title: "Google Ads Optimizasyon", description: "Arama kampanyalarınızda uzun kuyruklu anahtar kelimelere ağırlık verin. 'En iyi kafe Bakü' gibi kelimeler dönüşüm oranını %25 artırır.", potentialRevenue: "+₺5.800/ay", confidence: 87, icon: "target" },
  { id: "r3", title: "Loyalty Program", description: "5. ziyarette 1 ücretsiz kahve kampanyası başlatın. Müşteri sadakati ortalama %40 artış sağlar.", potentialRevenue: "+₺4.100/ay", confidence: 79, icon: "star" },
];

const reportHistory: ReportHistoryItem[] = [
  { id: "rh1", date: "24 Haz 2024", type: "Gelir Tahmini", typeColor: "bg-[#EDE9FE] text-[#7C3AED]", summary: "Temmuz ayı gelir tahmini: ₺385.000 (+%12)", confidence: 91, status: "Tamamlandı" },
  { id: "rh2", date: "22 Haz 2024", type: "Rakip Analizi", typeColor: "bg-[#FEE2E2] text-[#DC2626]", summary: "3 yeni rakip tespit edildi, fiyat karşılaştırması yapıldı", confidence: 85, status: "Tamamlandı" },
  { id: "rh3", date: "20 Haz 2024", type: "Optimizasyon", typeColor: "bg-[#D1FAE5] text-[#059669]", summary: "Reklam bütçesi optimizasyonu, ROI %18 artış", confidence: 93, status: "Uygulandı" },
  { id: "rh4", date: "18 Haz 2024", type: "Trend Raporu", typeColor: "bg-[#FEF3C7] text-[#D97706]", summary: "Yaz sezonu trend analizi ve öneriler", confidence: 88, status: "Tamamlandı" },
  { id: "rh5", date: "15 Haz 2024", type: "Gelir Tahmini", typeColor: "bg-[#EDE9FE] text-[#7C3AED]", summary: "Haziran ayı gelir tahmini: ₺340.000 (+%8)", confidence: 89, status: "Uygulandı" },
];

// ─── Icon Maps ───────────────────────────────────────────

function TrendIcon({ icon, className }: { icon: string; className?: string }) {
  switch (icon) {
    case "sun": return <Sun className={className} />;
    case "users": return <Users className={className} />;
    case "cloud": return <CloudRain className={className} />;
    case "store": return <Store className={className} />;
    case "zap": return <Zap className={className} />;
    case "target": return <Target className={className} />;
    case "star": return <Star className={className} />;
    default: return <BarChart3 className={className} />;
  }
}

// ─── Custom Tooltip ──────────────────────────────────────

function ForecastTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string; dataKey: string }>; label?: string }) {
  if (!active || !payload) return null;
  return (
    <div className="bg-white rounded-lg border border-[#E2E8F0] shadow-lg p-3">
      <p className="text-sm font-semibold text-[#0F172A] mb-2">{label}</p>
      {payload.map((entry, index) => {
        if (entry.value == null) return null;
        let labelText = entry.dataKey === "actual" ? "Gerçekleşen" : entry.dataKey === "forecast" ? "Tahmin" : entry.dataKey === "lower" ? "Alt Sınır" : "Üst Sınır";
        return (
          <div key={index} className="flex items-center gap-2 text-sm">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-[#475569]">{labelText}:</span>
            <span className="font-semibold text-[#0F172A]">₺{entry.value.toLocaleString()}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─── KPI Card Component (Mor Gradient) ───────────────────

interface PurpleKPICardProps {
  title: string;
  value: string;
  change: string;
  icon: React.ElementType;
  delay: number;
}

function PurpleKPICard({ title, value, change, icon: Icon, delay }: PurpleKPICardProps) {
  return (
    <Card
      className="bg-[#7C3AED] text-white border-none opacity-0 animate-fade-in transition-all duration-200 hover:shadow-[0_4px_16px_rgba(124,58,237,0.35)] hover:-translate-y-0.5"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "forwards" }}
    >
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-white/15">
              <Icon className="w-5 h-5 text-white" />
            </div>
            <span className="text-[13px] font-medium text-white/70 uppercase tracking-wide">{title}</span>
          </div>
        </div>
        <p className="text-[32px] font-bold text-white leading-tight tracking-tight">{value}</p>
        <p className="text-[13px] text-white/60 mt-1">{change}</p>
      </CardContent>
    </Card>
  );
}

// ─── Main Component ──────────────────────────────────────

export default function AIReportsPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [appliedRecs, setAppliedRecs] = useState<Set<string>>(new Set());
  const [rejectedRecs, setRejectedRecs] = useState<Set<string>>(new Set());

  // Load AI reports data from API
  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([
        api.aiReports.overview(),
        api.aiReports.trends(),
        api.aiReports.recommendations(),
        api.aiReports.forecast(),
        api.aiReports.history(),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI raporları yüklenemedi");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }

  function handleApply(recId: string) {
    setAppliedRecs((prev) => new Set(prev).add(recId));
  }

  function handleReject(recId: string) {
    setRejectedRecs((prev) => new Set(prev).add(recId));
  }

  if (loading) {
    return <DashboardSkeleton />;
  }

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

  return (
    <div className="space-y-6">
      {/* ═══ Page Header ════════════════════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">AI Raporları</h1>
          <p className="text-sm text-[#475569] mt-0.5">Yapay zeka destekli öngörüler ve öneriler</p>
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
          <Button className="bg-[#7C3AED] hover:bg-[#6D28D9] text-white h-10 px-4 gap-2">
            <Sparkles className="w-4 h-4" />
            Yeni AI Raporu
          </Button>
        </div>
      </div>

      {/* ═══ Purple KPI Cards ═══════════════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        <PurpleKPICard title="AI Öngörü" value="23" change="aktif öngörü mevcut" icon={Brain} delay={0} />
        <PurpleKPICard title="Tahmini Gelir Artışı" value="+18%" change="gelecek 30 gün" icon={TrendingUp} delay={80} />
        <PurpleKPICard title="Tahmini ROAS" value="3.2x" change="tüm platformlar ortalama" icon={Target} delay={160} />
        <PurpleKPICard title="Aktif Öneri" value="5" change="uygulanmayı bekliyor" icon={Lightbulb} delay={240} />
      </div>

      {/* ═══ Revenue Forecast Chart ═════════════════════════ */}
      <Card
        className="opacity-0 animate-fade-in-up"
        style={{ animationDelay: "200ms", animationFillMode: "forwards", animationDuration: "500ms" }}
      >
        <CardHeader className="flex flex-row items-start justify-between pb-2">
          <div>
            <CardTitle className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-[#475569]" />
              Gelir Tahmini
            </CardTitle>
            <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">
              AI tabanlı 15 günlük gelir projeksiyonu
            </CardDescription>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#2563EB]" />
              <span className="text-xs text-[#475569]">Gerçekleşen</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#7C3AED]" />
              <span className="text-xs text-[#475569]">Tahmin</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#7C3AED] opacity-30" />
              <span className="text-xs text-[#475569]">Güven Aralığı</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={revenueForecastData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="confidenceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#7C3AED" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} interval={2} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "#94A3B8", fontSize: 12 }} tickFormatter={(v: number) => `₺${(v / 1000).toFixed(0)}K`} />
                <Tooltip content={<ForecastTooltip />} />
                <Area type="monotone" dataKey="lower" stroke="none" fill="#7C3AED" fillOpacity={0.08} />
                <Area type="monotone" dataKey="upper" stroke="none" fill="url(#confidenceGradient)" />
                <Area type="monotone" dataKey="actual" stroke="#2563EB" strokeWidth={2.5} fill="none" dot={{ r: 4, fill: "#2563EB" }} activeDot={{ r: 6 }} />
                <Area type="monotone" dataKey="forecast" stroke="#7C3AED" strokeWidth={2.5} strokeDasharray="8 4" fill="none" dot={{ r: 4, fill: "#7C3AED" }} activeDot={{ r: 6 }} />
                <ReferenceLine x="24 Haz" stroke="#DC2626" strokeDasharray="4 4" label={{ value: "Bugün", fill: "#DC2626", fontSize: 11, position: "top" }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* ═══ Trend Analysis Cards ══════════════════════════ */}
      <div>
        <h2 className="text-lg font-semibold text-[#0F172A] mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-[#475569]" />
          Trend Analizi
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
          {trendCards.map((trend, index) => {
            const IconComponent = ({ className }: { className?: string }) => <TrendIcon icon={trend.icon} className={className} />;
            return (
              <Card
                key={trend.id}
                className="opacity-0 animate-fade-in-up transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5"
                style={{ animationDelay: `${300 + index * 80}ms`, animationFillMode: "forwards", animationDuration: "500ms" }}
              >
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className={cn("flex items-center justify-center w-10 h-10 rounded-full", trend.bg)}>
                      <IconComponent className={cn("w-5 h-5", trend.color)} />
                    </div>
                    <div className="flex items-center gap-1">
                      <Percent className="w-3 h-3 text-[#94A3B8]" />
                      <span className="text-[11px] font-semibold text-[#94A3B8]">%{trend.confidence} güven</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <p className="text-sm font-semibold text-[#0F172A]">{trend.title}</p>
                  </div>
                  <p className={cn("text-2xl font-bold mb-2", trend.color)}>{trend.value}</p>
                  <p className="text-xs text-[#475569] leading-relaxed">{trend.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* ═══ AI Recommendations ════════════════════════════ */}
      <div>
        <h2 className="text-lg font-semibold text-[#0F172A] mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-[#7C3AED]" />
          Kişiselleştirilmiş Öneriler
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {aiRecommendations.map((rec, index) => {
            const IconComponent = ({ className }: { className?: string }) => <TrendIcon icon={rec.icon} className={className} />;
            return (
              <Card
                key={rec.id}
                className="opacity-0 animate-fade-in-up transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5"
                style={{ animationDelay: `${400 + index * 100}ms`, animationFillMode: "forwards", animationDuration: "500ms" }}
              >
                <CardContent className="p-5">
                  <div className="flex items-start gap-3 mb-3">
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-[#EDE9FE] shrink-0">
                      <IconComponent className="w-5 h-5 text-[#7C3AED]" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-[#0F172A]">{rec.title}</h3>
                      <p className="text-xs text-[#475569] mt-1 leading-relaxed">{rec.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-[#F1F5F9]">
                    <div>
                      <p className="text-xs text-[#94A3B8]">Potansiyel Gelir</p>
                      <p className="text-sm font-bold text-[#059669]">{rec.potentialRevenue}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-[#94A3B8]">Güven Skoru</p>
                      <p className="text-sm font-semibold text-[#0F172A]">%{rec.confidence}</p>
                    </div>
                  </div>
                  {!appliedRecs.has(rec.id) && !rejectedRecs.has(rec.id) ? (
                    <div className="flex gap-2 mt-3">
                      <Button size="sm" className="flex-1 bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-8" onClick={() => handleApply(rec.id)}>
                        <Check className="w-4 h-4 mr-1" />
                        Uygula
                      </Button>
                      <Button size="sm" variant="outline" className="flex-1 h-8 border-[#FEE2E2] text-[#DC2626] hover:bg-[#FEE2E2] hover:text-[#DC2626]" onClick={() => handleReject(rec.id)}>
                        <X className="w-4 h-4 mr-1" />
                        Reddet
                      </Button>
                    </div>
                  ) : appliedRecs.has(rec.id) ? (
                    <Badge className="w-full mt-3 justify-center h-8 bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5]">
                      <Check className="w-4 h-4 mr-1" />
                      Uygulandı
                    </Badge>
                  ) : (
                    <Badge className="w-full mt-3 justify-center h-8 bg-[#FEE2E2] text-[#DC2626] hover:bg-[#FEE2E2]">
                      <X className="w-4 h-4 mr-1" />
                      Reddedildi
                    </Badge>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* ═══ Report History ════════════════════════════════ */}
      <Card
        className="opacity-0 animate-fade-in-up"
        style={{ animationDelay: "500ms", animationFillMode: "forwards", animationDuration: "500ms" }}
      >
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
              <FileText className="w-5 h-5 text-[#475569]" />
              Rapor Geçmişi
            </CardTitle>
            <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">Oluşturulan tüm AI raporları</CardDescription>
          </div>
          <Button variant="outline" size="sm" className="h-8 gap-2">
            <Download className="w-3.5 h-3.5" />
            Dışa Aktar
          </Button>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0]">
                  <th className="text-left font-semibold text-[#475569] px-3 py-3">Tarih</th>
                  <th className="text-left font-semibold text-[#475569] px-3 py-3">Tür</th>
                  <th className="text-left font-semibold text-[#475569] px-3 py-3">Özet</th>
                  <th className="text-center font-semibold text-[#475569] px-3 py-3">Güven</th>
                  <th className="text-center font-semibold text-[#475569] px-3 py-3">Durum</th>
                  <th className="text-center font-semibold text-[#475569] px-3 py-3">Eylem</th>
                </tr>
              </thead>
              <tbody>
                {reportHistory.map((report) => (
                  <tr key={report.id} className="border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors">
                    <td className="px-3 py-3 text-[#475569]">{report.date}</td>
                    <td className="px-3 py-3">
                      <Badge className={cn("text-[11px] font-semibold", report.typeColor)}>
                        {report.type}
                      </Badge>
                    </td>
                    <td className="px-3 py-3 text-[#0F172A]">{report.summary}</td>
                    <td className="text-center px-3 py-3">
                      <span className="text-sm font-semibold text-[#0F172A]">%{report.confidence}</span>
                    </td>
                    <td className="text-center px-3 py-3">
                      <Badge
                        className={cn(
                          "text-[11px] font-semibold",
                          report.status === "Tamamlandı" && "bg-[#DBEAFE] text-[#2563EB] hover:bg-[#DBEAFE]",
                          report.status === "Uygulandı" && "bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5]",
                          report.status === "Beklemede" && "bg-[#FEF3C7] text-[#D97706] hover:bg-[#FEF3C7]",
                        )}
                      >
                        {report.status}
                      </Badge>
                    </td>
                    <td className="text-center px-3 py-3">
                      <Button variant="ghost" size="sm" className="h-7 text-[#2563EB] text-xs hover:underline">
                        Görüntüle
                        <ArrowUpRight className="w-3 h-3 ml-1" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

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
