import { useState } from "react";
import {
  Instagram,
  Facebook,
  Twitter,
  Music2,
  TrendingUp,
  TrendingDown,
  Heart,
  MessageCircle,
  Share2,
  Eye,
  Plus,
  Settings,
  ChevronRight,
  MoreHorizontal,
  Clock,
  FileEdit,
  CheckCircle2,
  AlertCircle,
  ArrowUpRight,
  Image,
  Play,
  Pause,
  Globe,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────

interface SocialAccount {
  id: string;
  platform: "instagram" | "facebook" | "tiktok" | "twitter";
  name: string;
  followers: number;
  change: number;
  changeType: "up" | "down";
  posts: number;
  status: "active" | "warning" | "inactive";
}

interface PostItem {
  id: string;
  title: string;
  platform: "instagram" | "facebook" | "tiktok" | "twitter";
  type: "image" | "video" | "carousel" | "story";
  likes: number;
  comments: number;
  shares: number;
  date: string;
  gradient: string;
  status: "published" | "scheduled" | "draft";
}

interface EngagementDataPoint {
  day: string;
  likes: number;
  comments: number;
  shares: number;
}

interface Competitor {
  id: string;
  name: string;
  handle: string;
  followers: number;
  engagementRate: number;
  change: number;
  changeType: "up" | "down";
}

// ─── Mock Data: Social Accounts ──────────────────────────

const mockAccounts: SocialAccount[] = [
  {
    id: "acc-1",
    platform: "instagram",
    name: "Instagram",
    followers: 12450,
    change: 5.2,
    changeType: "up",
    posts: 156,
    status: "active",
  },
  {
    id: "acc-2",
    platform: "facebook",
    name: "Facebook",
    followers: 8230,
    change: 3.1,
    changeType: "up",
    posts: 89,
    status: "active",
  },
  {
    id: "acc-3",
    platform: "tiktok",
    name: "TikTok",
    followers: 5100,
    change: 12.8,
    changeType: "up",
    posts: 45,
    status: "active",
  },
  {
    id: "acc-4",
    platform: "twitter",
    name: "Twitter",
    followers: 3800,
    change: 1.2,
    changeType: "down",
    posts: 203,
    status: "warning",
  },
];

// ─── Mock Data: Posts ────────────────────────────────────

const mockPublishedPosts: PostItem[] = [
  {
    id: "post-1",
    title: "Yeni Menü Tanıtımı",
    platform: "instagram",
    type: "carousel",
    likes: 1240,
    comments: 89,
    shares: 45,
    date: "15 Haz 2024",
    gradient: "from-pink-500 to-purple-600",
    status: "published",
  },
  {
    id: "post-2",
    title: "Mutfakta Bir Gün",
    platform: "tiktok",
    type: "video",
    likes: 3800,
    comments: 156,
    shares: 420,
    date: "14 Haz 2024",
    gradient: "from-gray-900 to-gray-700",
    status: "published",
  },
  {
    id: "post-3",
    title: "Hafta Sonu Özel",
    platform: "facebook",
    type: "image",
    likes: 520,
    comments: 34,
    shares: 12,
    date: "13 Haz 2024",
    gradient: "from-blue-500 to-blue-700",
    status: "published",
  },
  {
    id: "post-4",
    title: "Müşteri Yorumları",
    platform: "instagram",
    type: "image",
    likes: 890,
    comments: 67,
    shares: 23,
    date: "12 Haz 2024",
    gradient: "from-amber-400 to-orange-500",
    status: "published",
  },
  {
    id: "post-5",
    title: "Şefin Özel Tarifi",
    platform: "tiktok",
    type: "video",
    likes: 5600,
    comments: 234,
    shares: 890,
    date: "11 Haz 2024",
    gradient: "from-teal-500 to-emerald-600",
    status: "published",
  },
  {
    id: "post-6",
    title: "Kampanya Duyurusu",
    platform: "twitter",
    type: "image",
    likes: 320,
    comments: 18,
    shares: 56,
    date: "10 Haz 2024",
    gradient: "from-sky-500 to-indigo-600",
    status: "published",
  },
];

const mockScheduledPosts: PostItem[] = [
  {
    id: "sch-1",
    title: "Ramazan Menüsü",
    platform: "instagram",
    type: "carousel",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "18 Haz 2024 · 14:00",
    gradient: "from-emerald-500 to-teal-600",
    status: "scheduled",
  },
  {
    id: "sch-2",
    title: "Personel Tanıtımı",
    platform: "facebook",
    type: "image",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "19 Haz 2024 · 10:00",
    gradient: "from-violet-500 to-purple-600",
    status: "scheduled",
  },
  {
    id: "sch-3",
    title: "Yemek Hazırlığı",
    platform: "tiktok",
    type: "video",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "20 Haz 2024 · 16:30",
    gradient: "from-rose-500 to-pink-600",
    status: "scheduled",
  },
  {
    id: "sch-4",
    title: "İndirim Fırsatı",
    platform: "twitter",
    type: "image",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "21 Haz 2024 · 09:00",
    gradient: "from-amber-500 to-yellow-600",
    status: "scheduled",
  },
];

const mockDraftPosts: PostItem[] = [
  {
    id: "draft-1",
    title: "Yeni Şube Açılışı",
    platform: "instagram",
    type: "carousel",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "Taslak",
    gradient: "from-indigo-500 to-blue-600",
    status: "draft",
  },
  {
    id: "draft-2",
    title: "Mevsimsel Tatlılar",
    platform: "facebook",
    type: "image",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "Taslak",
    gradient: "from-fuchsia-500 to-pink-600",
    status: "draft",
  },
  {
    id: "draft-3",
    title: "Online Sipariş",
    platform: "tiktok",
    type: "video",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "Taslak",
    gradient: "from-cyan-500 to-blue-600",
    status: "draft",
  },
  {
    id: "draft-4",
    title: "Etkinlik Daveti",
    platform: "twitter",
    type: "image",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "Taslak",
    gradient: "from-orange-500 to-red-600",
    status: "draft",
  },
  {
    id: "draft-5",
    title: "Şefin Tavsiyeleri",
    platform: "instagram",
    type: "story",
    likes: 0,
    comments: 0,
    shares: 0,
    date: "Taslak",
    gradient: "from-lime-500 to-green-600",
    status: "draft",
  },
];

// ─── Mock Data: Engagement Chart ─────────────────────────

const mockEngagementData: EngagementDataPoint[] = [
  { day: "9 Haz", likes: 4200, comments: 380, shares: 210 },
  { day: "10 Haz", likes: 3800, comments: 420, shares: 190 },
  { day: "11 Haz", likes: 6800, comments: 510, shares: 420 },
  { day: "12 Haz", likes: 5100, comments: 340, shares: 280 },
  { day: "13 Haz", likes: 3200, comments: 210, shares: 150 },
  { day: "14 Haz", likes: 7200, comments: 580, shares: 560 },
  { day: "15 Haz", likes: 5400, comments: 450, shares: 320 },
];

// ─── Mock Data: Competitors ──────────────────────────────

const mockCompetitors: Competitor[] = [
  {
    id: "comp-1",
    name: "Gourmet Burger",
    handle: "@gourmetburgerbaku",
    followers: 18900,
    engagementRate: 4.8,
    change: 2.3,
    changeType: "up",
  },
  {
    id: "comp-2",
    name: "Sushi Master",
    handle: "@sushimasteraz",
    followers: 10200,
    engagementRate: 3.2,
    change: 0.8,
    changeType: "up",
  },
  {
    id: "comp-3",
    name: "Kebab House",
    handle: "@kebabhouseaz",
    followers: 6700,
    engagementRate: 5.1,
    change: 1.5,
    changeType: "down",
  },
];

// ─── Platform Config ─────────────────────────────────────

const platformIcons = {
  instagram: Instagram,
  facebook: Facebook,
  tiktok: Music2,
  twitter: Twitter,
};

const platformColors = {
  instagram: { bg: "bg-pink-50", text: "text-pink-600", icon: "#E4405F", badge: "bg-pink-100 text-pink-700" },
  facebook: { bg: "bg-blue-50", text: "text-blue-600", icon: "#1877F2", badge: "bg-blue-100 text-blue-700" },
  tiktok: { bg: "bg-gray-100", text: "text-gray-800", icon: "#000000", badge: "bg-gray-200 text-gray-800" },
  twitter: { bg: "bg-sky-50", text: "text-sky-600", icon: "#1DA1F2", badge: "bg-sky-100 text-sky-700" },
};

const statusConfig = {
  active: { label: "Aktif", dot: "bg-[#059669]", text: "text-[#059669]" },
  warning: { label: "Uyarı", dot: "bg-[#D97706]", text: "text-[#D97706]" },
  inactive: { label: "Pasif", dot: "bg-[#DC2626]", text: "text-[#DC2626]" },
};

// ─── Helpers ─────────────────────────────────────────────

function formatNumber(num: number): string {
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  }
  return num.toLocaleString("tr-TR");
}

