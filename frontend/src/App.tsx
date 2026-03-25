import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'

// Lazy-load all pages for code splitting
const OverviewPage       = lazy(() => import('@/pages/OverviewPage'))
const RunsPage           = lazy(() => import('@/pages/RunsPage'))
const RunDetailPage      = lazy(() => import('@/pages/RunDetailPage'))
const TestCasePage       = lazy(() => import('@/pages/TestCasePage'))
const CoveragePage       = lazy(() => import('@/pages/CoveragePage'))
const FailureAnalysisPage = lazy(() => import('@/pages/FailureAnalysisPage'))
const TrendsPage         = lazy(() => import('@/pages/TrendsPage'))
const DefectsPage        = lazy(() => import('@/pages/DefectsPage'))
const SearchPage         = lazy(() => import('@/pages/SearchPage'))
const ProjectsPage           = lazy(() => import('@/pages/ProjectsPage'))
const SettingsPage           = lazy(() => import('@/pages/SettingsPage'))
const NotificationsPage      = lazy(() => import('@/pages/settings/NotificationsPage'))
const ChatPage                  = lazy(() => import('@/pages/ChatPage'))
const AgentStatusPage           = lazy(() => import('@/pages/AgentStatusPage'))
const DeepInvestigationPage     = lazy(() => import('@/pages/DeepInvestigationPage'))
const ReleaseGatePage           = lazy(() => import('@/pages/ReleaseGatePage'))

const Fallback = () => (
  <div className="flex items-center justify-center h-64">
    <LoadingSpinner size="lg" />
  </div>
)

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={
            <Suspense fallback={<Fallback />}><OverviewPage /></Suspense>
          } />
          <Route path="runs" element={
            <Suspense fallback={<Fallback />}><RunsPage /></Suspense>
          } />
          <Route path="runs/:runId" element={
            <Suspense fallback={<Fallback />}><RunDetailPage /></Suspense>
          } />
          <Route path="runs/:runId/tests/:testId" element={
            <Suspense fallback={<Fallback />}><TestCasePage /></Suspense>
          } />
          <Route path="coverage" element={
            <Suspense fallback={<Fallback />}><CoveragePage /></Suspense>
          } />
          <Route path="failures" element={
            <Suspense fallback={<Fallback />}><FailureAnalysisPage /></Suspense>
          } />
          <Route path="trends" element={
            <Suspense fallback={<Fallback />}><TrendsPage /></Suspense>
          } />
          <Route path="defects" element={
            <Suspense fallback={<Fallback />}><DefectsPage /></Suspense>
          } />
          <Route path="search" element={
            <Suspense fallback={<Fallback />}><SearchPage /></Suspense>
          } />
          <Route path="projects" element={
            <Suspense fallback={<Fallback />}><ProjectsPage /></Suspense>
          } />
          <Route path="settings" element={
            <Suspense fallback={<Fallback />}><SettingsPage /></Suspense>
          } />
          <Route path="settings/notifications" element={
            <Suspense fallback={<Fallback />}><NotificationsPage /></Suspense>
          } />
          <Route path="chat" element={
            <Suspense fallback={<Fallback />}><ChatPage /></Suspense>
          } />
          <Route path="agents" element={
            <Suspense fallback={<Fallback />}><AgentStatusPage /></Suspense>
          } />
          <Route path="agents/run/:runId" element={
            <Suspense fallback={<Fallback />}><AgentStatusPage /></Suspense>
          } />
          <Route path="deep-investigate" element={
            <Suspense fallback={<Fallback />}><DeepInvestigationPage /></Suspense>
          } />
          <Route path="deep-investigate/:runId" element={
            <Suspense fallback={<Fallback />}><DeepInvestigationPage /></Suspense>
          } />
          <Route path="release-gate" element={
            <Suspense fallback={<Fallback />}><ReleaseGatePage /></Suspense>
          } />
          <Route path="release-gate/:runId" element={
            <Suspense fallback={<Fallback />}><ReleaseGatePage /></Suspense>
          } />
        </Route>
      </Route>
    </Routes>
  )
}
