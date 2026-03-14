import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import { Gauge } from 'lucide-react'
export default function DefectsPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Defects" subtitle="Defect growth, velocity, and Jira ticket board" />
      <EmptyState icon={<Gauge className="h-10 w-10" />} title="Defect Analytics — Phase 4"
        description="Defect injection vs resolution charts, MTTR by severity, and Jira sync — Phase 4." />
    </div>
  )
}
