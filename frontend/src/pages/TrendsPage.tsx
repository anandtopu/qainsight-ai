import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import { TrendingUp } from 'lucide-react'
export default function TrendsPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Trends" subtitle="Historical pass/fail rates and sprint comparisons" />
      <EmptyState icon={<TrendingUp className="h-10 w-10" />} title="Trends — Phase 3"
        description="Configurable time-window trend charts and sprint-over-sprint comparison reports — Phase 3." />
    </div>
  )
}
