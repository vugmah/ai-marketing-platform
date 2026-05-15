import { HashRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import BranchesPage from "./pages/BranchesPage";
import SocialMediaPage from "./pages/SocialMediaPage";
import AdsPage from "./pages/AdsPage";
import CreativeStudioPage from "./pages/CreativeStudioPage";
import ChatInboxPage from "./pages/ChatInboxPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import AIReportsPage from "./pages/AIReportsPage";
import SettingsPage from "./pages/SettingsPage";
import UsersPage from "./pages/UsersPage";

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/branches" element={<BranchesPage />} />
          <Route path="/social-media" element={<SocialMediaPage />} />
          <Route path="/ads" element={<AdsPage />} />
          <Route path="/creative-studio" element={<CreativeStudioPage />} />
          <Route path="/chat-inbox" element={<ChatInboxPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/ai-reports" element={<AIReportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/users" element={<UsersPage />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
