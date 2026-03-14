import { useState, useEffect } from 'react'
import { FlaskConical, Plus } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'
import { projectsService, type Project } from '@/services/projectsService'
import { useProjectStore } from '@/store/projectStore'
import { fromNow } from '@/utils/formatters'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const { setActiveProject } = useProjectStore()

  useEffect(() => { projectsService.list().then(setProjects).catch(() => {}) }, [])

  return (
    <div className="space-y-4">
      <PageHeader title="Projects" subtitle="Manage test projects and their integrations"
        actions={<button className="btn-primary flex items-center gap-2 text-sm"><Plus className="h-4 w-4"/>New Project</button>} />
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {projects.map(p => (
          <div key={p.id}
            className="card hover:border-blue-600/50 transition-colors cursor-pointer group"
            onClick={() => setActiveProject(p)}>
            <div className="flex items-start gap-3">
              <div className="p-2.5 bg-blue-600/10 rounded-xl">
                <FlaskConical className="h-5 w-5 text-blue-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-slate-200 group-hover:text-blue-300 transition-colors">{p.name}</p>
                <p className="text-xs text-slate-500 font-mono mt-0.5">{p.slug}</p>
                {p.description && <p className="text-sm text-slate-400 mt-2 line-clamp-2">{p.description}</p>}
                <div className="flex gap-3 mt-3 text-xs text-slate-500">
                  {p.jira_project_key && <span>Jira: {p.jira_project_key}</span>}
                  {p.ocp_namespace && <span>OCP: {p.ocp_namespace}</span>}
                </div>
                <p className="text-xs text-slate-600 mt-2">Created {fromNow(p.created_at)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
