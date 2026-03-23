import { useState, useEffect } from 'react'
import { FlaskConical, Plus, X } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'
import { projectsService, type Project } from '@/services/projectsService'
import { useProjectStore } from '@/store/projectStore'
import { fromNow } from '@/utils/formatters'
import toast from 'react-hot-toast'

interface NewProjectForm {
  name: string
  slug: string
  description: string
  jira_project_key: string
  ocp_namespace: string
}

const EMPTY_FORM: NewProjectForm = {
  name: '',
  slug: '',
  description: '',
  jira_project_key: '',
  ocp_namespace: '',
}

function slugify(s: string) {
  return s.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '').slice(0, 100)
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState<NewProjectForm>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const { setActiveProject } = useProjectStore()

  const load = () => projectsService.list().then(setProjects).catch(() => {})
  useEffect(() => { load() }, [])

  const handleNameChange = (name: string) => {
    setForm(f => ({ ...f, name, slug: slugify(name) }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.slug.trim()) return
    setSaving(true)
    try {
      const payload: Record<string, string> = { name: form.name, slug: form.slug }
      if (form.description) payload.description = form.description
      if (form.jira_project_key) payload.jira_project_key = form.jira_project_key
      if (form.ocp_namespace) payload.ocp_namespace = form.ocp_namespace
      const created = await projectsService.create(payload)
      toast.success(`Project "${created.name}" created`)
      setShowModal(false)
      setForm(EMPTY_FORM)
      load()
    } catch {
      toast.error('Failed to create project')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Projects" subtitle="Manage test projects and their integrations"
        actions={
          <button
            className="btn-primary flex items-center gap-2 text-sm"
            onClick={() => { setForm(EMPTY_FORM); setShowModal(true) }}
          >
            <Plus className="h-4 w-4" /> New Project
          </button>
        }
      />

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

        {projects.length === 0 && (
          <div className="col-span-full flex flex-col items-center py-16 text-slate-500">
            <FlaskConical className="h-10 w-10 mb-3 text-slate-700" />
            <p className="font-medium">No projects yet</p>
            <p className="text-sm mt-1">Create your first project to start ingesting test reports</p>
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
              <h2 className="font-semibold text-slate-100">New Project</h2>
              <button onClick={() => setShowModal(false)} className="btn-ghost p-1">
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Project Name *</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. Payment Gateway API"
                  value={form.name}
                  onChange={e => handleNameChange(e.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Slug *</label>
                <input
                  type="text"
                  className="input font-mono text-sm"
                  placeholder="e.g. payment-gateway-api"
                  value={form.slug}
                  onChange={e => setForm(f => ({ ...f, slug: slugify(e.target.value) }))}
                  required
                />
                <p className="text-xs text-slate-600 mt-1">URL-friendly identifier — auto-filled from name</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Description</label>
                <textarea
                  className="input resize-none"
                  rows={2}
                  placeholder="Optional project description"
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Jira Project Key</label>
                  <input
                    type="text"
                    className="input font-mono text-sm"
                    placeholder="e.g. PAY"
                    value={form.jira_project_key}
                    onChange={e => setForm(f => ({ ...f, jira_project_key: e.target.value.toUpperCase() }))}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">OCP Namespace</label>
                  <input
                    type="text"
                    className="input text-sm"
                    placeholder="e.g. qa-testing"
                    value={form.ocp_namespace}
                    onChange={e => setForm(f => ({ ...f, ocp_namespace: e.target.value }))}
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button type="button" className="btn-secondary flex-1" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary flex-1" disabled={saving}>
                  {saving ? 'Creating…' : 'Create Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
