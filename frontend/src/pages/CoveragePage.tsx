import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import { ShieldCheck } from 'lucide-react'

export default function CoveragePage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Test Coverage" subtitle="Suite × build heatmap and API endpoint matrix" />
      <EmptyState
        icon={<ShieldCheck className="h-10 w-10" />}
        title="Coverage Analytics — Phase 4"
        description="D3.js coverage heatmap, suite treemap, and API endpoint coverage matrix will be implemented in Phase 4 of the development plan."
      />
    </div>
  )
}
