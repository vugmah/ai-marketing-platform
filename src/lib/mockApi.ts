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

// ═══════════════════════════════════════════════════════════════════════════════
// EXPANDED MOCK DATA — consumed by api.ts
// ═══════════════════════════════════════════════════════════════════════════════

export const mockAuthUser = {
  id: "user-1",
  name: "Vüqar Məmmədov",
  email: "vugmah@gmail.com",
  role: "company_admin",
  company: "FoodFlow Azerbaijan",
  avatar: null,
};

export const mockBranchList = [
  { id: "all", name: "Tüm Şubeler", city: "Tüm Şehirler", type: "all", status: "active" as const },
  { id: "branch-1", name: "Nizami Şubesi", city: "Bakü", type: "Restoran", status: "active" as const },
  { id: "branch-2", name: "Gənclik Şubesi", city: "Bakü", type: "Restoran", status: "active" as const },
  { id: "branch-3", name: "28 May Şubesi", city: "Bakü", type: "Kafe", status: "active" as const },
  { id: "branch-4", name: "Sumqayıt Şubesi", city: "Sumqayıt", type: "Restoran", status: "active" as const },
  { id: "branch-5", name: "Gəncə Şubesi", city: "Gəncə", type: "Kafe", status: "inactive" as const },
];

export const mockStats = {
  revenue_this_month: 124580,
  revenue_last_month: 108040,
  active_campaigns: 12,
  total_campaigns: 24,
  engagement_rate: 4.62,
  roas: 3.8,
  total_orders: 3842,
  new_customers: 186,
  returning_customers: 342,
  avg_order_value: 32.40,
};

export const mockChartData = {
  labels: ["1 Haz", "2 Haz", "3 Haz", "4 Haz", "5 Haz", "6 Haz", "7 Haz", "8 Haz", "9 Haz", "10 Haz", "11 Haz", "12 Haz", "13 Haz", "14 Haz", "15 Haz", "16 Haz", "17 Haz", "18 Haz", "19 Haz", "20 Haz", "21 Haz", "22 Haz", "23 Haz", "24 Haz", "25 Haz", "26 Haz", "27 Haz", "28 Haz", "29 Haz", "30 Haz"],
  revenue: [18500, 22100, 19800, 24500, 21200, 19800, 18600, 23200, 25600, 24100, 21800, 20500, 19800, 22400, 24800, 26200, 23500, 22100, 20800, 24200, 26800, 28900, 27200, 25600, 23800, 25100, 26500, 27800, 26200, 28600],
  orders: [1240, 1480, 1320, 1630, 1410, 1320, 1250, 1540, 1720, 1600, 1480, 1390, 1320, 1520, 1680, 1750, 1580, 1480, 1400, 1620, 1780, 1920, 1820, 1720, 1580, 1680, 1760, 1840, 1740, 1890],
  visitors: [3200, 3800, 3500, 4100, 3700, 3500, 3300, 4000, 4300, 4100, 3800, 3600, 3500, 3900, 4200, 4500, 4000, 3800, 3600, 4200, 4600, 4900, 4700, 4400, 4100, 4300, 4500, 4800, 4600, 5000],
};

export const mockRecentOrders = [
  { id: "ord-1", customer: "Əhməd Məmmədov", amount: 125.50, status: "completed", branch: "Nizami Şubesi", date: "2 dk önce" },
  { id: "ord-2", customer: "Leyla Əliyeva", amount: 89.00, status: "processing", branch: "Gənclik Şubesi", date: "5 dk önce" },
  { id: "ord-3", customer: "Nigar Hüseynova", amount: 210.00, status: "completed", branch: "28 May Şubesi", date: "12 dk önce" },
  { id: "ord-4", customer: "Rəşad Quliyev", amount: 45.50, status: "cancelled", branch: "Nizami Şubesi", date: "18 dk önce" },
  { id: "ord-5", customer: "Aygün Səfərova", amount: 156.00, status: "completed", branch: "Sumqayıt Şubesi", date: "25 dk önce" },
  { id: "ord-6", customer: "Tural Əhmədov", amount: 78.00, status: "processing", branch: "Gənclik Şubesi", date: "35 dk önce" },
];

