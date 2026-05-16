import { HashRouter, Routes, Route, useParams, useNavigate } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster } from "@/components/ui/sonner";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import BranchesPage from "@/pages/BranchesPage";
import SocialMediaPage from "@/pages/SocialMediaPage";
import AdsPage from "@/pages/AdsPage";
import CreativeStudioPage from "@/pages/CreativeStudioPage";
import ChatInboxPage from "@/pages/ChatInboxPage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import AIReportsPage from "@/pages/AIReportsPage";
import SettingsPage from "@/pages/SettingsPage";
import UsersPage from "@/pages/UsersPage";
import ErrorPage from "@/pages/ErrorPage";

/**
 * App - Root component with ErrorBoundary, Toast notifications,
 * and routing setup with error pages.
 */
export default function App() {
  return (
    <ErrorBoundary>
      <HashRouter>
        {/* Toast notifications - positioned top-right */}
        <Toaster
          position="top-right"
          richColors
          closeButton
          toastOptions={{
            duration: 4000,
          }}
        />

        <Routes>
          {/* Error pages (no layout wrapper) */}
          <Route path="/error/:code" element={<ErrorPageRedirect />} />

          {/* Main app routes wrapped in Layout */}
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
            {/* Catch-all for unknown routes inside layout */}
            <Route path="*" element={<ErrorPage code={404} />} />
          </Route>
        </Routes>
      </HashRouter>
    </ErrorBoundary>
  );
}

/**
 * ErrorPageRedirect - Reads error code from URL params
 * and renders the appropriate error page.
 */
function ErrorPageRedirect() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();

  const errorCode = (() => {
    const num = parseInt(code || "", 10);
    if ([403, 404, 500].includes(num)) return num as 403 | 404 | 500;
    return 404;
  })();

  return (
    <Layout>
      <ErrorPage
        code={errorCode}
        onBack={() => navigate(-1)}
        onHome={() => navigate("/dashboard")}
        onRetry={() => window.location.reload()}
      />
    </Layout>
  );
}
