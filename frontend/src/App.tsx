import { useState, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import ProtectedLayout from '@/components/layout/ProtectedLayout'
import Toast from '@/components/ui/Toast'
import CommandPalette from '@/components/ai/CommandPalette'
import AISidebar from '@/components/ai/AISidebar'
import AIQuickAsk from '@/components/ai/AIQuickAsk'
import ErrorBoundary from '@/components/layout/ErrorBoundary'

// 路由级代码分割：各页面/路由模块按需加载，避免单一巨型 chunk（>500kB 警告）
const LoginPage = lazy(() => import('@/pages/auth/LoginPage'))
const PortalPage = lazy(() => import('@/pages/portal/PortalPage'))
const ProfileRoutes = lazy(() => import('@/pages/profile/ProfileRoutes'))
const SalesRoutes = lazy(() => import('@/pages/sales/SalesRoutes'))
const TrainingRoutes = lazy(() => import('@/pages/training/TrainingRoutes'))
const DecisionRoutes = lazy(() => import('@/pages/decision/DecisionRoutes'))
const CollabRoutes = lazy(() => import('@/pages/collab/CollabRoutes'))
const KnowledgeRoutes = lazy(() => import('@/pages/knowledge/KnowledgeRoutes'))
const CollectionRoutes = lazy(() => import('@/pages/collection/CollectionRoutes'))
const NotificationCenterPage = lazy(() => import('@/pages/notification/NotificationCenterPage'))
const CrmPage = lazy(() => import('@/pages/crm/CrmPage'))
const CfmPage = lazy(() => import('@/pages/cfm/CfmPage'))
const ToolsPage = lazy(() => import('@/pages/tools/ToolsPage'))
const PlatformPage = lazy(() => import('@/pages/platform/PlatformPage'))
const MdmPage = lazy(() => import('@/pages/mdm/MdmPage'))
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage'))
const AuditPage = lazy(() => import('@/pages/audit/AuditPage'))
const ObservabilityPage = lazy(() => import('@/pages/observability/ObservabilityPage'))
const AIAssistantPage = lazy(() => import('@/pages/ai/AIAssistantPage'))
const OntologyRoutes = lazy(() => import('@/pages/ontology/OntologyRoutes'))
const ComplianceRoutes = lazy(() => import('@/pages/compliance/ComplianceRoutes'))

function RouteFallback() {
  return (
    <div className="flex items-center justify-center h-full min-h-[40vh] text-sm text-slate-400">
      加载中…
    </div>
  )
}

// 路由感知内容（必须在 BrowserRouter 内部才能使用 useLocation）
function AppContent() {
  const [aiSidebarOpen, setAiSidebarOpen] = useState(false)
  const location = useLocation()
  // /ai 路由已经有完整聊天面板，避免与全局 AISidebar 重复遮挡
  const isAIPage = location.pathname.startsWith('/ai')

  return (
    <>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
        {/* 公开路由 */}
        <Route path="/login" element={<LoginPage />} />

        {/* 受保护路由 */}
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Navigate to="/portal" replace />} />
          <Route path="/portal" element={<PortalPage />} />
          <Route path="/profile/*" element={<ProfileRoutes />} />
          <Route path="/sales/*" element={<SalesRoutes />} />
          <Route path="/training/*" element={<TrainingRoutes />} />
          <Route path="/decision/*" element={<DecisionRoutes />} />
          <Route path="/collab/*" element={<CollabRoutes />} />
          <Route path="/knowledge/*" element={<KnowledgeRoutes />} />
          <Route path="/collection/*" element={<CollectionRoutes />} />
          <Route path="/notification-center" element={<NotificationCenterPage />} />
          <Route path="/crm" element={<CrmPage />} />
          <Route path="/cfm" element={<CfmPage />} />
          <Route path="/tools" element={<ToolsPage />} />
          <Route path="/ai" element={<AIAssistantPage />} />
          <Route path="/ontology/*" element={<OntologyRoutes />} />
          <Route path="/platform" element={<PlatformPage />} />
          <Route path="/mdm" element={<MdmPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/observability" element={<ObservabilityPage />} />
          <Route path="/compliance/*" element={<ComplianceRoutes />} />
        </Route>

        {/* 兜底 */}
        <Route path="*" element={<Navigate to="/portal" replace />} />
        </Routes>
      </Suspense>

      {/* 全局组件 */}
      <Toast />
      <CommandPalette />

      {/* 全局 AI 浮动按钮 + 侧边栏：仅在非 /ai 路由下显示（/ai 页面自带完整聊天面板） */}
      {!isAIPage && (
        <>
          <button
            onClick={() => setAiSidebarOpen(true)}
            className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-brand-500 hover:bg-brand-600 text-white shadow-lg flex items-center justify-center transition-colors"
            title="AI 助手"
          >
            <Sparkles className="w-6 h-6" />
          </button>

          {/* 快速问答浮动按钮（在主按钮左侧） */}
          <AIQuickAsk />

          <AISidebar open={aiSidebarOpen} onClose={() => setAiSidebarOpen(false)} />
        </>
      )}
    </>
  )
}

// 外壳：只负责 ErrorBoundary + BrowserRouter
function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
