import { useState, useEffect } from "react";
import {
  Settings,
  Bell,
  Shield,
  Plug,
  Globe,
  Clock,
  DollarSign,
  Mail,
  Smartphone,
  Send,
  Instagram,
  Facebook,
  ShoppingBag,
  Copy,
  Check,
  Eye,
  EyeOff,
  Lock,
  KeyRound,
  Monitor,
  ChevronDown,
  Save,
  ToggleLeft,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

// ─── Inline Mock Data ────────────────────────────────────

interface NotificationSetting {
  event: string;
  email: boolean;
  app: boolean;
  telegram: boolean;
}

interface Integration {
  id: string;
  name: string;
  icon: React.ElementType;
  connected: boolean;
  lastSync: string | null;
  color: string;
}

interface ApiKey {
  id: string;
  name: string;
  key: string;
  created: string;
  lastUsed: string;
}

interface Session {
  id: string;
  device: string;
  browser: string;
  ip: string;
  location: string;
  lastActive: string;
  current: boolean;
}

const notificationSettings: NotificationSetting[] = [
  { event: "Yeni sipariş alındığında", email: true, app: true, telegram: false },
  { event: "Düşük stok uyarısı", email: true, app: true, telegram: true },
  { event: "Günlük rapor hazır", email: true, app: false, telegram: true },
  { event: "AI önerileri", email: false, app: true, telegram: false },
  { event: "Sistem uyarıları", email: true, app: true, telegram: true },
];

const integrations: Integration[] = [
  { id: "int-1", name: "Instagram", icon: Instagram, connected: true, lastSync: "5 dk önce", color: "#E4405F" },
  { id: "int-2", name: "Facebook", icon: Facebook, connected: true, lastSync: "10 dk önce", color: "#1877F2" },
  { id: "int-3", name: "TikTok", icon: Smartphone, connected: false, lastSync: null, color: "#000000" },
  { id: "int-4", name: "Google Ads", icon: Monitor, connected: true, lastSync: "1 saat önce", color: "#4285F4" },
  { id: "int-5", name: "Meta Ads", icon: Facebook, connected: true, lastSync: "30 dk önce", color: "#0668E1" },
  { id: "int-6", name: "WhatsApp", icon: Smartphone, connected: false, lastSync: null, color: "#25D366" },
  { id: "int-7", name: "Telegram", icon: Send, connected: true, lastSync: "2 dk önce", color: "#0088CC" },
  { id: "int-8", name: "Shopify", icon: ShoppingBag, connected: false, lastSync: null, color: "#96BF48" },
];

const apiKeys: ApiKey[] = [
  { id: "api-1", name: "Üretim API Anahtarı", key: "pk_live_51HYs2jK8QJ4mP2v9xYzA8BcDeFgHiJkLmNoPqRsTuVwXyZ", created: "12.03.2025", lastUsed: "2 saat önce" },
  { id: "api-2", name: "Test API Anahtarı", key: "pk_test_9xYzA8BcDeFgHiJkLmNoPqRsTuVwXyZ7aBcD3eFgH", created: "15.05.2025", lastUsed: "1 gün önce" },
];

const sessions: Session[] = [
  { id: "s1", device: "MacBook Pro", browser: "Chrome 125", ip: "185.30.**.***", location: "Bakü, Azerbaycan", lastActive: "Şu an", current: true },
  { id: "s2", device: "iPhone 15 Pro", browser: "Safari 17", ip: "185.30.**.***", location: "Bakü, Azerbaycan", lastActive: "2 saat önce", current: false },
  { id: "s3", device: "Windows PC", browser: "Edge 124", ip: "94.20.**.***", location: "Sumqayıt, Azerbaycan", lastActive: "3 gün önce", current: false },
];

const languages = ["Türkçe", "English", "Azerbaycan"];
const timezones = ["UTC+04:00 (Bakü)", "UTC+03:00 (İstanbul)", "UTC+00:00 (Londra)"];
const currencies = ["AZN", "USD", "EUR", "TRY"];

// ─── Main Component ──────────────────────────────────────

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("general");
  const [loading, setLoading] = useState(true);

  // Load settings from API
  useEffect(() => {
    let mounted = true;
    async function loadData() {
      try {
        setLoading(true);
        await Promise.all([
          api.settings.get(),
          api.settings.integrations(),
          api.settings.apiKeys(),
          api.settings.sessions(),
        ]);
      } catch (err) {
        if (mounted) console.error("Ayarlar yüklenemedi:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    loadData();
    return () => { mounted = false; };
  }, []);
  const [companyName, setCompanyName] = useState("FoodFlow Azerbaijan");
  const [language, setLanguage] = useState("Türkçe");
  const [timezone, setTimezone] = useState("UTC+04:00 (Bakü)");
  const [currency, setCurrency] = useState("AZN");
  const [notifications, setNotifications] = useState(notificationSettings);
  const [twoFA, setTwoFA] = useState(true);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [integrationList, setIntegrationList] = useState(integrations);

  const toggleNotification = (index: number, channel: "email" | "app" | "telegram") => {
    setNotifications((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [channel]: !next[index][channel] };
      return next;
    });
  };

  const handleCopy = (id: string, key: string) => {
    navigator.clipboard?.writeText(key);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const toggleIntegration = (id: string) => {
    setIntegrationList((prev) =>
      prev.map((i) =>
        i.id === id
          ? { ...i, connected: !i.connected, lastSync: !i.connected ? "Az önce" : null }
          : i
      )
    );
  };

  return (
    <div className="space-y-6">
      {/* ═══ Page Header ════════════════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Ayarlar</h1>
          <p className="text-sm text-[#475569] mt-0.5">Platform ayarlarınızı yapılandırın</p>
        </div>
        <Button className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-9 gap-2">
          <Save className="w-4 h-4" />
          Değişiklikleri Kaydet
        </Button>
      </div>

      {/* ═══ Tabs ═══════════════════════════════════════ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="bg-white border border-[#E2E8F0] p-1 h-auto gap-1 opacity-0 animate-fade-in" style={{ animationFillMode: "forwards" }}>
          <TabsTrigger value="general" className={cn("gap-2 px-4 py-2 text-sm data-[state=active]:bg-[#2563EB] data-[state=active]:text-white", activeTab === "general" ? "" : "text-[#475569]")}>
            <Settings className="w-4 h-4" /> Genel
          </TabsTrigger>
          <TabsTrigger value="notifications" className={cn("gap-2 px-4 py-2 text-sm data-[state=active]:bg-[#2563EB] data-[state=active]:text-white", activeTab === "notifications" ? "" : "text-[#475569]")}>
            <Bell className="w-4 h-4" /> Bildirimler
          </TabsTrigger>
          <TabsTrigger value="security" className={cn("gap-2 px-4 py-2 text-sm data-[state=active]:bg-[#2563EB] data-[state=active]:text-white", activeTab === "security" ? "" : "text-[#475569]")}>
            <Shield className="w-4 h-4" /> Güvenlik
          </TabsTrigger>
          <TabsTrigger value="integrations" className={cn("gap-2 px-4 py-2 text-sm data-[state=active]:bg-[#2563EB] data-[state=active]:text-white", activeTab === "integrations" ? "" : "text-[#475569]")}>
            <Plug className="w-4 h-4" /> Entegrasyonlar
          </TabsTrigger>
        </TabsList>

        {/* ─── Tab: General ──────────────────────────── */}
        <TabsContent value="general" className="space-y-5 mt-0">
          <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "100ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-[#0F172A]">Şirket Bilgileri</CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8]">Temel şirket ayarlarınızı güncelleyin</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Company Name */}
              <div>
                <label className="text-sm font-medium text-[#0F172A] mb-1.5 block">Şirket Adı</label>
                <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} className="h-10 border-[#E2E8F0] max-w-md" />
              </div>
              {/* Language */}
              <div>
                <label className="text-sm font-medium text-[#0F172A] mb-1.5 block">Dil</label>
                <div className="relative max-w-md">
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full h-10 px-3 pr-10 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] appearance-none cursor-pointer"
                  >
                    {languages.map((l) => <option key={l} value={l}>{l}</option>)}
                  </select>
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8] pointer-events-none" />
                </div>
              </div>
              {/* Timezone */}
              <div>
                <label className="text-sm font-medium text-[#0F172A] mb-1.5 block">Zaman Dilimi</label>
                <div className="relative max-w-md">
                  <select
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="w-full h-10 px-3 pr-10 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] appearance-none cursor-pointer"
                  >
                    {timezones.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
                  </select>
                  <Clock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8] pointer-events-none" />
                </div>
              </div>
              {/* Currency */}
              <div>
                <label className="text-sm font-medium text-[#0F172A] mb-1.5 block">Para Birimi</label>
                <div className="relative max-w-md">
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full h-10 px-3 pr-10 bg-white border border-[#E2E8F0] rounded-lg text-sm text-[#0F172A] appearance-none cursor-pointer"
                  >
                    {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8] pointer-events-none" />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Tab: Notifications ────────────────────── */}
        <TabsContent value="notifications" className="space-y-5 mt-0">
          <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "100ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-[#0F172A]">Bildirim Tercihleri</CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8]">Hangi olaylar için hangi kanallarda bildirim alacağınızı seçin</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#E2E8F0]">
                      <th className="text-left text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3 min-w-[240px]">Olay</th>
                      <th className="text-center text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">
                        <div className="flex flex-col items-center gap-1"><Mail className="w-4 h-4" />E-posta</div>
                      </th>
                      <th className="text-center text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">
                        <div className="flex flex-col items-center gap-1"><Smartphone className="w-4 h-4" />Uygulama</div>
                      </th>
                      <th className="text-center text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider px-3 py-3">
                        <div className="flex flex-col items-center gap-1"><Send className="w-4 h-4" />Telegram</div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {notifications.map((ns, idx) => (
                      <tr key={idx} className={cn("border-b border-[#F1F5F9] hover:bg-[#F8FAFC] transition-colors", idx % 2 === 0 ? "bg-white" : "bg-[#FAFBFC]")}>
                        <td className="px-3 py-3.5 text-sm font-medium text-[#0F172A]">{ns.event}</td>
                        <td className="px-3 py-3.5 text-center">
                          <Switch checked={ns.email} onCheckedChange={() => toggleNotification(idx, "email")} className="data-[state=checked]:bg-[#2563EB]" />
                        </td>
                        <td className="px-3 py-3.5 text-center">
                          <Switch checked={ns.app} onCheckedChange={() => toggleNotification(idx, "app")} className="data-[state=checked]:bg-[#2563EB]" />
                        </td>
                        <td className="px-3 py-3.5 text-center">
                          <Switch checked={ns.telegram} onCheckedChange={() => toggleNotification(idx, "telegram")} className="data-[state=checked]:bg-[#2563EB]" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Tab: Security ─────────────────────────── */}
        <TabsContent value="security" className="space-y-5 mt-0">
          {/* Password Change */}
          <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "100ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
                <Lock className="w-4 h-4 text-[#2563EB]" /> Şifre Değiştir
              </CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8]">Hesap güvenliğiniz için düzenli olarak şifrenizi değiştirin</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 max-w-lg">
              <div className="relative">
                <label className="text-sm font-medium text-[#0F172A] mb-1.5 block">Mevcut Şifre</label>
                <Input type={showOld ? "text" : "password"} value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} className="h-10 border-[#E2E8F0] pr-10" placeholder="••••••••" />
                <button onClick={() => setShowOld(!showOld)} className="absolute right-3 top-[34px] text-[#94A3B8] hover:text-[#475569]">
                  {showOld ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <div className="relative">
                <label className="text-sm font-medium text-[#0F172A] mb-1.5 block">Yeni Şifre</label>
                <Input type={showNew ? "text" : "password"} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="h-10 border-[#E2E8F0] pr-10" placeholder="••••••••" />
                <button onClick={() => setShowNew(!showNew)} className="absolute right-3 top-[34px] text-[#94A3B8] hover:text-[#475569]">
                  {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <div className="relative">
                <label className="text-sm font-medium text-[#0F172A] mb-1.5 block">Yeni Şifre (Tekrar)</label>
                <Input type={showConfirm ? "text" : "password"} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="h-10 border-[#E2E8F0] pr-10" placeholder="••••••••" />
                <button onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3 top-[34px] text-[#94A3B8] hover:text-[#475569]">
                  {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <Button className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-9 mt-2">
                <KeyRound className="w-4 h-4 mr-1" /> Şifreyi Güncelle
              </Button>
            </CardContent>
          </Card>

          {/* Two Factor Auth */}
          <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "200ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-[#D1FAE5]">
                    <Shield className="w-5 h-5 text-[#059669]" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#0F172A]">İki Faktörlü Kimlik Doğrulama (2FA)</p>
                    <p className="text-[13px] text-[#94A3B8]">Hesabınıza ek bir güvenlik katmanı ekleyin</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge className={cn("text-[11px] h-5 px-2", twoFA ? "bg-[#D1FAE5] text-[#059669]" : "bg-[#F1F5F9] text-[#94A3B8]")}>
                    {twoFA ? "Aktif" : "Pasif"}
                  </Badge>
                  <Switch checked={twoFA} onCheckedChange={setTwoFA} className="data-[state=checked]:bg-[#059669]" />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* API Keys */}
          <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "300ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-[#0F172A] flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-[#2563EB]" /> API Anahtarları
              </CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8]">Uygulama entegrasyonları için API anahtarlarınızı yönetin</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {apiKeys.map((ak) => (
                <div key={ak.id} className="flex items-center justify-between p-4 rounded-lg border border-[#E2E8F0] bg-[#FAFBFC] hover:bg-[#F8FAFC] transition-colors">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[#0F172A]">{ak.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="text-xs text-[#475569] bg-[#F1F5F9] px-2 py-0.5 rounded font-mono truncate max-w-[300px] block">
                        {ak.key.slice(0, 12)}...{ak.key.slice(-8)}
                      </code>
                      <span className="text-[11px] text-[#94A3B8]">Son kullanım: {ak.lastUsed}</span>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5 ml-3"
                    onClick={() => handleCopy(ak.id, ak.key)}
                  >
                    {copiedId === ak.id ? <Check className="w-3.5 h-3.5 text-[#059669]" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedId === ak.id ? "Kopyalandı" : "Kopyala"}
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Active Sessions */}
          <Card className="opacity-0 animate-fade-in-up" style={{ animationDelay: "400ms", animationFillMode: "forwards", animationDuration: "500ms" }}>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-[#0F172A]">Aktif Oturumlar</CardTitle>
              <CardDescription className="text-[13px] text-[#94A3B8]">Hesabınıza giriş yapmış cihazlar</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {sessions.map((s) => (
                <div key={s.id} className={cn("flex items-center justify-between p-4 rounded-lg border transition-colors", s.current ? "border-[#2563EB] bg-[#DBEAFE]/20" : "border-[#E2E8F0] bg-[#FAFBFC]")}>
                  <div className="flex items-center gap-3">
                    <div className={cn("flex items-center justify-center w-10 h-10 rounded-full", s.current ? "bg-[#DBEAFE] text-[#2563EB]" : "bg-[#F1F5F9] text-[#94A3B8]")}>
                      <Monitor className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-[#0F172A]">{s.device}</p>
                        {s.current && <Badge className="bg-[#DBEAFE] text-[#2563EB] hover:bg-[#DBEAFE] text-[10px] h-4 px-1.5">Bu Cihaz</Badge>}
                      </div>
                      <p className="text-[12px] text-[#94A3B8]">{s.browser} · {s.ip} · {s.location}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-[#94A3B8]">{s.lastActive}</span>
                    {!s.current && (
                      <Button variant="outline" size="sm" className="h-7 text-xs text-[#DC2626] border-[#FECACA] hover:bg-[#FEE2E2]">
                        Oturumu Kapat
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ─── Tab: Integrations ─────────────────────── */}
        <TabsContent value="integrations" className="space-y-5 mt-0">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {integrationList.map((integration, idx) => {
              const Icon = integration.icon;
              return (
                <Card
                  key={integration.id}
                  className="opacity-0 animate-fade-in-up transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]"
                  style={{ animationDelay: `${100 + idx * 60}ms`, animationFillMode: "forwards", animationDuration: "400ms" }}
                >
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div
                          className="flex items-center justify-center w-11 h-11 rounded-xl"
                          style={{ backgroundColor: `${integration.color}15` }}
                        >
                          <Icon className="w-5 h-5" style={{ color: integration.color }} />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-[#0F172A]">{integration.name}</p>
                          <p className="text-[11px] text-[#94A3B8]">{integration.connected ? integration.lastSync : "Bağlı değil"}</p>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <Badge
                        className={cn(
                          "text-[11px] h-5 px-2 font-medium",
                          integration.connected
                            ? "bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5]"
                            : "bg-[#F1F5F9] text-[#94A3B8] hover:bg-[#F1F5F9]"
                        )}
                      >
                        <span className={cn("w-1.5 h-1.5 rounded-full mr-1.5", integration.connected ? "bg-[#059669]" : "bg-[#94A3B8]")} />
                        {integration.connected ? "Bağlı" : "Bağlan"}
                      </Badge>
                      <Button
                        variant={integration.connected ? "outline" : "default"}
                        size="sm"
                        className={cn(
                          "h-7 text-xs",
                          integration.connected
                            ? "text-[#DC2626] border-[#FECACA] hover:bg-[#FEE2E2]"
                            : "bg-[#2563EB] hover:bg-[#1D4ED8] text-white"
                        )}
                        onClick={() => toggleIntegration(integration.id)}
                      >
                        {integration.connected ? "Bağlantıyı Kes" : "Bağlan"}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>
      </Tabs>

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
