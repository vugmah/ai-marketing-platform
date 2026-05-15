/**
 * Mock API Data - AI Marketing Automation Platform
 * All data is realistic mock data for the dashboard
 */

// ─── Types ───────────────────────────────────────────────

export interface KPIData {
  id: string;
  title: string;
  value: string;
  change: string;
  trend: "up" | "down";
  period: string;
  icon: string;
  accent: string;
}

export interface SalesDataPoint {
  date: string;
  revenue: number;
  orders: number;
}

export interface AdSpendDataPoint {
  name: string;
  value: number;
  color: string;
}

export interface AlertData {
  id: string;
  type: "critical" | "warning" | "info" | "ai";
  title: string;
  description: string;
  meta: string;
  timestamp: string;
}

export interface AIInsight {
  id: string;
  title: string;
  description: string;
  confidence: number;
  type: "content" | "ads" | "budget" | "general";
  timestamp: string;
}

export interface BranchData {
  id: string;
  name: string;
  city: string;
  type: string;
  revenue: number;
  orders: number;
  rating: number;
  status: "active" | "inactive" | "pending";
  percentage: number;
}

export interface UserData {
  name: string;
  email: string;
  role: string;
  company: string;
  avatar: string | null;
}

// ─── KPI Data ────────────────────────────────────────────

export const mockKPIs: KPIData[] = [
  {
    id: "kpi-revenue",
    title: "Toplam Gelir",
    value: "₼ 124,580",
    change: "+15.3%",
    trend: "up",
    period: "Geçen aya göre",
    icon: "Wallet",
    accent: "#0D9488",
  },
  {
    id: "kpi-orders",
    title: "Toplam Sipariş",
    value: "3,842",
    change: "+8.7%",
    trend: "up",
    period: "Geçen aya göre",
    icon: "ShoppingCart",
    accent: "#EA580C",
  },
  {
    id: "kpi-engagement",
    title: "Etkileşim Oranı",
    value: "4.62%",
    change: "-1.2%",
    trend: "down",
    period: "Geçen aya göre",
    icon: "Heart",
    accent: "#DB2777",
  },
  {
    id: "kpi-roas",
    title: "ROAS (Reklam Getirisi)",
    value: "3.8x",
    change: "+0.4x",
    trend: "up",
    period: "Geçen aya göre",
    icon: "Target",
    accent: "#7C3AED",
  },
];

// ─── 30-Day Sales Data ───────────────────────────────────

export const mockSalesData: SalesDataPoint[] = [
  { date: "1 Haz", revenue: 18500, orders: 1240 },
  { date: "2 Haz", revenue: 22100, orders: 1480 },
  { date: "3 Haz", revenue: 19800, orders: 1320 },
  { date: "4 Haz", revenue: 24500, orders: 1630 },
  { date: "5 Haz", revenue: 21200, orders: 1410 },
  { date: "6 Haz", revenue: 19800, orders: 1320 },
  { date: "7 Haz", revenue: 18600, orders: 1250 },
  { date: "8 Haz", revenue: 23200, orders: 1540 },
  { date: "9 Haz", revenue: 25600, orders: 1720 },
  { date: "10 Haz", revenue: 24100, orders: 1600 },
  { date: "11 Haz", revenue: 21800, orders: 1480 },
  { date: "12 Haz", revenue: 20500, orders: 1390 },
  { date: "13 Haz", revenue: 19800, orders: 1320 },
  { date: "14 Haz", revenue: 22400, orders: 1520 },
  { date: "15 Haz", revenue: 24800, orders: 1680 },
  { date: "16 Haz", revenue: 26200, orders: 1750 },
  { date: "17 Haz", revenue: 23500, orders: 1580 },
  { date: "18 Haz", revenue: 22100, orders: 1480 },
  { date: "19 Haz", revenue: 20800, orders: 1400 },
  { date: "20 Haz", revenue: 24200, orders: 1620 },
  { date: "21 Haz", revenue: 26800, orders: 1780 },
  { date: "22 Haz", revenue: 28900, orders: 1920 },
  { date: "23 Haz", revenue: 27200, orders: 1820 },
  { date: "24 Haz", revenue: 25600, orders: 1720 },
  { date: "25 Haz", revenue: 23800, orders: 1580 },
  { date: "26 Haz", revenue: 25100, orders: 1680 },
  { date: "27 Haz", revenue: 26500, orders: 1760 },
  { date: "28 Haz", revenue: 27800, orders: 1840 },
  { date: "29 Haz", revenue: 26200, orders: 1740 },
  { date: "30 Haz", revenue: 28600, orders: 1890 },
];

// ─── Ad Spend Distribution ───────────────────────────────

export const mockAdSpend: AdSpendDataPoint[] = [
  { name: "Google Ads", value: 4500, color: "#2563EB" },
  { name: "Meta Ads", value: 3500, color: "#059669" },
  { name: "TikTok Ads", value: 2000, color: "#D97706" },
];

// ─── Alerts ──────────────────────────────────────────────