export const mockRevenueBreakdown = [
  { name: "Google Ads", value: 4500, color: "#2563EB" },
  { name: "Meta Ads", value: 3500, color: "#059669" },
  { name: "TikTok Ads", value: 2000, color: "#D97706" },
  { name: "LinkedIn", value: 1200, color: "#7C3AED" },
];

export const mockBestProducts = [
  { id: "p1", name: "Çiken Burger", revenue: 24500, orders: 980, trend: "+12%" as const },
  { id: "p2", name: "Qril Toyuq Salatı", revenue: 18200, orders: 640, trend: "+8%" as const },
  { id: "p3", name: "Margherita Pizza", revenue: 15600, orders: 520, trend: "-3%" as const },
  { id: "p4", name: "Tuna Salatı", revenue: 12300, orders: 410, trend: "+5%" as const },
  { id: "p5", name: "Falafel Tabağı", revenue: 9800, orders: 340, trend: "+15%" as const },
];

export const mockSalesComparison = [
  { period: "Bu Hafta", revenue: 42500, orders: 1420 },
  { period: "Geçen Hafta", revenue: 38900, orders: 1310 },
  { period: "2 Hafta Önce", revenue: 41200, orders: 1380 },
  { period: "3 Hafta Önce", revenue: 36500, orders: 1220 },
];

export const mockEmployeePerformance = [
  { id: "e1", name: "Nigar Hüseynova", role: "Müdür", branch: "Nizami Şubesi", sales: 45200, rating: 4.8, status: "active" as const },
  { id: "e2", name: "Rəşad Quliyev", role: "Garson", branch: "Nizami Şubesi", sales: 32100, rating: 4.5, status: "active" as const },
  { id: "e3", name: "Leyla Əliyeva", role: "Müdür", branch: "Gənclik Şubesi", sales: 38400, rating: 4.6, status: "active" as const },
  { id: "e4", name: "Əhməd Məmmədov", role: "Aşçı", branch: "28 May Şubesi", sales: 28900, rating: 4.7, status: "active" as const },
  { id: "e5", name: "Aygün Səfərova", role: "Garson", branch: "Sumqayıt Şubesi", sales: 21500, rating: 4.3, status: "active" as const },
];

export const mockSystemHealth = {
  status: "healthy" as const,
  uptime: "99.97%",
  last_check: "2 dk önce",
  services: [
    { name: "API", status: "operational" as const },
    { name: "Database", status: "operational" as const },
    { name: "AI Engine", status: "operational" as const },
    { name: "Social Connectors", status: "degraded" as const },
  ],
};

export const mockAuditLogs = [
  { id: "log-1", user: "Vüqar Məmmədov", action: "Kampanya oluşturdu", target: "Yaz İndirimi 2025", timestamp: "5 dk önce" },
  { id: "log-2", user: "Nigar Hüseynova", action: "Menü güncelledi", target: "Nizami Şubesi", timestamp: "15 dk önce" },
  { id: "log-3", user: "Rəşad Quliyev", action: "Rapor indirdi", target: "Aylık Satış Raporu", timestamp: "1 saat önce" },
  { id: "log-4", user: "Leyla Əliyeva", action: "Şube ayarlarını değiştirdi", target: "Gənclik Şubesi", timestamp: "2 saat önce" },
];

export const mockSavedReports = [
  { id: "rpt-1", title: "Aylık Satış Özeti", type: "sales", created_at: "2025-06-01", last_run: "2 saat önce" },
  { id: "rpt-2", title: "Reklam ROI Analizi", type: "ads", created_at: "2025-06-05", last_run: "1 gün önce" },
  { id: "rpt-3", title: "Şube Karşılaştırma", type: "branches", created_at: "2025-06-10", last_run: "3 gün önce" },
  { id: "rpt-4", title: "Müşteri Segmentasyon", type: "customers", created_at: "2025-06-12", last_run: "12 saat önce" },
  { id: "rpt-5", title: "Sosyal Medya Performans", type: "social", created_at: "2025-06-15", last_run: "5 dk önce" },
];

