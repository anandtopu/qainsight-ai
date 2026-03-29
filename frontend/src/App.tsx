import { type ComponentType, lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useWebVitals } from '@/hooks/useWebVitals'
import LoginPage from '@/pages/LoginPage'

const OverviewPage = lazy(() => import('@/pages/OverviewPage'))
const RunsPage = lazy(() => import('@/pages/RunsPage'))
const RunDetailPage = lazy(() => import('@/pages/RunDetailPage'))
const TestCasePage = lazy(() => import('@/pages/TestCasePage'))
const CoveragePage = lazy(() => import('@/pages/CoveragePage'))
const SuiteDetailPage = lazy(() => import('@/pages/SuiteDetailPage'))
const FailureAnalysisPage = lazy(() => import('@/pages/FailureAnalysisPage'))
const TrendsPage = lazy(() => import('@/pages/TrendsPage'))
const DefectsPage = lazy(() => import('@/pages/DefectsPage'))
const SearchPage = lazy(() => import('@/pages/SearchPage'))
const ProjectsPage = lazy(() => import('@/pages/ProjectsPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const NotificationsPage = lazy(() => import('@/pages/settings/NotificationsPage'))
const ChatPage = lazy(() => import('@/pages/ChatPage'))
const AgentStatusPage = lazy(() => import('@/pages/AgentStatusPage'))
const DeepInvestigationPage = lazy(() => import('@/pages/DeepInvestigationPage'))
const ReleaseGatePage = lazy(() => import('@/pages/ReleaseGatePage'))
const TestManagementPage = lazy(() => import('@/pages/TestManagementPage'))
const LiveExecutionPage = lazy(() => import('@/pages/LiveExecutionPage'))
const ReleasesPage = lazy(() => import('@/pages/ReleasesPage'))
const UserManagementPage = lazy(() => import('@/pages/UserManagementPage'))

type AppRoute = {
  path: string
  component: ComponentType
}

const appRoutes: AppRoute[] = [
  { path: 'overview', component: OverviewPage },
  { path: 'runs', component: RunsPage },
  { path: 'runs/:runId', component: RunDetailPage },
  { path: 'runs/:runId/tests/:testId', component: TestCasePage },
  { path: 'coverage', component: CoveragePage },
  { path: 'coverage/suite', component: SuiteDetailPage },
  { path: 'failures', component: FailureAnalysisPage },
  { path: 'trends', component: TrendsPage },
  { path: 'defects', component: DefectsPage },
  { path: 'search', component: SearchPage },
  { path: 'projects', component: ProjectsPage },
  { path: 'settings', component: SettingsPage },
  { path: 'settings/notifications', component: NotificationsPage },
  { path: 'chat', component: ChatPage },
  { path: 'agents', component: AgentStatusPage },
  { path: 'agents/run/:runId', component: AgentStatusPage },
  { path: 'deep-investigate', component: DeepInvestigationPage },
  { path: 'deep-investigate/:runId', component: DeepInvestigationPage },
  { path: 'release-gate', component: ReleaseGatePage },
  { path: 'release-gate/:runId', component: ReleaseGatePage },
  { path: 'test-management', component: TestManagementPage },
  { path: 'live', component: LiveExecutionPage },
  { path: 'releases', component: ReleasesPage },
  { path: 'users', component: UserManagementPage },
]

function RouteFallback() {
  return (
    <div className="flex h-64 items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  )
}

function renderLazyRoute(Component: ComponentType) {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Component />
    </Suspense>
  )
}

export default function App() {
  useWebVitals()

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          {appRoutes.map(({ path, component }) => (
            <Route key={path} path={path} element={renderLazyRoute(component)} />
          ))}
        </Route>
      </Route>
    </Routes>
  )
}
