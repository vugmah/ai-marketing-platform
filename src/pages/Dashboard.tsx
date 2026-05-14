import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Wallet,
  ShoppingCart,
  Heart,
  Target,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Download,
  MoreHorizontal,
  AlertTriangle,
  MessageSquare,
  Info,
  Sparkles,
  Sparkle,
  Check,
  ArrowUpRight,
  PlusCircle,
  Share2,
  Palette,
  Brain,
  ChevronDown,
  ChevronRight,
  Settings,
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
  Line,
  ComposedChart,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  mockKPIs,
  mockSalesData,
  mockAdSpend,
  mockAlerts,
  mockAIInsights,
  mockBranchPerformance,
  mockQuickActions,
} from "@/lib/mockApi";
import type { KPIData, AlertData, AIInsight, QuickAction } from "@/lib/mockApi";

// ─── KPI Icon Map ────────────────────────────────────────

const kpiIconMap = {
  Wallet: Wallet,
  ShoppingCart: ShoppingCart,
  Heart: Heart,
  Target: Target,
};

// ─── Alert Styling Maps ──────────────────────────────────

const alertIconMap = {
  critical: AlertTriangle,
  warning: MessageSquare,
  info: Info,
  ai: Sparkles,
};

const alertColorMap = {
  critical: { text: "text-[#DC2626]", bg: "bg-[#FEE2E2]", border: "border-l-[#DC2626]" },
  warning: { text: "text-[#D97706]", bg: "bg-[#FEF3C7]", border: "border-l-[#D97706]" },
  info: { text: "text-[#2563EB]", bg: "bg-[#DBEAFE]", border: "border-l-[#2563EB]" },
  ai: { text: "text-[#7C3AED]", bg: "bg-[#EDE9FE]", border: "border-l-[#7C3AED]" },
};

// ─── Quick Action Icon Map ───────────────────────────────

const qaIconMap: Record<string, React.ElementType> = {
  PlusCircle: PlusCircle,
  Share2: Share2,
  Palette: Palette,
  Brain: Brain,
  MessageSquare: MessageSquare,
};

const qaBranchColors = [
  "bg-[#2563EB]",
  "bg-[#059669]",
  "bg-[#D97706]",
  "bg-[#EA580C]",
  "bg-[#DB2777]",
];

// ─── Time Range Options ──────────────────────────────────

const timeRanges = ["Bugün", "Son 7 Gün", "Son 30 Gün", "Son 90 Gün", "Bu Yıl"];

// ─── Custom Tooltip for Sales Chart ──────────────────────

function SalesTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload) return null;
  return (
    <div className="bg-white rounded-lg border border-[#E2E8F0] shadow-lg p-3">
      <p className="text-sm font-semibold text-[#0F172A] mb-2">{label}</p>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 text-sm">
          <span
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-[#475569]">
            {entry.name === "Gelir" ? "Gelir" : "Sipariş"}:
          </span>
          <span className="font-semibold text-[#0F172A]">
            {entry.name === "Gelir" ? `₼${entry.value.toLocaleString()}` : `${entry.value.toLocaleString()} sipariş`}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Custom Tooltip for Pie Chart ────────────────────────

function PieTooltip({ active, payload }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; payload: { color: string } }>;
}) {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0];
  const total = mockAdSpend.reduce((sum, item) => sum + item.value, 0);
  const percent = ((data.value / total) * 100).toFixed(0);
  return (
    <div className="bg-white rounded-lg border border-[#E2E8F0] shadow-lg p-3">
      <div className="flex items-center gap-2 mb-1">
        <span
          className="w-2.5 h-2.5 rounded-full"
          style={{ backgroundColor: data.payload.color }}
        />
        <span className="text-sm font-semibold text-[#0F172A]">{data.name}</span>
      </div>
      <p className="text-sm text-[#475569]">₼{data.value.toLocaleString()}</p>
      <p className="text-xs text-[#94A3B8]">Toplamın %{percent}'i</p>
    </div>
  );
}