export const mockExportHistory = [
  { id: "exp-1", format: "PDF", title: "Aylık Satış Raporu", size: "2.4 MB", status: "completed" as const, created_at: "2 saat önce" },
  { id: "exp-2", format: "Excel", title: "Şube Performansı", size: "1.1 MB", status: "completed" as const, created_at: "1 gün önce" },
  { id: "exp-3", format: "PDF", title: "Reklam Analizi", size: "3.2 MB", status: "processing" as const, created_at: "5 dk önce" },
];

export const mockWeeklyRevenue = [
  { week: "Hafta 1", revenue: 42500, target: 40000 },
  { week: "Hafta 2", revenue: 38900, target: 40000 },
  { week: "Hafta 3", revenue: 41200, target: 40000 },
  { week: "Hafta 4", revenue: 45600, target: 42000 },
];

export const mockMonthlyRevenue = [
  { month: "Ocak", revenue: 98500, target: 95000 },
  { month: "Şubat", revenue: 102000, target: 95000 },
  { month: "Mart", revenue: 112000, target: 100000 },
  { month: "Nisan", revenue: 108000, target: 100000 },
  { month: "Mayıs", revenue: 118000, target: 110000 },
  { month: "Haziran", revenue: 124580, target: 115000 },
];

export const mockCustomerGrowth = [
  { month: "Ocak", new: 120, returning: 340 },
  { month: "Şubat", new: 145, returning: 355 },
  { month: "Mart", new: 180, returning: 370 },
  { month: "Nisan", new: 160, returning: 385 },
  { month: "Mayıs", new: 210, returning: 400 },
  { month: "Haziran", new: 186, returning: 342 },
];

export const mockTopCustomers = [
  { id: "c1", name: "Əhməd Məmmədov", orders: 48, total: 1560, lastOrder: "2 gün önce" },
  { id: "c2", name: "Leyla Əliyeva", orders: 42, total: 1380, lastOrder: "1 gün önce" },
  { id: "c3", name: "Nigar Hüseynova", orders: 38, total: 1250, lastOrder: "3 gün önce" },
  { id: "c4", name: "Rəşad Quliyev", orders: 35, total: 1100, lastOrder: "5 gün önce" },
  { id: "c5", name: "Aygün Səfərova", orders: 30, total: 980, lastOrder: "1 gün önce" },
];

export const mockDigitalCampaigns = [
  { id: "camp-1", name: "Yaz İndirimi 2025", platform: "Meta Ads", budget: 5000, spent: 3240, impressions: 125000, clicks: 4200, roas: 3.8, status: "active" as const },
  { id: "camp-2", name: "Google Performance Max", platform: "Google Ads", budget: 4500, spent: 4500, impressions: 98000, clicks: 3100, roas: 4.2, status: "paused" as const },
  { id: "camp-3", name: "TikTok Viral", platform: "TikTok Ads", budget: 2000, spent: 1280, impressions: 185000, clicks: 5200, roas: 2.8, status: "active" as const },
  { id: "camp-4", name: "LinkedIn B2B", platform: "LinkedIn", budget: 1200, spent: 720, impressions: 24000, clicks: 480, roas: 2.1, status: "active" as const },
];

export const mockSocialAccounts = [
  { id: "sa-1", platform: "Instagram", handle: "@foodflow.az", followers: 12400, engagement: 4.2, status: "connected" as const },
  { id: "sa-2", platform: "Facebook", handle: "FoodFlow Azerbaijan", followers: 8900, engagement: 3.1, status: "connected" as const },
  { id: "sa-3", platform: "TikTok", handle: "@foodflow.az", followers: 15200, engagement: 6.8, status: "connected" as const },
  { id: "sa-4", platform: "Google Business", handle: "FoodFlow Azerbaijan", followers: 3200, engagement: 2.5, status: "connected" as const },
];

export const mockGoogleRankingData = [
  { keyword: "restoran bakü", position: 3, change: 1 },
  { keyword: "en iyi burger bakü", position: 1, change: 0 },
  { keyword: "yemek siparişi", position: 5, change: -1 },
  { keyword: "kafe bakü", position: 4, change: 2 },
  { keyword: "pizza siparişi", position: 2, change: 1 },
];

