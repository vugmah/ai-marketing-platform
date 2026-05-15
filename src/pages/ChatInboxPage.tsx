import { useState, useRef, useEffect } from "react";
import {
  Instagram,
  Facebook,
  Send,
  Paperclip,
  Mic,
  Smile,
  Search,
  Filter,
  MoreHorizontal,
  Tag,
  AlertTriangle,
  ArrowRightLeft,
  XCircle,
  Bot,
  User,
  CheckCheck,
  Sparkles,
  ChevronDown,
  Globe,
  Volume2,
  MessageSquare,
  Phone,
  Mail,
  Clock,
  CircleDot,
  Wifi,
  WifiOff,
  PauseCircle,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────

interface Conversation {
  id: string;
  name: string;
  avatar: string;
  channel: "Instagram" | "Facebook" | "Telegram" | "WhatsApp" | "Web";
  lastMessage: string;
  time: string;
  unread: number;
  status: "open" | "closed" | "pending";
  email: string;
  phone: string;
  tags: string[];
}

interface Message {
  id: string;
  sender: "customer" | "ai" | "agent";
  content: string;
  time: string;
  read: boolean;
}

// ─── Mock Data ───────────────────────────────────────────

const conversations: Conversation[] = [
  { id: "conv1", name: "Aygün Məmmədova", avatar: "AM", channel: "Instagram", lastMessage: "Bugünkü menünüzde neler var? Özel bir kampanya var mı?", time: "2 dk", unread: 2, status: "open", email: "aygun@email.com", phone: "+994 55 123 45 67", tags: ["Soru", "Menü"] },
  { id: "conv2", name: "Elçin Quliyev", avatar: "EQ", channel: "WhatsApp", lastMessage: "Siparişim hala gelmedi, neden gecikti?", time: "15 dk", unread: 1, status: "open", email: "elcin@email.com", phone: "+994 50 987 65 43", tags: ["Şikayet", "Sipariş"] },
  { id: "conv3", name: "Nigar Həsənli", avatar: "NH", channel: "Facebook", lastMessage: "Teşekkürler, harika hizmet!", time: "1 saat", unread: 0, status: "closed", email: "nigar@email.com", phone: "+994 70 555 44 33", tags: ["Teşekkür"] },
  { id: "conv4", name: "Rəşad Əliyev", avatar: "RƏ", channel: "Telegram", lastMessage: "Rezervasyon yapmak istiyorum, 4 kişilik masa.", time: "2 saat", unread: 0, status: "pending", email: "reshad@email.com", phone: "+994 55 777 88 99", tags: ["Rezervasyon"] },
  { id: "conv5", name: "Leyla İbrahimova", avatar: "Lİ", channel: "Web", lastMessage: "Şubenizin çalışma saatleri nedir?", time: "3 saat", unread: 0, status: "closed", email: "leyla@email.com", phone: "+994 50 222 33 44", tags: ["Bilgi"] },
  { id: "conv6", name: "Tural Mənsimov", avatar: "TM", channel: "Instagram", lastMessage: "Kampanya ne zamana kadar geçerli olacak?", time: "5 saat", unread: 3, status: "open", email: "tural@email.com", phone: "+994 70 111 22 33", tags: ["Kampanya"] },
];

const messagesData: Record<string, Message[]> = {
  conv1: [
    { id: "m1", sender: "customer", content: "Merhaba, bugünkü menünüzde neler var? Özel bir kampanya var mı?", time: "14:20", read: true },
    { id: "m2", sender: "ai", content: "Merhaba! Bugün özel yaz menümüz aktif. Izgara levrek, taze salatalar ve ev limonatası ile harika bir öğle yemeği sizi bekliyor. Hafta sonuna özel %15 indirim kampanyamız da var!", time: "14:21", read: true },
    { id: "m3", sender: "customer", content: "Harika! Levrek fiyatı ne kadar?", time: "14:23", read: true },
    { id: "m4", sender: "customer", content: "Ve indirimden nasıl faydalanabilirim?", time: "14:25", read: false },
  ],
  conv2: [
    { id: "m1", sender: "customer", content: "Siparişim hala gelmedi, neden gecikti?", time: "13:05", read: true },
    { id: "m2", sender: "ai", content: "Özür dileriz, siparişinizde gecikme yaşandığını duyduk. Sipariş numaranızı paylaşabilir misiniz? Size en kısa sürede yardımcı olacağız.", time: "13:06", read: true },
    { id: "m3", sender: "agent", content: "Merhaba, sipariş #4823 için kuryemiz yolda. Tahmini varış süresi 10 dakika. Anlayışınız için teşekkürler.", time: "13:15", read: false },
  ],
  conv3: [
    { id: "m1", sender: "customer", content: "Dün akşam şubenize gittik, gerçekten çok güzeldi!", time: "11:30", read: true },
    { id: "m2", sender: "ai", content: "Çok teşekkür ederiz! Sizi tekrar aramızda görmekten mutluluk duyarız. Bir dahaki ziyaretinizde %10 indirim kazanabilirsiniz!", time: "11:31", read: true },
    { id: "m3", sender: "customer", content: "Teşekkürler, harika hizmet!", time: "11:35", read: true },
  ],
  conv4: [
    { id: "m1", sender: "customer", content: "Rezervasyon yapmak istiyorum, 4 kişilik masa.", time: "10:00", read: true },
    { id: "m2", sender: "ai", content: "Tabii, size yardımcı olabilirim. Hangi tarih ve saat için rezervasyon yaptırmak istersiniz?", time: "10:01", read: true },
    { id: "m3", sender: "customer", content: "Yarın akşam 20:00 için.", time: "10:05", read: true },
  ],
  conv5: [
    { id: "m1", sender: "customer", content: "Şubenizin çalışma saatleri nedir?", time: "09:15", read: true },
    { id: "m2", sender: "ai", content: "Şubemiz hafta içi 08:00 - 23:00, hafta sonu ise 09:00 - 00:00 saatleri arasında hizmet vermektedir. Mutlu saat (happy hour) 16:00 - 19:00 arasındadır!", time: "09:16", read: true },
    { id: "m3", sender: "customer", content: "Teşekkür ederim.", time: "09:20", read: true },
  ],
  conv6: [
    { id: "m1", sender: "customer", content: "Instagram\'da gördüğüm kampanya ne zamana kadar geçerli olacak?", time: "08:30", read: true },
    { id: "m2", sender: "ai", content: "Yaz Sezonu Kampanyamız 31 Temmuz 2024 tarihine kadar geçerlidir. Tüm menülerde %15 indirim fırsatını kaçırmayın!", time: "08:31", read: true },
    { id: "m3", sender: "customer", content: "Online sipariş verebilir miyim?", time: "08:35", read: false },
    { id: "m4", sender: "customer", content: "Ve kampanya ne zamana kadar sürecek tekrar soruyorum.", time: "08:40", read: false },
  ],
};

// ─── Channel Helpers ─────────────────────────────────────

function getChannelBadge(channel: Conversation["channel"]) {
  const styles = {
    Instagram: "bg-pink-100 text-pink-600 hover:bg-pink-100",
    Facebook: "bg-blue-100 text-blue-600 hover:bg-blue-100",
    Telegram: "bg-sky-100 text-sky-600 hover:bg-sky-100",
    WhatsApp: "bg-green-100 text-green-600 hover:bg-green-100",
    Web: "bg-indigo-100 text-indigo-600 hover:bg-indigo-100",
  };
  return styles[channel];
}

function getChannelIcon(channel: Conversation["channel"]) {
  switch (channel) {
    case "Instagram": return <Instagram className="w-3.5 h-3.5" />;
    case "Facebook": return <Facebook className="w-3.5 h-3.5" />;
    case "Telegram": return <Send className="w-3.5 h-3.5" />;
    case "WhatsApp": return <MessageSquare className="w-3.5 h-3.5" />;
    case "Web": return <Globe className="w-3.5 h-3.5" />;
  }
}

function getStatusBadge(status: Conversation["status"]) {
  switch (status) {
    case "open": return { label: "Açık", className: "bg-[#D1FAE5] text-[#059669] hover:bg-[#D1FAE5]", icon: CircleDot };
    case "closed": return { label: "Kapalı", className: "bg-[#E2E8F0] text-[#475569] hover:bg-[#E2E8F0]", icon: CheckCheck };
    case "pending": return { label: "Beklemede", className: "bg-[#FEF3C7] text-[#D97706] hover:bg-[#FEF3C7]", icon: PauseCircle };
  }
}

function getStatusDot(status: Conversation["status"]) {
  switch (status) {
    case "open": return "bg-[#059669]";
    case "closed": return "bg-[#94A3B8]";
    case "pending": return "bg-[#D97706]";
  }
}

// ─── Typing Indicator ────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-2.5 bg-[#F5F3FF] rounded-2xl rounded-tl-sm w-fit">
      <Bot className="w-3.5 h-3.5 text-[#7C3AED] mr-1" />
      <span className="w-1.5 h-1.5 rounded-full bg-[#7C3AED] animate-bounce" style={{ animationDelay: "0ms" }} />
      <span className="w-1.5 h-1.5 rounded-full bg-[#7C3AED] animate-bounce" style={{ animationDelay: "150ms" }} />
      <span className="w-1.5 h-1.5 rounded-full bg-[#7C3AED] animate-bounce" style={{ animationDelay: "300ms" }} />
      <span className="text-[10px] text-[#7C3AED] ml-1">AI yazıyor...</span>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────

export default function ChatInboxPage() {
  const [selectedConv, setSelectedConv] = useState<string>("conv1");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeChannel, setActiveChannel] = useState("all");
  const [aiAutoReply, setAiAutoReply] = useState(true);
  const [messageInput, setMessageInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const selectedConversation = conversations.find((c) => c.id === selectedConv);
  const currentMessages = messagesData[selectedConv] || [];

  const filteredConversations = conversations.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.lastMessage.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesChannel = activeChannel === "all" || c.channel.toLowerCase() === activeChannel;
    return matchesSearch && matchesChannel;
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentMessages, isTyping]);

  const handleSendMessage = () => {
    if (!messageInput.trim()) return;
    setMessageInput("");
    setIsTyping(true);
    setTimeout(() => setIsTyping(false), 2000);
  };

  return (
    <div className="space-y-0 -mx-6 -my-6">
      {/* ═══ Page Header ════════════════════════════════════ */}
      <div className="px-6 pt-6 pb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 opacity-0 animate-fade-in">
        <div>
          <h1 className="text-[28px] font-bold text-[#0F172A] tracking-tight">Gelen Kutusu</h1>
          <p className="text-sm text-[#475569] mt-0.5">Tüm kanallardan gelen mesajları yönetin</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#EDE9FE] rounded-full">
            <Bot className="w-4 h-4 text-[#7C3AED]" />
            <span className="text-sm text-[#7C3AED] font-medium">AI Oto-Yanıt</span>
            <Switch checked={aiAutoReply} onCheckedChange={setAiAutoReply} className="data-[state=checked]:bg-[#7C3AED]" />
          </div>
        </div>
      </div>

      {/* ═══ 3-Panel Layout ═════════════════════════════════ */}
      <div className="flex h-[calc(100vh-180px)] border-t border-[#E2E8F0] opacity-0 animate-fade-in" style={{ animationDelay: "100ms", animationFillMode: "forwards" }}>
        {/* ═══ Sol Panel: Konuşma Listesi ═════════════════ */}
        <div className="w-[340px] min-w-[340px] border-r border-[#E2E8F0] bg-white flex flex-col">
          {/* Channel Tabs */}
          <div className="p-3 border-b border-[#E2E8F0]">
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
              <Input placeholder="Konuşma ara..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-9 h-9 text-sm" />
            </div>
            <div className="flex gap-1 overflow-x-auto">
              {[
                { key: "all", label: "Tümü", count: conversations.length },
                { key: "instagram", label: "Instagram", count: conversations.filter((c) => c.channel === "Instagram").reduce((s, c) => s + c.unread, 0) },
                { key: "facebook", label: "Facebook", count: conversations.filter((c) => c.channel === "Facebook").reduce((s, c) => s + c.unread, 0) },
                { key: "telegram", label: "Telegram", count: conversations.filter((c) => c.channel === "Telegram").reduce((s, c) => s + c.unread, 0) },
                { key: "whatsapp", label: "WhatsApp", count: conversations.filter((c) => c.channel === "WhatsApp").reduce((s, c) => s + c.unread, 0) },
                { key: "web", label: "Web", count: conversations.filter((c) => c.channel === "Web").reduce((s, c) => s + c.unread, 0) },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveChannel(tab.key)}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors",
                    activeChannel === tab.key ? "bg-[#0F172A] text-white" : "bg-[#F1F5F9] text-[#475569] hover:bg-[#E2E8F0]"
                  )}
                >
                  {tab.key !== "all" && getChannelIcon(tab.key.charAt(0).toUpperCase() + tab.key.slice(1) as Conversation["channel"])}
                  {tab.label}
                  {tab.count > 0 && (
                    <span className={cn("ml-0.5 text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center", activeChannel === tab.key ? "bg-white text-[#0F172A]" : "bg-[#DC2626] text-white")}>
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Conversation List */}
          <div className="flex-1 overflow-y-auto">
            {filteredConversations.map((conv) => {
              const status = getStatusBadge(conv.status);
              const StatusIcon = status.icon;
              const isSelected = selectedConv === conv.id;
              return (
                <button
                  key={conv.id}
                  onClick={() => setSelectedConv(conv.id)}
                  className={cn(
                    "flex items-start gap-3 w-full px-4 py-3 text-left border-b border-[#F1F5F9] transition-colors",
                    isSelected ? "bg-[#F5F3FF] border-l-[3px] border-l-[#7C3AED]" : "hover:bg-[#F8FAFC] border-l-[3px] border-l-transparent"
                  )}
                >
                  <div className="relative shrink-0">
                    <Avatar className="w-10 h-10">
                      <AvatarFallback className="bg-[#7C3AED] text-white text-sm font-semibold">{conv.avatar}</AvatarFallback>
                    </Avatar>
                    <div className={cn("absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white", getStatusDot(conv.status))} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className={cn("text-sm font-semibold truncate", isSelected ? "text-[#7C3AED]" : "text-[#0F172A]")}>{conv.name}</span>
                      <span className="text-[11px] text-[#94A3B8] shrink-0">{conv.time}</span>
                    </div>
                    <p className="text-xs text-[#475569] line-clamp-2 leading-relaxed">{conv.lastMessage}</p>
                    <div className="flex items-center gap-2 mt-1.5">
                      <Badge className={cn("text-[10px] h-4 px-1 font-medium", getChannelBadge(conv.channel))}>
                        {conv.channel}
                      </Badge>
                      {conv.unread > 0 && (
                        <span className="flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-[#DC2626] text-white text-[10px] font-bold">
                          {conv.unread}
                        </span>
                      )}
                      <Badge className={cn("text-[10px] h-4 px-1", status.className)}>
                        <StatusIcon className="w-2.5 h-2.5 mr-0.5" />
                        {status.label}
                      </Badge>
                    </div>
                  </div>
                </button>
              );
            })}
            {filteredConversations.length === 0 && (
              <div className="text-center py-12 text-[#94A3B8]">
                <Search className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">Sonuç bulunamadı</p>
              </div>
            )}
          </div>
        </div>

        {/* ═══ Orta Panel: Sohbet Penceresi ═════════════════ */}
        <div className="flex-1 flex flex-col bg-[#F8FAFC]">
          {/* Chat Header */}
          {selectedConversation && (
            <div className="flex items-center justify-between px-5 py-3 bg-white border-b border-[#E2E8F0]">
              <div className="flex items-center gap-3">
                <Avatar className="w-9 h-9">
                  <AvatarFallback className="bg-[#7C3AED] text-white text-xs font-semibold">{selectedConversation.avatar}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="text-sm font-semibold text-[#0F172A]">{selectedConversation.name}</p>
                  <div className="flex items-center gap-1.5">
                    <div className={cn("w-1.5 h-1.5 rounded-full", getStatusDot(selectedConversation.status))} />
                    <span className="text-[11px] text-[#94A3B8]">{selectedConversation.channel} · {getStatusBadge(selectedConversation.status).label}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Tag className="w-4 h-4 text-[#475569]" />
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreHorizontal className="w-4 h-4 text-[#475569]" />
                </Button>
              </div>
            </div>
          )}

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {currentMessages.map((msg) => {
              if (msg.sender === "agent") {
                return (
                  <div key={msg.id} className="flex items-end justify-end gap-2">
                    <div className="flex flex-col items-end max-w-[70%]">
                      <div className="px-4 py-2.5 bg-[#2563EB] text-white rounded-2xl rounded-tr-sm">
                        <p className="text-sm leading-relaxed">{msg.content}</p>
                      </div>
                      <div className="flex items-center gap-1 mt-1">
                        <span className="text-[10px] text-[#94A3B8]">{msg.time}</span>
                        {msg.read ? <CheckCheck className="w-3 h-3 text-[#2563EB]" /> : <CheckCheck className="w-3 h-3 text-[#94A3B8]" />}
                      </div>
                    </div>
                    <Avatar className="w-7 h-7 shrink-0">
                      <AvatarFallback className="bg-[#2563EB] text-white text-[10px]">VM</AvatarFallback>
                    </Avatar>
                  </div>
                );
              }

              if (msg.sender === "ai") {
                return (
                  <div key={msg.id} className="flex items-end justify-start gap-2">
                    <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[#EDE9FE] shrink-0">
                      <Bot className="w-4 h-4 text-[#7C3AED]" />
                    </div>
                    <div className="flex flex-col items-start max-w-[70%]">
                      <div className="px-4 py-2.5 bg-[#F5F3FF] text-[#0F172A] rounded-2xl rounded-tl-sm border border-[#EDE9FE]">
                        <div className="flex items-center gap-1 mb-1">
                          <Badge className="bg-[#EDE9FE] text-[#7C3AED] hover:bg-[#EDE9FE] text-[9px] h-4 px-1 font-semibold">AI</Badge>
                        </div>
                        <p className="text-sm leading-relaxed">{msg.content}</p>
                      </div>
                      <span className="text-[10px] text-[#94A3B8] mt-1">{msg.time}</span>
                    </div>
                  </div>
                );
              }

              return (
                <div key={msg.id} className="flex items-end justify-start gap-2">
                  <Avatar className="w-7 h-7 shrink-0">
                    <AvatarFallback className="bg-[#0F172A] text-white text-[10px]">{selectedConversation?.avatar}</AvatarFallback>
                  </Avatar>
                  <div className="flex flex-col items-start max-w-[70%]">
                    <div className="px-4 py-2.5 bg-white text-[#0F172A] rounded-2xl rounded-tl-sm border border-[#E2E8F0] shadow-sm">
                      <p className="text-sm leading-relaxed">{msg.content}</p>
                    </div>
                    <span className="text-[10px] text-[#94A3B8] mt-1">{msg.time}</span>
                  </div>
                </div>
              );
            })}

            {isTyping && (
              <div className="flex items-end justify-start gap-2">
                <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[#EDE9FE] shrink-0">
                  <Bot className="w-4 h-4 text-[#7C3AED]" />
                </div>
                <TypingIndicator />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Message Input */}
          <div className="px-5 py-3 bg-white border-t border-[#E2E8F0]">
            <div className="flex items-end gap-2">
              <div className="flex items-center gap-1 mr-1">
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Smile className="w-4 h-4 text-[#94A3B8]" />
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Paperclip className="w-4 h-4 text-[#94A3B8]" />
                </Button>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <Mic className="w-4 h-4 text-[#94A3B8]" />
                </Button>
              </div>
              <Textarea
                placeholder="Mesaj yazın..."
                value={messageInput}
                onChange={(e) => setMessageInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }}
                className="flex-1 min-h-[40px] max-h-[100px] resize-none text-sm"
              />
              <Button
                onClick={handleSendMessage}
                disabled={!messageInput.trim()}
                className="bg-[#2563EB] hover:bg-[#1D4ED8] text-white h-9 w-9 p-0 shrink-0"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* ═══ Sağ Panel: Bilgi Paneli ════════════════════ */}
        <div className="w-[320px] min-w-[320px] border-l border-[#E2E8F0] bg-white flex flex-col overflow-y-auto">
          {selectedConversation && (
            <>
              {/* Müşteri Profili */}
              <div className="p-5 border-b border-[#E2E8F0] text-center">
                <Avatar className="w-16 h-16 mx-auto mb-3">
                  <AvatarFallback className="bg-[#7C3AED] text-white text-xl font-semibold">{selectedConversation.avatar}</AvatarFallback>
                </Avatar>
                <h3 className="text-base font-semibold text-[#0F172A]">{selectedConversation.name}</h3>
                <div className="flex items-center justify-center gap-1.5 mt-1">
                  <Mail className="w-3.5 h-3.5 text-[#94A3B8]" />
                  <span className="text-xs text-[#475569]">{selectedConversation.email}</span>
                </div>
                <div className="flex items-center justify-center gap-1.5 mt-1">
                  <Phone className="w-3.5 h-3.5 text-[#94A3B8]" />
                  <span className="text-xs text-[#475569]">{selectedConversation.phone}</span>
                </div>
              </div>

              {/* Konuşma Detayları */}
              <div className="p-4 border-b border-[#E2E8F0]">
                <h4 className="text-xs font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">Konuşma Detayları</h4>
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getChannelIcon(selectedConversation.channel)}
                      <span className="text-sm text-[#475569]">Kanal</span>
                    </div>
                    <Badge className={cn("text-[11px]", getChannelBadge(selectedConversation.channel))}>
                      {selectedConversation.channel}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CircleDot className="w-4 h-4 text-[#94A3B8]" />
                      <span className="text-sm text-[#475569]">Durum</span>
                    </div>
                    <Badge className={cn("text-[11px]", getStatusBadge(selectedConversation.status).className)}>
                      {getStatusBadge(selectedConversation.status).label}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-[#94A3B8]" />
                      <span className="text-sm text-[#475569]">Son Aktivite</span>
                    </div>
                    <span className="text-sm font-medium text-[#0F172A]">{selectedConversation.time} önce</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <User className="w-4 h-4 text-[#94A3B8]" />
                      <span className="text-sm text-[#475569]">Atanan</span>
                    </div>
                    <span className="text-sm font-medium text-[#0F172A]">Vüqar Məmmədov</span>
                  </div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 shrink-0">
                      <Tag className="w-4 h-4 text-[#94A3B8]" />
                      <span className="text-sm text-[#475569]">Etiketler</span>
                    </div>
                    <div className="flex flex-wrap gap-1 justify-end">
                      {selectedConversation.tags.map((tag) => (
                        <Badge key={tag} variant="outline" className="text-[10px] h-5 border-[#E2E8F0] text-[#475569]">{tag}</Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* AI Ayarları */}
              <div className="p-4 border-b border-[#E2E8F0]">
                <h4 className="text-xs font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">AI Ayarları</h4>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Bot className="w-4 h-4 text-[#7C3AED]" />
                      <span className="text-sm text-[#475569]">Oto-Yanıt</span>
                    </div>
                    <Switch defaultChecked className="data-[state=checked]:bg-[#7C3AED]" />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Globe className="w-4 h-4 text-[#475569]" />
                      <span className="text-sm text-[#475569]">Yanıt Dili</span>
                    </div>
                    <select className="text-xs bg-[#F8FAFC] border border-[#E2E8F0] rounded-md px-2 py-1 text-[#0F172A] outline-none focus:ring-2 focus:ring-[#7C3AED]">
                      <option>Türkçe</option>
                      <option>Azərbaycan</option>
                      <option>English</option>
                      <option>Русский</option>
                    </select>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Volume2 className="w-4 h-4 text-[#475569]" />
                      <span className="text-sm text-[#475569]">Ton</span>
                    </div>
                    <select className="text-xs bg-[#F8FAFC] border border-[#E2E8F0] rounded-md px-2 py-1 text-[#0F172A] outline-none focus:ring-2 focus:ring-[#7C3AED]">
                      <option>Dostane</option>
                      <option>Profesyonel</option>
                      <option>Samimi</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Hızlı Eylemler */}
              <div className="p-4">
                <h4 className="text-xs font-semibold text-[#94A3B8] uppercase tracking-wider mb-3">Hızlı Eylemler</h4>
                <div className="space-y-2">
                  <Button variant="outline" size="sm" className="w-full justify-start gap-2 h-9 text-sm">
                    <Tag className="w-4 h-4 text-[#475569]" />
                    Etiket Ekle
                  </Button>
                  <Button variant="outline" size="sm" className="w-full justify-start gap-2 h-9 text-sm">
                    <AlertTriangle className="w-4 h-4 text-[#D97706]" />
                    Şikayet Oluştur
                  </Button>
                  <Button variant="outline" size="sm" className="w-full justify-start gap-2 h-9 text-sm">
                    <ArrowRightLeft className="w-4 h-4 text-[#2563EB]" />
                    Transfer Et
                  </Button>
                  <Button variant="outline" size="sm" className="w-full justify-start gap-2 h-9 text-sm hover:bg-[#FEE2E2] hover:text-[#DC2626] hover:border-[#DC2626]">
                    <XCircle className="w-4 h-4" />
                    Konuşmayı Kapat
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
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
        .animate-fade-in {
          animation: fadeIn 0.5s ease-out;
        }
        .animate-fade-in-up {
          animation: fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes bounce {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-4px); }
        }
        .animate-bounce {
          animation: bounce 0.6s infinite;
        }
      `}</style>
    </div>
  );
}