export const mockAlerts: AlertData[] = [
  {
    id: "alert-1",
    type: "critical",
    title: "Düşük ROAS Tespit Edildi",
    description:
      "Google Ads kampanyanızın ROAS değeri 1.2x'e düştü. Acil optimizasyon önerilir.",
    meta: "Şube 3 · Google Ads",
    timestamp: "5 dk önce",
  },
  {
    id: "alert-2",
    type: "warning",
    title: "Negatif Yorum Bildirimi",
    description:
      "Şube 1 Google Business profiline 1 yıldızlı yorum eklendi. Yanıt bekleniyor.",
    meta: "Şube 1 · Google Maps",
    timestamp: "15 dk önce",
  },
  {
    id: "alert-3",
    type: "info",
    title: "Kampanya Durduruldu",
    description:
      "Meta Ads 'Yaz Kampanyası' bütçe limitine ulaştığı için otomatik durduruldu.",
    meta: "Şube 2 · Meta Ads",
    timestamp: "1 saat önce",
  },
  {
    id: "alert-4",
    type: "ai",
    title: "AI: Bütçe Optimizasyonu",
    description:
      "TikTok Ads bütçenizi %30 artırmanız eklenimde %18 daha fazla dönüşüm sağlayabilir.",
    meta: "AI Öngörü · Tüm Şubeler",
    timestamp: "30 dk önce",
  },
];

// ─── AI Insights ─────────────────────────────────────────

export const mockAIInsights: AIInsight[] = [
  {
    id: "ai-1",
    title: "İçerik Optimizasyonu",
    description:
      "Hafta sonu paylaşımlarınızda video formatına geçiş etkileşimi %35 artırabilir. Video içeriklerinizin süresini 15-30 saniye arasında tutmanız önerilir.",
    confidence: 92,
    type: "content",
    timestamp: "2 dk önce",
  },
  {
    id: "ai-2",
    title: "Reklam Bütçesi",
    description:
      "Google Ads bütçenizin %15'ini TikTok'a kaydırmayı düşünün. Genç kitlede marka bilinirliği %22 artabilir.",
    confidence: 88,
    type: "ads",
    timestamp: "15 dk önce",
  },
];

// ─── Branch Performance ──────────────────────────────────

export const mockBranches: BranchData[] = [
  {
    id: "branch-1",
    name: "Nizami Şubesi",
    city: "Bakü",
    type: "Restoran",
    revenue: 18500,
    orders: 420,
    rating: 4.2,
    status: "active",
    percentage: 85,
  },
  {
    id: "branch-2",
    name: "Gənclik Şubesi",
    city: "Bakü",
    type: "Restoran",
    revenue: 15200,
    orders: 380,
    rating: 4.0,
    status: "active",
    percentage: 62,
  },
  {
    id: "branch-3",
    name: "28 May Şubesi",
    city: "Bakü",
    type: "Kafe",
    revenue: 11200,
    orders: 320,
    rating: 4.5,
    status: "active",
    percentage: 48,
  },
];

// ─── Branch Performance for bar chart ────────────────────

export const mockBranchPerformance: BranchData[] = [
  {
    id: "bp-1",
    name: "Şube 1",
    city: "Bakı",
    type: "Restoran",
    revenue: 12450,
    orders: 420,
    rating: 4.2,
    status: "active",
    percentage: 85,
  },
  {
    id: "bp-2",
    name: "Şube 2",
    city: "Sumqayıt",
    type: "Restoran",
    revenue: 8230,
    orders: 380,
    rating: 4.0,
    status: "active",
    percentage: 62,
  },
  {
    id: "bp-3",
    name: "Şube 3",
    city: "Gəncə",
    type: "Kafe",
    revenue: 6180,
    orders: 320,
    rating: 4.5,
    status: "active",
    percentage: 48,
  },
  {
    id: "bp-4",
    name: "Şube 4",
    city: "Mingəçevir",
    type: "Restoran",
    revenue: 4950,
    orders: 260,
    rating: 4.1,
    status: "active",
    percentage: 35,
  },
  {
    id: "bp-5",
    name: "Şube 5",
    city: "Şəki",
    type: "Kafe",
    revenue: 3720,
    orders: 180,
    rating: 4.3,
    status: "active",
    percentage: 25,
  },
];

// ─── User Data ───────────────────────────────────────────

export const mockUser: UserData = {
  name: "Vüqar Məmmədov",
  email: "vugmah@gmail.com",
  role: "company_admin",
  company: "FoodFlow Azerbaijan",
  avatar: null,
};

// ─── Quick Actions ───────────────────────────────────────

export interface QuickAction {
  id: string;
  label: string;
  icon: string;
  route: string;
  color: string;
}

export const mockQuickActions: QuickAction[] = [
  {
    id: "qa-1",
    label: "Yeni Kampanya Oluştur",
    icon: "PlusCircle",
    route: "/ads",
    color: "#2563EB",
  },
  {
    id: "qa-2",
    label: "Sosyal Medya Gönderisi Planla",
    icon: "Share2",
    route: "/social-media",
    color: "#2563EB",
  },
  {
    id: "qa-3",
    label: "Yaratıcı İçerik Üret",
    icon: "Palette",
    route: "/creative-studio",
    color: "#2563EB",
  },
  {
    id: "qa-4",
    label: "AI Rapor Oluştur",
    icon: "Brain",
    route: "/ai-reports",
    color: "#2563EB",
  },
  {
    id: "qa-5",
    label: "Gelen Mesajları Görüntüle",
    icon: "MessageSquare",
    route: "/chat-inbox",
    color: "#2563EB",
  },
];

// ─── Notification Count ──────────────────────────────────

export const mockNotificationCount = 4;