export const mockBacklinkData = [
  { domain: "timeout.com", links: 12, authority: 78 },
  { domain: "tripadvisor.com", links: 8, authority: 92 },
  { domain: "baku.az", links: 15, authority: 54 },
  { domain: "1map.com", links: 6, authority: 48 },
];

export const mockPageSpeedData = {
  desktop: { score: 88, lcp: "2.1s", fid: "12ms", cls: "0.05" },
  mobile: { score: 72, lcp: "3.4s", fid: "28ms", cls: "0.12" },
};

export const mockBehaviorFlowData = [
  { page: "/anasayfa", visitors: 45200, dropOff: "32%", nextPage: "/menu" },
  { page: "/menu", visitors: 30800, dropOff: "28%", nextPage: "/sepet" },
  { page: "/sepet", visitors: 18200, dropOff: "45%", nextPage: "/odeme" },
  { page: "/odeme", visitors: 9800, dropOff: "15%", nextPage: "/tesekkur" },
];

export const mockDemographicData = [
  { age: "18-24", male: 15, female: 22 },
  { age: "25-34", male: 28, female: 32 },
  { age: "35-44", male: 18, female: 15 },
  { age: "45-54", male: 8, female: 6 },
  { age: "55+", male: 3, female: 2 },
];

export const mockCustomEventsData = [
  { event: "menu_goruntuleme", count: 45200 },
  { event: "sepet_ekleme", count: 18500 },
  { event: "siparis_tamamlama", count: 9800 },
  { event: "yorum_yapma", count: 3200 },
  { event: "kampanya_tiklama", count: 7800 },
];

export const mockFinancialOverview = {
  revenue: 124580,
  expenses: 87600,
  profit: 36980,
  profitMargin: 29.7,
  tax: 7396,
  netProfit: 29584,
};

export const mockInventoryStockData = [
  { product: "Çiken Burger", inStock: 120, minLevel: 50, status: "adequate" as const },
  { product: "Patates Kızartması", inStock: 85, minLevel: 60, status: "adequate" as const },
  { product: "Cola", inStock: 200, minLevel: 100, status: "adequate" as const },
  { product: "Marul", inStock: 12, minLevel: 30, status: "low" as const },
  { product: "Domates", inStock: 8, minLevel: 25, status: "critical" as const },
];

export const mockSupplierData = [
  { id: "sup-1", name: "Bakü Et Ürünleri", category: "Et", status: "active" as const, rating: 4.5 },
  { id: "sup-2", name: "Gənclik Gıda", category: "Sebze/Meyve", status: "active" as const, rating: 4.2 },
  { id: "sup-3", name: "Coca-Cola Azerbaycan", category: "İçecek", status: "active" as const, rating: 4.8 },
  { id: "sup-4", name: "Unilever", category: "Temizlik", status: "inactive" as const, rating: 3.9 },
];

export const mockInvoicesData = [
  { id: "inv-1", number: "FAT-2025-001", amount: 5200, status: "paid" as const, date: "2025-06-01", supplier: "Bakü Et Ürünleri" },
  { id: "inv-2", number: "FAT-2025-002", amount: 3100, status: "paid" as const, date: "2025-06-05", supplier: "Gənclik Gıda" },
  { id: "inv-3", number: "FAT-2025-003", amount: 2800, status: "pending" as const, date: "2025-06-10", supplier: "Coca-Cola Azerbaycan" },
  { id: "inv-4", number: "FAT-2025-004", amount: 1500, status: "overdue" as const, date: "2025-05-20", supplier: "Unilever" },
];

export const mockCompanyList = [
  { id: "comp-1", name: "FoodFlow Azerbaijan", industry: "Restoran", branches: 5, status: "active" as const },
  { id: "comp-2", name: "CafeLine Premium", industry: "Kafe", branches: 3, status: "active" as const },
  { id: "comp-3", name: "BurgerLab", industry: "Fast Food", branches: 2, status: "inactive" as const },
];
