import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import { Bug } from 'lucide-react'
export default function FailureAnalysisPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Failure Analysis" subtitle="Flaky leaderboard, error clustering, and repeat-failure detection" />
      <EmptyState icon={<Bug className="h-10 w-10" />} title="Failure Analysis — Phase 4"
        description="Flaky test leaderboard, error message clustering, and auto-categorisation charts — Phase 4." />
    </div>
  )
}