// ─── KPI Card Component ──────────────────────────────────

function KPICard({ data, index }: { data: KPIData; index: number }) {
  const Icon = kpiIconMap[data.icon as keyof typeof kpiIconMap] || Wallet;
  const TrendIcon = data.trend === "up" ? TrendingUp : TrendingDown;
  const trendColor =
    data.trend === "up" ? "text-[#059669] bg-[#D1FAE5]" : "text-[#DC2626] bg-[#FEE2E2]";

  return (
    <Card
      className={cn(
        "cursor-pointer transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5",
        "opacity-0 animate-fade-in"
      )}
      style={{
        animationDelay: `${index * 80}ms`,
        animationFillMode: "forwards",
      }}
    >
      <CardContent className="p-6">
        {/* Top row: icon + label + trend */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div
              className="flex items-center justify-center w-10 h-10 rounded-full"
              style={{ backgroundColor: `${data.accent}1A` }}
            >
              <Icon className="w-5 h-5" style={{ color: data.accent }} />
            </div>
            <span className="text-[13px] font-medium text-[#94A3B8] uppercase tracking-wide">
              {data.title}
            </span>
          </div>
          <div
            className={cn(
              "flex items-center gap-1 text-xs font-semibold rounded-full px-2 py-0.5",
              trendColor
            )}
          >
            <TrendIcon className="w-3 h-3" />
            {data.change}
          </div>
        </div>

        {/* Value */}
        <p className="text-[32px] font-bold text-[#0F172A] leading-tight tracking-tight">
          {data.value}
        </p>

        {/* Period */}
        <p className="text-[13px] text-[#94A3B8] mt-1">{data.period}</p>
      </CardContent>
    </Card>
  );
}

// ─── Main Dashboard Component ────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate();
  const [timeRange, setTimeRange] = useState("Son 30 Gün");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [visibleInsights, setVisibleInsights] = useState(1);

  // Simulate typing effect for AI insight
  const [typedText, setTypedText] = useState("");
  const fullText = mockAIInsights[0]?.description || "";

  useEffect(() => {
    setTypedText("");
    let index = 0;
    const interval = setInterval(() => {
      if (index <= fullText.length) {
        setTypedText(fullText.slice(0, index));
        index++;
      } else {
        clearInterval(interval);
      }
    }, 20);
    return () => clearInterval(interval);
  }, [fullText]);

  // Refresh handler
  const handleRefresh = () => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 800);
  };

  // Ad spend total
  const adSpendTotal = useMemo(
    () => mockAdSpend.reduce((sum, item) => sum + item.value, 0),
    []
  );

  return (
    <div className="space-y-6">
      {/* ═══ Section 1: Page Header ═══════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Dashboard</h1>
          <p className="text-sm text-[#475569] mt-0.5">
            İşletmenizin performansına genel bakış
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Time Range Selector */}
          <div className="relative">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2 h-9 px-3 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors min-w-[140px]"
            >
              <span className="flex-1 text-left">{timeRange}</span>
              <ChevronDown
                className={cn("w-4 h-4 text-[#94A3B8] transition-transform", dropdownOpen && "rotate-180")}
              />
            </button>
            {dropdownOpen && (
              <div className="absolute right-0 top-10 w-[160px] bg-white rounded-lg border border-[#E2E8F0] shadow-lg z-50 overflow-hidden">
                {timeRanges.map((range) => (
                  <button
                    key={range}
                    onClick={() => { setTimeRange(range); setDropdownOpen(false); }}
                    className={cn(
                      "flex items-center w-full px-3 py-2 text-sm hover:bg-[#F8FAFC] transition-colors",
                      timeRange === range && "bg-[#F1F5F9] text-[#2563EB] font-medium"
                    )}
                  >
                    {range}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Refresh */}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            className="h-9 w-9"
          >
            <RefreshCw
              className={cn("w-4 h-4 text-[#475569]", refreshing && "animate-spin")}
            />
          </Button>

          {/* Export */}
          <Button variant="ghost" size="icon" className="h-9 w-9">
            <Download className="w-4 h-4 text-[#475569]" />
          </Button>
        </div>
      </div>

      {/* ═══ Section 2: KPI Cards ═════════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        {mockKPIs.map((kpi, index) => (
          <KPICard key={kpi.id} data={kpi} index={index} />
        ))}
      </div>

      {/* ═══ Section 3: Sales Trend Chart ═════════════════ */}
      <Card
        className="opacity-0 animate-fade-in-up"
        style={{
          animationDelay: "200ms",
          animationFillMode: "forwards",
          animationDuration: "500ms",
        }}
      >
        <CardHeader className="flex flex-row items-start justify-between pb-2">
          <div>
            <CardTitle className="text-base font-semibold text-[#0F172A]">
              30 Günlük Satış Trendi
            </CardTitle>
            <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">
              Günlük gelir ve sipariş hacmi
            </CardDescription>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <MoreHorizontal className="w-4 h-4 text-[#94A3B8]" />
          </Button>
        </CardHeader>
        <CardContent>
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={mockSalesData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563EB" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#E2E8F0"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#94A3B8", fontSize: 12 }}
                  interval={4}
                />
                <YAxis
                  yAxisId="left"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#94A3B8", fontSize: 12 }}
                  tickFormatter={(value: number) => `₼${(value / 1000).toFixed(0)}K`}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#94A3B8", fontSize: 12 }}
                  tickFormatter={(value: number) =>
                    value >= 1000 ? `${(value / 1000).toFixed(0)}K` : String(value)
                  }
                />
                <Tooltip content={<SalesTooltip />} />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="revenue"
                  name="Gelir"
                  stroke="#2563EB"
                  strokeWidth={2}
                  fill="url(#revenueGradient)"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="orders"
                  name="Sipariş"
                  stroke="#EA580C"
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Legend */}
          <div className="flex items-center justify-center gap-6 mt-4">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#2563EB]" />
              <span className="text-xs text-[#475569]">Gelir</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#EA580C]" />
              <span className="text-xs text-[#475569]">Sipariş</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ═══ Section 4: Two-Column (Ad Spend + Alerts) ════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ── Ad Spend Distribution ─────────── */}
        <Card
          className="opacity-0 animate-fade-in-up"
          style={{
            animationDelay: "300ms",
            animationFillMode: "forwards",
            animationDuration: "500ms",
          }}
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold text-[#0F172A]">
              Reklam Harcama Dağılımı
            </CardTitle>
            <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">
              Platform bazlı aylık harcama
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[240px] relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={mockAdSpend}
                    cx="50%"
                    cy="50%"
                    innerRadius="60%"
                    outerRadius="80%"
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                  >
                    {mockAdSpend.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<PieTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              {/* Center label */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-xl font-bold text-[#0F172A]">
                  ₼{adSpendTotal.toLocaleString()}
                </span>
                <span className="text-xs text-[#94A3B8]">Toplam Harcama</span>
              </div>
            </div>

            {/* Custom Legend */}
            <div className="flex items-center justify-center gap-5 mt-4 flex-wrap">
              {mockAdSpend.map((item) => {
                const total = mockAdSpend.reduce((s, i) => s + i.value, 0);
                const pct = ((item.value / total) * 100).toFixed(0);
                return (
                  <div key={item.name} className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-xs text-[#475569]">{item.name}</span>
                    <span className="text-xs font-semibold text-[#0F172A]">%{pct}</span>
                    <span className="text-[11px] text-[#94A3B8]">
                      ₼{item.value.toLocaleString()}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* ── Critical Alerts ──────────────── */}
        <Card
          className="opacity-0 animate-fade-in-right"
          style={{
            animationDelay: "350ms",
            animationFillMode: "forwards",
            animationDuration: "400ms",
          }}
        >
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base font-semibold text-[#0F172A]">
                  Kritik Uyarılar
                </CardTitle>
                <Badge className="bg-[#FEE2E2] text-[#DC2626] hover:bg-[#FEE2E2] text-[11px] h-5 px-1.5">
                  {mockAlerts.length}
                </Badge>
              </div>
              <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">
                İşlem gerektiren durumlar
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-0 max-h-[280px] overflow-y-auto">
              {mockAlerts.map((alert: AlertData, index: number) => {
                const Icon = alertIconMap[alert.type];
                const colors = alertColorMap[alert.type];
                return (
                  <div
                    key={alert.id}
                    className={cn(
                      "flex gap-3 px-3 py-3 border-l-[3px] rounded-r-lg cursor-pointer",
                      "hover:bg-[#F8FAFC] transition-colors",
                      colors.border,
                      "opacity-0 animate-slide-in-right"
                    )}
                    style={{
                      animationDelay: `${350 + index * 100}ms`,
                      animationFillMode: "forwards",
                      animationDuration: "300ms",
                    }}
                  >
                    <div
                      className={cn(
                        "flex items-center justify-center w-8 h-8 rounded-full shrink-0",
                        colors.bg
                      )}
                    >
                      <Icon className={cn("w-4 h-4", colors.text)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-[#0F172A]">{alert.title}</p>
                      <p className="text-xs text-[#475569] mt-0.5 line-clamp-2">
                        {alert.description}
                      </p>
                      <div className="flex items-center justify-between mt-1.5">
                        <span className="text-[11px] text-[#94A3B8]">{alert.meta}</span>
                        <span className="text-[11px] text-[#94A3B8]">{alert.timestamp}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <button
              onClick={() => navigate("/ai-reports")}
              className="mt-3 text-xs font-medium text-[#2563EB] hover:underline flex items-center gap-1"
            >
              Tümünü Gör
              <ChevronRight className="w-3 h-3" />
            </button>
          </CardContent>
        </Card>
      </div>

      {/* ═══ Section 5: AI Insight Card ═══════════════════ */}
      <Card
        className={cn(
          "border-l-[3px] border-l-[#7C3AED] bg-[#F5F3FF] opacity-0 animate-fade-in-up",
          "hover:bg-[#EDE9FE] transition-colors"
        )}
        style={{
          animationDelay: "400ms",
          animationFillMode: "forwards",
          animationDuration: "500ms",
        }}
      >
        <CardContent className="p-6">
          {/* Header */}
          <div className="flex items-center gap-2 mb-3">
            <div className="relative">
              <Sparkle className="w-5 h-5 text-[#7C3AED]" />
              <div className="absolute inset-0 w-5 h-5 bg-[#7C3AED] rounded-full blur-md opacity-30 animate-pulse" />
            </div>
            <h3 className="text-base font-semibold text-[#0F172A]">AI Öngörüleri</h3>
            <Badge className="bg-[#EDE9FE] text-[#7C3AED] hover:bg-[#EDE9FE] text-[11px] h-5 px-2 font-semibold">
              NEW
            </Badge>
          </div>

          {/* Insight Content */}
          {mockAIInsights.slice(0, visibleInsights).map((insight: AIInsight) => (
            <div key={insight.id} className="mb-4">
              <p className="text-sm font-semibold text-[#0F172A] mb-1">{insight.title}</p>
              <p className="text-sm text-[#475569] leading-relaxed">
                {insight.id === mockAIInsights[0].id ? typedText : insight.description}
                {insight.id === mockAIInsights[0].id && (
                  <span className="animate-pulse">|</span>
                )}
              </p>
              <div className="flex items-center gap-2 mt-2">
                <Badge
                  variant="outline"
                  className="text-[11px] h-5 border-[#7C3AED] text-[#7C3AED]"
                >
                  <Check className="w-3 h-3 mr-1" />
                  %{insight.confidence} güven
                </Badge>
              </div>
            </div>
          ))}

          {/* Actions */}
          <div className="flex items-center justify-between mt-4">
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-8"
                onClick={() => {}}
              >
                <Check className="w-4 h-4 mr-1" />
                Uygula
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-[#475569] hover:text-[#0F172A]"
                onClick={() => navigate("/ai-reports")}
              >
                Detaylar
                <ArrowUpRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
            <span className="text-xs text-[#94A3B8]">
              {mockAIInsights[0]?.timestamp}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* ═══ Section 6: Quick Actions + Branch Perf ═══════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ── Quick Actions ────────────────── */}
        <Card
          className="opacity-0 animate-fade-in-up"
          style={{
            animationDelay: "450ms",
            animationFillMode: "forwards",
            animationDuration: "500ms",
          }}
        >
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-[#0F172A]">
              Hızlı İşlemler
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {mockQuickActions.map((action: QuickAction, index: number) => {
                const Icon = qaIconMap[action.icon] || PlusCircle;
                return (
                  <button
                    key={action.id}
                    onClick={() => navigate(action.route)}
                    className={cn(
                      "flex items-center gap-3 w-full h-12 px-3 rounded-lg text-sm text-[#0F172A]",
                      "hover:bg-[#F8FAFC] hover:border-l-[3px] hover:border-l-[#DBEAFE] transition-all",
                      "opacity-0 animate-fade-in"
                    )}
                    style={{
                      animationDelay: `${450 + index * 50}ms`,
                      animationFillMode: "forwards",
                      animationDuration: "300ms",
                    }}
                  >
                    <Icon className="w-5 h-5 text-[#2563EB] shrink-0" />
                    {action.label}
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => navigate("/settings")}
              className="mt-3 text-xs font-medium text-[#2563EB] hover:underline flex items-center gap-1"
            >
              Tümünü Gör
              <ChevronRight className="w-3 h-3" />
            </button>
          </CardContent>
        </Card>

        {/* ── Branch Performance ───────────── */}
        <Card
          className="opacity-0 animate-fade-in-up"
          style={{
            animationDelay: "450ms",
            animationFillMode: "forwards",
            animationDuration: "500ms",
          }}
        >
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-[#0F172A]">
              Şube Performansı
            </CardTitle>
            <CardDescription className="text-[13px] text-[#94A3B8] mt-0.5">
              Aylık gelire göre sıralama
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {mockBranchPerformance.map((branch, index) => (
                <div
                  key={branch.id}
                  className="group cursor-pointer"
                  onClick={() => navigate("/branches")}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div>
                      <span className="text-sm font-semibold text-[#0F172A]">
                        {branch.name}
                      </span>
                      <span className="text-xs text-[#94A3B8] ml-1.5">
                        ({branch.city})
                      </span>
                    </div>
                    <span className="text-sm font-bold text-[#0F172A]">
                      ₼{branch.revenue.toLocaleString()}
                    </span>
                  </div>
                  {/* Progress bar */}
                  <div className="h-2 bg-[#F1F5F9] rounded-full overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all duration-700 ease-out",
                        qaBranchColors[index % qaBranchColors.length]
                      )}
                      style={{
                        width: `${branch.percentage}%`,
                        transitionDelay: `${500 + index * 100}ms`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={() => navigate("/branches")}
              className="mt-4 text-xs font-medium text-[#2563EB] hover:underline flex items-center gap-1"
            >
              Tüm Şubeler
              <ChevronRight className="w-3 h-3" />
            </button>
          </CardContent>
        </Card>
      </div>

      {/* ═══ CSS Animations ═══════════════════════════════ */}
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
        .animate-spin {
          animation: spin 0.8s linear;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
