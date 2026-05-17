import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, Users, BarChart3, Megaphone, Settings, Briefcase, HelpCircle, MessageSquare, Building2, FileText, Zap, Globe } from 'lucide-react'

/* ─── pages ─── */
import { OperatorWorkspace } from './pages/OperatorWorkspace'
import { ReportsPage } from './pages/ReportsPage'
import { FollowersPage } from './pages/FollowersPage'

/* ─── simple placeholder pages ─── */
function DashboardPage() {
  return <OperatorWorkspace />
}

function SocialPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Sosyal Medya Yönetimi</h1>
      <p className="text-gray-600 mb-4">Sosyal medya hesaplarınızı yönetin.</p>
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <h3 className="font-semibold mb-2">Hesaplar</h3>
        <p className="text-sm text-gray-500 mb-2">Henüz hesap eklenmemiş.</p>
        <button className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 text-sm">Hesap Ekle</button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4"><h4 className="font-semibold">Toplam Takipçi</h4><p className="text-2xl font-bold text-blue-600">0</p></div>
        <div className="bg-white rounded-lg shadow p-4"><h4 className="font-semibold">Etkileşim Oranı</h4><p className="text-2xl font-bold text-green-600">0%</p></div>
        <div className="bg-white rounded-lg shadow p-4"><h4 className="font-semibold">Gönderi Sayısı</h4><p className="text-2xl font-bold text-purple-600">0</p></div>
      </div>
    </div>
  )
}

function AdsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Reklam Yönetimi</h1>
      <p className="text-gray-600 mb-4">Reklam kampanyalarınızı yönetin.</p>
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <h3 className="font-semibold mb-2">Kampanyalar</h3>
        <p className="text-sm text-gray-500 mb-2">Henüz kampanya oluşturulmamış.</p>
        <button className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 text-sm">Kampanya Oluştur</button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4"><h4 className="font-semibold">Aktif Kampanya</h4><p className="text-2xl font-bold text-green-600">0</p></div>
        <div className="bg-white rounded-lg shadow p-4"><h4 className="font-semibold">Toplam Harcama</h4><p className="text-2xl font-bold text-red-600">₼0</p></div>
        <div className="bg-white rounded-lg shadow p-4"><h4 className="font-semibold">Dönüşüm</h4><p className="text-2xl font-bold text-blue-600">0%</p></div>
      </div>
    </div>
  )
}

function AnalyticsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Analitik</h1>
      <p className="text-gray-600">Veri analizi ve raporlama.</p>
      <ReportsPage />
    </div>
  )
}

function SettingsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Ayarlar</h1>
      <p className="text-gray-600">Sistem ayarlarını yapılandırın.</p>
    </div>
  )
}

function BillingPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Fatura Yönetimi</h1>
      <p className="text-gray-600">Fatura ve ödeme yönetimi.</p>
    </div>
  )
}

function SupportPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Destek</h1>
      <p className="text-gray-600">Destek talepleri ve yardım.</p>
    </div>
  )
}

/* ─── sidebar nav items ─── */
const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/social', label: 'Sosyal Medya', icon: Globe },
  { to: '/ads', label: 'Reklam Yönetimi', icon: Megaphone },
  { to: '/followers', label: 'Takipçiler', icon: Users },
  { to: '/analytics', label: 'Analitik', icon: BarChart3 },
  { to: '/reports', label: 'Raporlar', icon: FileText },
  { to: '/billing', label: 'Fatura', icon: Briefcase },
  { to: '/support', label: 'Destek', icon: HelpCircle },
  { to: '/settings', label: 'Ayarlar', icon: Settings },
]

/* ─── layout ─── */
function Layout() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen bg-gray-50">
      {/* sidebar */}
      <aside className={`${collapsed ? 'w-16' : 'w-56'} bg-slate-900 text-white flex flex-col transition-all duration-200`}>
        <div className="p-4 flex items-center gap-2 border-b border-slate-700">
          <Zap className="w-6 h-6 text-blue-400" />
          {!collapsed && <span className="font-bold text-lg">NexusAI</span>}
        </div>

        <nav className="flex-1 py-4">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 mx-2 rounded-lg transition-colors ${
                  isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                }`
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span className="text-sm">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-4 text-slate-400 hover:text-white border-t border-slate-700 text-center text-xs"
        >
          {collapsed ? '>>' : '<< Menüyü Daralt'}
        </button>
      </aside>

      {/* main content */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/social" element={<SocialPage />} />
          <Route path="/ads" element={<AdsPage />} />
          <Route path="/followers" element={<FollowersPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/billing" element={<BillingPage />} />
          <Route path="/support" element={<SupportPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  )
}