// ─── Custom Tooltip for Engagement Chart ─────────────────

function EngagementTooltip({ active, payload, label }: {
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
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-[#475569]">
            {entry.name === "likes" ? "Beğeni" : entry.name === "comments" ? "Yorum" : "Paylaşım"}:
          </span>
          <span className="font-semibold text-[#0F172A]">{entry.value.toLocaleString("tr-TR")}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Account Card Component ──────────────────────────────

function AccountCard({ account, index }: { account: SocialAccount; index: number }) {
  const Icon = platformIcons[account.platform];
  const TrendIcon = account.changeType === "up" ? TrendingUp : TrendingDown;
  const colors = platformColors[account.platform];
  const status = statusConfig[account.status];

  return (
    <Card
      className={cn(
        "transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5",
        "opacity-0 animate-fade-in"
      )}
      style={{ animationDelay: `${index * 80}ms`, animationFillMode: "forwards" }}
    >
      <CardContent className="p-5">
        {/* Header: Icon + Status */}
        <div className="flex items-center justify-between mb-4">
          <div className={cn("flex items-center justify-center w-11 h-11 rounded-xl", colors.bg)}>
            <Icon className="w-5 h-5" style={{ color: colors.icon }} />
          </div>
          <div className="flex items-center gap-1.5">
            <span className={cn("w-2 h-2 rounded-full", status.dot)} />
            <span className={cn("text-xs font-medium", status.text)}>{status.label}</span>
          </div>
        </div>

        {/* Follower Count */}
        <p className="text-[28px] font-bold text-[#0F172A] leading-tight">
          {account.followers.toLocaleString("tr-TR")}
        </p>
        <p className="text-xs text-[#94A3B8] mb-3">Takipçi</p>

        {/* Change + Posts Row */}
        <div className="flex items-center justify-between mb-4">
          <div
            className={cn(
              "flex items-center gap-1 text-xs font-semibold rounded-full px-2 py-0.5",
              account.changeType === "up"
                ? "text-[#059669] bg-[#D1FAE5]"
                : "text-[#DC2626] bg-[#FEE2E2]"
            )}
          >
            <TrendIcon className="w-3 h-3" />
            {account.changeType === "up" ? "+" : "-"}
            {Math.abs(account.change)}%
          </div>
          <span className="text-xs text-[#475569]">
            {account.posts} {account.platform === "tiktok" ? "video" : "gönderi"}
          </span>
        </div>

        {/* Manage Button */}
        <Button
          variant="outline"
          size="sm"
          className="w-full h-8 text-xs font-medium border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A]"
        >
          <Settings className="w-3.5 h-3.5 mr-1.5" />
          Hesabı Yönet
        </Button>
      </CardContent>
    </Card>
  );
}

// ─── Post Card Component ─────────────────────────────────

function PostCard({ post, index }: { post: PostItem; index: number }) {
  const colors = platformColors[post.platform];

  return (
    <div
      className={cn(
        "group rounded-xl border border-[#E2E8F0] bg-white overflow-hidden",
        "transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] hover:-translate-y-0.5",
        "opacity-0 animate-fade-in"
      )}
      style={{ animationDelay: `${index * 60}ms`, animationFillMode: "forwards" }}
    >
      {/* Image Placeholder */}
      <div
        className={cn(
          "h-32 bg-gradient-to-br flex items-center justify-center relative",
          post.gradient
        )}
      >
        {post.type === "video" ? (
          <Play className="w-8 h-8 text-white/80" />
        ) : post.type === "carousel" ? (
          <Image className="w-8 h-8 text-white/80" />
        ) : (
          <Image className="w-8 h-8 text-white/80" />
        )}
        {/* Platform Badge */}
        <Badge
          className={cn(
            "absolute top-2 left-2 text-[10px] font-semibold border-0",
            colors.badge
          )}
        >
          {post.platform === "instagram" && "Instagram"}
          {post.platform === "facebook" && "Facebook"}
          {post.platform === "tiktok" && "TikTok"}
          {post.platform === "twitter" && "Twitter"}
        </Badge>
        {/* Type Badge */}
        <Badge
          variant="outline"
          className="absolute top-2 right-2 text-[10px] font-medium bg-white/80 border-white/40"
        >
          {post.type === "carousel" && "Karusel"}
          {post.type === "video" && "Video"}
          {post.type === "image" && "Görsel"}
          {post.type === "story" && "Hikaye"}
        </Badge>
      </div>

      {/* Content */}
      <div className="p-3.5">
        <h4 className="text-sm font-semibold text-[#0F172A] truncate mb-1">
          {post.title}
        </h4>
        <p className="text-xs text-[#94A3B8] mb-3">{post.date}</p>

        {/* Stats */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <Heart className="w-3.5 h-3.5 text-[#EC4899]" />
            <span className="text-xs text-[#475569]">{formatNumber(post.likes)}</span>
          </div>
          <div className="flex items-center gap-1">
            <MessageCircle className="w-3.5 h-3.5 text-[#3B82F6]" />
            <span className="text-xs text-[#475569]">{formatNumber(post.comments)}</span>
          </div>
          <div className="flex items-center gap-1">
            <Share2 className="w-3.5 h-3.5 text-[#8B5CF6]" />
            <span className="text-xs text-[#475569]">{formatNumber(post.shares)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Competitor Row Component ────────────────────────────

function CompetitorRow({ competitor, index }: { competitor: Competitor; index: number }) {
  const TrendIcon = competitor.changeType === "up" ? TrendingUp : TrendingDown;

  return (
    <div
      className={cn(
        "flex items-center justify-between p-4 rounded-xl border border-[#E2E8F0] bg-white",
        "transition-all duration-200 hover:shadow-sm",
        "opacity-0 animate-fade-in"
      )}
      style={{ animationDelay: `${index * 80}ms`, animationFillMode: "forwards" }}
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-[#F1F5F9] text-[#475569] font-bold text-sm">
          {competitor.name.charAt(0)}
        </div>
        <div>
          <p className="text-sm font-semibold text-[#0F172A]">{competitor.name}</p>
          <p className="text-xs text-[#94A3B8]">{competitor.handle}</p>
        </div>
      </div>

      <div className="flex items-center gap-8">
        <div className="text-center">
          <p className="text-sm font-semibold text-[#0F172A]">
            {competitor.followers.toLocaleString("tr-TR")}
          </p>
          <p className="text-[11px] text-[#94A3B8]">Takipçi</p>
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-[#0F172A]">%{competitor.engagementRate}</p>
          <p className="text-[11px] text-[#94A3B8]">Etkileşim</p>
        </div>
        <div
          className={cn(
            "flex items-center gap-1 text-xs font-semibold rounded-full px-2 py-0.5",
            competitor.changeType === "up"
              ? "text-[#059669] bg-[#D1FAE5]"
              : "text-[#DC2626] bg-[#FEE2E2]"
          )}
        >
          <TrendIcon className="w-3 h-3" />
          {competitor.changeType === "up" ? "+" : "-"}
          {Math.abs(competitor.change)}%
        </div>
        <Button variant="ghost" size="sm" className="h-8 text-xs text-[#475569] hover:text-[#0F172A]">
          <ArrowUpRight className="w-3.5 h-3.5 mr-1" />
          Detay
        </Button>
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────

export default function SocialMediaPage() {
  const [activeTab, setActiveTab] = useState("published");

  return (
    <div className="space-y-6">
      {/* ═══ Page Header ═══════════════════════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Sosyal Medya</h1>
          <p className="text-sm text-[#475569] mt-0.5">
            Tüm sosyal medya hesaplarınızı tek yerden yönetin
          </p>
        </div>
        <Button className="h-9 px-4 bg-[#7C3AED] hover:bg-[#6D28D9] text-white text-sm font-medium">
          <Plus className="w-4 h-4 mr-2" />
          Yeni Gönderi
        </Button>
      </div>

      {/* ═══ Platform Account Cards ════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        {mockAccounts.map((account, index) => (
          <AccountCard key={account.id} account={account} index={index} />
        ))}
      </div>

      {/* ═══ Posts Grid + Engagement Chart ═════════════ */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Posts Grid */}
        <Card className="xl:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-[#0F172A]">İçerik Yönetimi</CardTitle>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="w-4 h-4 text-[#94A3B8]" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="bg-[#F1F5F9] p-0.5 rounded-lg mb-4">
                <TabsTrigger
                  value="published"
                  className="text-xs font-medium rounded-md data-[state=active]:bg-white data-[state=active]:text-[#0F172A] data-[state=active]:shadow-sm text-[#475569] px-4 py-1.5"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                  Yayınlanan
                </TabsTrigger>
                <TabsTrigger
                  value="scheduled"
                  className="text-xs font-medium rounded-md data-[state=active]:bg-white data-[state=active]:text-[#0F172A] data-[state=active]:shadow-sm text-[#475569] px-4 py-1.5"
                >
                  <Clock className="w-3.5 h-3.5 mr-1.5" />
                  Zamanlanan
                </TabsTrigger>
                <TabsTrigger
                  value="drafts"
                  className="text-xs font-medium rounded-md data-[state=active]:bg-white data-[state=active]:text-[#0F172A] data-[state=active]:shadow-sm text-[#475569] px-4 py-1.5"
                >
                  <FileEdit className="w-3.5 h-3.5 mr-1.5" />
                  Taslaklar
                </TabsTrigger>
              </TabsList>

              <TabsContent value="published" className="mt-0">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {mockPublishedPosts.map((post, index) => (
                    <PostCard key={post.id} post={post} index={index} />
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="scheduled" className="mt-0">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {mockScheduledPosts.map((post, index) => (
                    <PostCard key={post.id} post={post} index={index} />
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="drafts" className="mt-0">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {mockDraftPosts.map((post, index) => (
                    <PostCard key={post.id} post={post} index={index} />
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Engagement Chart */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-bold text-[#0F172A]">Etkileşim Analizi</CardTitle>
            <p className="text-xs text-[#94A3B8]">Son 7 gün etkileşim istatistikleri</p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={mockEngagementData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="likesGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#EC4899" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#EC4899" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="commentsGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="sharesGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 11, fill: "#94A3B8" }}
                  axisLine={{ stroke: "#E2E8F0" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#94A3B8" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<EngagementTooltip />} />
                <Area
                  type="monotone"
                  dataKey="likes"
                  stroke="#EC4899"
                  strokeWidth={2}
                  fill="url(#likesGradient)"
                  name="likes"
                />
                <Area
                  type="monotone"
                  dataKey="comments"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  fill="url(#commentsGradient)"
                  name="comments"
                />
                <Area
                  type="monotone"
                  dataKey="shares"
                  stroke="#8B5CF6"
                  strokeWidth={2}
                  fill="url(#sharesGradient)"
                  name="shares"
                />
              </AreaChart>
            </ResponsiveContainer>

            {/* Legend */}
            <div className="flex items-center justify-center gap-5 mt-3 pt-3 border-t border-[#F1F5F9]">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#EC4899]" />
                <span className="text-xs text-[#475569]">Beğeni</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#3B82F6]" />
                <span className="text-xs text-[#475569]">Yorum</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#8B5CF6]" />
                <span className="text-xs text-[#475569]">Paylaşım</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ═══ Competitor Tracking ═══════════════════════ */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg font-bold text-[#0F172A]">Rakip Takibi</CardTitle>
              <p className="text-xs text-[#94A3B8] mt-0.5">
                Rakiplerinizin sosyal medya performansını karşılaştırın
              </p>
            </div>
            <Button variant="outline" size="sm" className="h-8 text-xs border-[#E2E8F0]">
              <Globe className="w-3.5 h-3.5 mr-1.5" />
              Rakip Ekle
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {mockCompetitors.map((competitor, index) => (
            <CompetitorRow key={competitor.id} competitor={competitor} index={index} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
