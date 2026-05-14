import { useState } from "react";
import {
  Sparkles,
  Wand2,
  FileText,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Plus,
  Download,
  Copy,
  ChevronRight,
  Instagram,
  Facebook,
  Music2,
  Twitter,
  Clock,
  Image,
  Play,
  FileImage,
  MonitorPlay,
  LayoutTemplate,
  Eye,
  Zap,
  TrendingUp,
  MoreHorizontal,
  Check,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────

interface FeatureCard {
  id: string;
  title: string;
  description: string;
  icon: "sparkles" | "wand" | "filetext" | "calendar";
  gradient: string;
  iconColor: string;
  action: string;
}

interface AuditCheck {
  id: string;
  label: string;
  status: "pass" | "warning" | "fail";
  detail: string;
}

interface GeneratedContent {
  id: string;
  title: string;
  format: "Instagram Post" | "Story" | "Reels" | "TikTok" | "Facebook Post" | "Twitter";
  platform: "instagram" | "facebook" | "tiktok" | "twitter";
  date: string;
  type: "image" | "video";
  gradient: string;
}

interface CalendarDay {
  day: string;
  date: number;
  isToday: boolean;
  items: Array<{
    type: "post" | "scheduled" | "urgent";
    platform: "instagram" | "facebook" | "tiktok" | "twitter";
  }>;
}

interface FormatItem {
  id: string;
  name: string;
  ratio: string;
  dimensions: string;
  platforms: Array<"instagram" | "facebook" | "tiktok" | "twitter">;
}

// ─── Mock Data: Feature Cards ────────────────────────────

const mockFeatures: FeatureCard[] = [
  {
    id: "feat-1",
    title: "Görsel Analizi",
    description: "AI ile görsellerinizi analiz edin, iyileştirme önerileri alın",
    icon: "sparkles",
    gradient: "from-purple-500 to-indigo-600",
    iconColor: "text-purple-600",
    action: "Analiz Et",
  },
  {
    id: "feat-2",
    title: "Görsel İyileştirme",
    description: "Otomatik iyileştirme uygulayın, renk ve netlik ayarları yapın",
    icon: "wand",
    gradient: "from-blue-500 to-cyan-600",
    iconColor: "text-blue-600",
    action: "İyileştir",
  },
  {
    id: "feat-3",
    title: "İçerik Üretimi",
    description: "Başlık, açıklama ve hashtag üretin, AI destekli içerik oluşturun",
    icon: "filetext",
    gradient: "from-emerald-500 to-teal-600",
    iconColor: "text-emerald-600",
    action: "Üret",
  },
  {
    id: "feat-4",
    title: "İçerik Planlayıcı",
    description: "AI destekli içerik takvimi oluşturun, otomatik zamanlayın",
    icon: "calendar",
    gradient: "from-orange-500 to-amber-600",
    iconColor: "text-orange-600",
    action: "Planla",
  },
];

// ─── Mock Data: Audit Checks ─────────────────────────────

const mockAuditChecks: AuditCheck[] = [
  { id: "check-1", label: "Renk Uyumu", status: "pass", detail: "+/+" },
  { id: "check-2", label: "Metin Oranı", status: "warning", detail: "!" },
  { id: "check-3", label: "Kompozisyon", status: "pass", detail: "+" },
  { id: "check-4", label: "Marka Tutarlılığı", status: "pass", detail: "+" },
];

// ─── Mock Data: Generated Content ────────────────────────

const mockGeneratedContent: GeneratedContent[] = [
  {
    id: "gen-1",
    title: "Yaz Menü Tanıtımı",
    format: "Instagram Post",
    platform: "instagram",
    date: "15 Haz 2024",
    type: "image",
    gradient: "from-pink-400 to-rose-500",
  },
  {
    id: "gen-2",
    title: "Mutfak Hikayeleri",
    format: "Story",
    platform: "instagram",
    date: "14 Haz 2024",
    type: "video",
    gradient: "from-purple-400 to-violet-500",
  },
  {
    id: "gen-3",
    title: "Şefin Özel Tarifi",
    format: "Reels",
    platform: "instagram",
    date: "13 Haz 2024",
    type: "video",
    gradient: "from-amber-400 to-orange-500",
  },
  {
    id: "gen-4",
    title: "Müşteri Deneyimi",
    format: "TikTok",
    platform: "tiktok",
    date: "12 Haz 2024",
    type: "video",
    gradient: "from-gray-700 to-gray-900",
  },
  {
    id: "gen-5",
    title: "Kampanya Görselleri",
    format: "Facebook Post",
    platform: "facebook",
    date: "11 Haz 2024",
    type: "image",
    gradient: "from-blue-400 to-blue-600",
  },
  {
    id: "gen-6",
    title: "Günün Menüsü",
    format: "Twitter",
    platform: "twitter",
    date: "10 Haz 2024",
    type: "image",
    gradient: "from-sky-400 to-cyan-500",
  },
];

// ─── Mock Data: Calendar ─────────────────────────────────

const mockCalendarDays: CalendarDay[] = [
  {
    day: "Pzt",
    date: 10,
    isToday: false,
    items: [
      { type: "post", platform: "instagram" },
      { type: "scheduled", platform: "facebook" },
    ],
  },
  {
    day: "Sal",
    date: 11,
    isToday: false,
    items: [
      { type: "post", platform: "tiktok" },
      { type: "urgent", platform: "instagram" },
    ],
  },
  {
    day: "Çar",
    date: 12,
    isToday: false,
    items: [
      { type: "scheduled", platform: "twitter" },
    ],
  },
  {
    day: "Per",
    date: 13,
    isToday: false,
    items: [
      { type: "post", platform: "instagram" },
      { type: "post", platform: "facebook" },
      { type: "scheduled", platform: "tiktok" },
    ],
  },
  {
    day: "Cum",
    date: 14,
    isToday: false,
    items: [
      { type: "scheduled", platform: "instagram" },
    ],
  },
  {
    day: "Cmt",
    date: 15,
    isToday: false,
    items: [
      { type: "post", platform: "tiktok" },
      { type: "urgent", platform: "twitter" },
    ],
  },
  {
    day: "Paz",
    date: 16,
    isToday: true,
    items: [
      { type: "post", platform: "instagram" },
      { type: "scheduled", platform: "facebook" },
      { type: "scheduled", platform: "tiktok" },
    ],
  },
];

// ─── Mock Data: Format Library ───────────────────────────

const mockFormats: FormatItem[] = [
  { id: "fmt-1", name: "Kare Gönderi", ratio: "1:1", dimensions: "1080 × 1080", platforms: ["instagram", "facebook"] },
  { id: "fmt-2", name: "Dikey Hikaye", ratio: "9:16", dimensions: "1080 × 1920", platforms: ["instagram", "facebook"] },
  { id: "fmt-3", name: "Yatay Gönderi", ratio: "16:9", dimensions: "1920 × 1080", platforms: ["facebook", "twitter"] },
  { id: "fmt-4", name: "Portre Gönderi", ratio: "4:5", dimensions: "1080 × 1350", platforms: ["instagram"] },
  { id: "fmt-5", name: "Reels / Shorts", ratio: "9:16", dimensions: "1080 × 1920", platforms: ["instagram", "tiktok"] },
  { id: "fmt-6", name: "Twitter Gönderi", ratio: "16:9", dimensions: "1200 × 675", platforms: ["twitter"] },
  { id: "fmt-7", name: "Kapak Fotoğrafı", ratio: "1:1", dimensions: "1080 × 1080", platforms: ["facebook", "instagram"] },
  { id: "fmt-8", name: "Pinterest Pin", ratio: "2:3", dimensions: "1000 × 1500", platforms: ["instagram", "facebook"] },
];

// ─── Icon Map ────────────────────────────────────────────

const featureIconMap = {
  sparkles: Sparkles,
  wand: Wand2,
  filetext: FileText,
  calendar: Calendar,
};

const platformIcons = {
  instagram: Instagram,
  facebook: Facebook,
  tiktok: Music2,
  twitter: Twitter,
};

const platformColors = {
  instagram: "text-pink-500 bg-pink-50",
  facebook: "text-blue-600 bg-blue-50",
  tiktok: "text-gray-800 bg-gray-100",
  twitter: "text-sky-500 bg-sky-50",
};

const platformBadgeColors = {
  instagram: "bg-pink-100 text-pink-700",
  facebook: "bg-blue-100 text-blue-700",
  tiktok: "bg-gray-200 text-gray-800",
  twitter: "bg-sky-100 text-sky-700",
};

const dotColors = {
  post: "bg-blue-500",
  scheduled: "bg-emerald-500",
  urgent: "bg-red-500",
};

const itemTypeLabels = {
  post: "Gönderi",
  scheduled: "Planlı",
  urgent: "Acil",
};

const checkStatusIcons = {
  pass: { icon: CheckCircle2, color: "text-[#059669]" },
  warning: { icon: AlertCircle, color: "text-[#D97706]" },
  fail: { icon: AlertCircle, color: "text-[#DC2626]" },
};

// ─── Feature Card Component ──────────────────────────────

function FeatureCardItem({ feature, index }: { feature: FeatureCard; index: number }) {
  const Icon = featureIconMap[feature.icon];

  return (
    <Card
      className={cn(
        "group cursor-pointer transition-all duration-200 hover:shadow-[0_8px_20px_rgba(0,0,0,0.12)] hover:-translate-y-1 overflow-hidden",
        "opacity-0 animate-fade-in"
      )}
      style={{ animationDelay: `${index * 80}ms`, animationFillMode: "forwards" }}
    >
      <CardContent className="p-0">
        {/* Gradient Header */}
        <div
          className={cn(
            "h-2 bg-gradient-to-r",
            feature.gradient
          )}
        />
        <div className="p-5">
          {/* Icon + Title */}
          <div className="flex items-start gap-4">
            <div className={cn("flex items-center justify-center w-11 h-11 rounded-xl", feature.iconColor.split(" ")[1])}>
              <Icon className={cn("w-5 h-5", feature.iconColor.split(" ")[0])} />
            </div>
            <div className="flex-1">
              <h3 className="text-base font-semibold text-[#0F172A]">{feature.title}</h3>
              <p className="text-xs text-[#475569] mt-1 leading-relaxed">{feature.description}</p>
            </div>
          </div>

          {/* Action Button */}
          <div className="mt-4 flex items-center justify-between">
            <Button
              size="sm"
              className={cn(
                "h-8 text-xs font-medium text-white bg-gradient-to-r",
                feature.gradient
              )}
            >
              <Zap className="w-3.5 h-3.5 mr-1.5" />
              {feature.action}
            </Button>
            <ChevronRight className="w-4 h-4 text-[#94A3B8] group-hover:text-[#475569] group-hover:translate-x-0.5 transition-all" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Generated Content Card Component ────────────────────

function GeneratedContentCard({ content, index }: { content: GeneratedContent; index: number }) {
  const PlatformIcon = platformIcons[content.platform];

  return (
    <div
      className={cn(
        "group rounded-xl border border-[#E2E8F0] bg-white overflow-hidden",
        "transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5",
        "opacity-0 animate-fade-in"
      )}
      style={{ animationDelay: `${index * 60}ms`, animationFillMode: "forwards" }}
    >
      {/* Gradient Placeholder */}
      <div
        className={cn(
          "h-28 bg-gradient-to-br flex items-center justify-center relative",
          content.gradient
        )}
      >
        {content.type === "video" ? (
          <Play className="w-7 h-7 text-white/80" />
        ) : (
          <Image className="w-7 h-7 text-white/80" />
        )}
        {/* Platform Icon */}
        <div className="absolute top-2 right-2 w-7 h-7 rounded-full bg-white/90 flex items-center justify-center">
          <PlatformIcon className="w-3.5 h-3.5 text-[#475569]" />
        </div>
      </div>

      {/* Content */}
      <div className="p-3.5">
        <Badge
          className={cn(
            "text-[10px] font-semibold border-0 mb-2",
            platformBadgeColors[content.platform]
          )}
        >
          {content.format}
        </Badge>
        <h4 className="text-sm font-semibold text-[#0F172A] truncate mb-1">{content.title}</h4>
        <div className="flex items-center justify-between">
          <span className="text-xs text-[#94A3B8]">{content.date}</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-[#475569] hover:text-[#0F172A] px-2"
          >
            <Download className="w-3.5 h-3.5 mr-1" />
            İndir
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Format Row Component ────────────────────────────────

function FormatRow({ format, index }: { format: FormatItem; index: number }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={cn(
        "flex items-center justify-between p-4 rounded-xl border border-[#E2E8F0] bg-white",
        "transition-all duration-200 hover:shadow-sm",
        "opacity-0 animate-fade-in"
      )}
      style={{ animationDelay: `${index * 50}ms`, animationFillMode: "forwards" }}
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-[#F1F5F9]">
          <LayoutTemplate className="w-5 h-5 text-[#475569]" />
        </div>
        <div>
          <p className="text-sm font-semibold text-[#0F172A]">{format.name}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <Badge variant="outline" className="text-[10px] h-5 px-1.5">
              {format.ratio}
            </Badge>
            <span className="text-xs text-[#94A3B8]">{format.dimensions}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Platform Icons */}
        <div className="flex items-center -space-x-1">
          {format.platforms.map((plat) => {
            const PlatIcon = platformIcons[plat];
            return (
              <div
                key={plat}
                className={cn(
                  "flex items-center justify-center w-6 h-6 rounded-full border-2 border-white",
                  platformColors[plat].split(" ")[1]
                )}
                title={plat}
              >
                <PlatIcon className={cn("w-3 h-3", platformColors[plat].split(" ")[0])} />
              </div>
            );
          })}
        </div>
        {/* Copy Button */}
        <Button
          variant="ghost"
          size="sm"
          className="h-8 text-xs text-[#475569] hover:text-[#0F172A] px-2"
          onClick={handleCopy}
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 mr-1 text-[#059669]" />
              <span className="text-[#059669]">Kopyalandı</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5 mr-1" />
              Kopyala
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────

export default function CreativeStudioPage() {
  return (
    <div className="space-y-6">
      {/* ═══ Page Header ═══════════════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Yaratıcı Stüdyo</h1>
          <p className="text-sm text-[#475569] mt-0.5">
            AI destekli içerik üretim ve yönetim merkezi
          </p>
        </div>
        <Button className="h-9 px-4 bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-sm font-medium">
          <Sparkles className="w-4 h-4 mr-2" />
          Yeni İçerik Oluştur
        </Button>
      </div>

      {/* ═══ Feature Cards (2x2 Grid) ══════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {mockFeatures.map((feature, index) => (
          <FeatureCardItem key={feature.id} feature={feature} index={index} />
        ))}
      </div>

      {/* ═══ Creative Audit Banner ═════════════════════ */}
      <Card className="bg-gradient-to-r from-[#7C3AED] to-[#6D28D9] border-0 text-white overflow-hidden">
        <CardContent className="p-6">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            {/* Left: Icon + Score + Checks */}
            <div className="flex items-start gap-5">
              <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-white/15 shrink-0">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-3 mb-3">
                  <h3 className="text-lg font-bold">Yaratıcı Denetim Skoru</h3>
                  <Badge className="bg-white/20 text-white border-0 text-sm font-bold px-2.5 py-0.5">
                    78/100
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-3">
                  {mockAuditChecks.map((check) => {
                    const StatusIcon = checkStatusIcons[check.status].icon;
                    const statusColor = checkStatusIcons[check.status].color;
                    return (
                      <div
                        key={check.id}
                        className="flex items-center gap-1.5 bg-white/10 rounded-full px-3 py-1"
                      >
                        <StatusIcon className={cn("w-3.5 h-3.5", statusColor === "text-[#059669]" ? "text-emerald-300" : statusColor === "text-[#D97706]" ? "text-amber-300" : "text-red-300")} />
                        <span className="text-xs font-medium">{check.label}</span>
                        <span className="text-xs font-bold ml-0.5">{check.detail}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Right: Button */}
            <Button
              variant="secondary"
              className="h-10 px-5 bg-white text-[#7C3AED] hover:bg-white/90 font-semibold text-sm shrink-0"
            >
              <FileText className="w-4 h-4 mr-2" />
              Denetim Raporu Al
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ═══ Generated Content + Mini Calendar ═════════ */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Generated Content */}
        <Card className="xl:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg font-bold text-[#0F172A]">Son Üretilen İçerikler</CardTitle>
                <p className="text-xs text-[#94A3B8] mt-0.5">
                  AI tarafından üretilen son içerikleriniz
                </p>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="w-4 h-4 text-[#94A3B8]" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {mockGeneratedContent.map((content, index) => (
                <GeneratedContentCard key={content.id} content={content} index={index} />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Mini Calendar */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-bold text-[#0F172A]">İçerik Takvimi</CardTitle>
            <p className="text-xs text-[#94A3B8]">Bu haftanın planlaması</p>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-7 gap-1">
              {mockCalendarDays.map((day) => (
                <div
                  key={day.date}
                  className={cn(
                    "flex flex-col items-center p-2 rounded-xl border transition-all",
                    day.isToday
                      ? "border-[#7C3AED] bg-[#F5F3FF]"
                      : "border-transparent hover:border-[#E2E8F0] hover:bg-[#F8FAFC]"
                  )}
                >
                  <span className="text-[11px] font-medium text-[#94A3B8] mb-1">{day.day}</span>
                  <span
                    className={cn(
                      "text-sm font-bold mb-2",
                      day.isToday ? "text-[#7C3AED]" : "text-[#0F172A]"
                    )}
                  >
                    {day.date}
                  </span>
                  <div className="flex items-center gap-0.5 flex-wrap justify-center">
                    {day.items.map((item, i) => (
                      <span
                        key={i}
                        className={cn(
                          "w-2 h-2 rounded-full",
                          dotColors[item.type]
                        )}
                        title={`${itemTypeLabels[item.type]} · ${item.platform}`}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 mt-4 pt-4 border-t border-[#F1F5F9]">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="text-[11px] text-[#475569]">Gönderi</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-[11px] text-[#475569]">Planlı</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-[11px] text-[#475569]">Acil</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ═══ Format Library ════════════════════════════ */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg font-bold text-[#0F172A]">Format Kütüphanesi</CardTitle>
              <p className="text-xs text-[#94A3B8] mt-0.5">
                Sosyal medya platformları için boyut referansları
              </p>
            </div>
            <Badge variant="outline" className="text-xs">{mockFormats.length} Format</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {mockFormats.map((format, index) => (
            <FormatRow key={format.id} format={format} index={index} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
