import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle, Calendar, CheckCircle2, ChevronDown, ChevronRight,
  Clock, GitBranch, Package, Plus, Rocket, Tag, Trash2, X,
} from 'lucide-react'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useReleases, useRelease } from '@/hooks/useReleases'
import { ALL_PROJECTS_ID, useProjectStore } from '@/store/projectStore'
import { releasesService } from '@/services/releasesService'
import { useRuns } from '@/hooks/useRuns'
import type { LinkedRun, Release, ReleaseDetail, ReleasePhase } from '@/types/releases'

// ── Constants ───────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ElementType }> = {
  planning:    { label: 'Planning',    color: 'text-blue-400',   bg: 'bg-blue-500/10 ring-blue-500/20',   icon: Clock        },
  in_progress: { label: 'In Progress', color: 'text-amber-400',  bg: 'bg-amber-500/10 ring-amber-500/20', icon: Rocket       },
  released:    { label: 'Released',    color: 'text-emerald-400',bg: 'bg-emerald-500/10 ring-emerald-500/20', icon: CheckCircle2 },
  cancelled:   { label: 'Cancelled',   color: 'text-slate-500',  bg: 'bg-slate-500/10 ring-slate-500/20', icon: X            },
}

const PHASE_TYPES = [
  { value: 'planning',    label: 'Planning'    },
  { value: 'development', label: 'Development' },
  { value: 'code_freeze', label: 'Code Freeze' },
  { value: 'qa_testing',  label: 'QA Testing'  },
  { value: 'uat',         label: 'UAT'         },
  { value: 'staging',     label: 'Staging'     },
  { value: 'production',  label: 'Production'  },
]

const PHASE_STATUS_COLOR: Record<string, string> = {
  pending:     'bg-slate-500/20 text-slate-400',
  in_progress: 'bg-amber-500/20 text-amber-400',
  completed:   'bg-emerald-500/20 text-emerald-400',
  skipped:     'bg-slate-500/10 text-slate-500',
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.planning
  const Icon = cfg.icon
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ring-1 ring-inset', cfg.bg, cfg.color)}>
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  )
}

// ── Create / Edit Release Modal ─────────────────────────────────────────────

interface ReleaseModalProps {
  projectId: string
  onClose: () => void
  onSaved: () => void
  initial?: Release
}

function ReleaseModal({ projectId, onClose, onSaved, initial }: ReleaseModalProps) {
  const [name, setName]           = useState(initial?.name ?? '')
  const [version, setVersion]     = useState(initial?.version ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [status, setStatus]       = useState(initial?.status ?? 'planning')
  const [plannedDate, setPlanned] = useState(
    initial?.planned_date ? initial.planned_date.slice(0, 10) : '',
  )
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!name.trim()) { toast.error('Release name is required'); return }
    setSaving(true)
    try {
      if (initial) {
        await releasesService.update(initial.id, {
          name: name.trim(),
          version: version || undefined,
          description: description || undefined,
          status,
          planned_date: plannedDate ? new Date(plannedDate).toISOString() : undefined,
        } as Partial<Release>)
        toast.success('Release updated')
      } else {
        await releasesService.create({
          project_id: projectId,
          name: name.trim(),
          version: version || undefined,
          description: description || undefined,
          status,
          planned_date: plannedDate ? new Date(plannedDate).toISOString() : undefined,
        })
        toast.success('Release created')
      }
      onSaved()
      onClose()
    } catch {
      toast.error('Failed to save release')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-lg shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-slate-100">{initial ? 'Edit Release' : 'New Release'}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200"><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Release Name *</label>
            <input
              value={name} onChange={e => setName(e.target.value)}
              placeholder="e.g. v2.4.0 — Login Revamp"
              className="input w-full"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Version</label>
              <input value={version} onChange={e => setVersion(e.target.value)} placeholder="e.g. 2.4.0" className="input w-full" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Status</label>
              <select value={status} onChange={e => setStatus(e.target.value)} className="input w-full">
                <option value="planning">Planning</option>
                <option value="in_progress">In Progress</option>
                <option value="released">Released</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Planned Release Date</label>
            <input type="date" value={plannedDate} onChange={e => setPlanned(e.target.value)} className="input w-full" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Description</label>
            <textarea
              value={description} onChange={e => setDescription(e.target.value)}
              rows={3}
              placeholder="What's included in this release?"
              className="input w-full resize-none"
            />
          </div>
        </div>
        <div className="flex gap-3 justify-end mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200">Cancel</button>
          <button
            onClick={save} disabled={saving}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg font-medium flex items-center gap-2"
          >
            {saving && <LoadingSpinner size="sm" />}
            {initial ? 'Save Changes' : 'Create Release'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Link Run Modal ──────────────────────────────────────────────────────────

function LinkRunModal({ releaseId, phases, onClose, onSaved }: {
  releaseId: string
  phases: ReleasePhase[]
  onClose: () => void
  onSaved: () => void
}) {
  const { data: runsData } = useRuns()
  const runs = runsData?.items ?? []
  const [selectedRun, setSelectedRun] = useState('')
  const [selectedPhase, setSelectedPhase] = useState('')
  const [saving, setSaving] = useState(false)

  async function link() {
    if (!selectedRun) { toast.error('Select a test run'); return }
    setSaving(true)
    try {
      await releasesService.linkRun(releaseId, selectedRun, selectedPhase || undefined)
      toast.success('Test run linked to release')
      onSaved()
      onClose()
    } catch {
      toast.error('Failed to link run')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-100">Link Test Run</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200"><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Test Run</label>
            <select value={selectedRun} onChange={e => setSelectedRun(e.target.value)} className="input w-full">
              <option value="">— Select run —</option>
              {(runs as Array<{ id: string; build_number?: number; created_at: string }>).map(r => (
                <option key={r.id} value={r.id}>
                  {r.build_number ?? r.id.slice(0, 8)} — {new Date(r.created_at).toLocaleDateString()}
                </option>
              ))}
            </select>
          </div>
          {phases.length > 0 && (
            <div>
              <label className="block text-xs text-slate-400 mb-1">Phase (optional)</label>
              <select value={selectedPhase} onChange={e => setSelectedPhase(e.target.value)} className="input w-full">
                <option value="">— No phase —</option>
                {phases.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          )}
        </div>
        <div className="flex gap-3 justify-end mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200">Cancel</button>
          <button
            onClick={link} disabled={saving || !selectedRun}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg font-medium flex items-center gap-2"
          >
            {saving && <LoadingSpinner size="sm" />}
            Link Run
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Phase Manager (inline) ──────────────────────────────────────────────────

function AddPhaseRow({ releaseId, onSaved }: { releaseId: string; onSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [type, setType] = useState('qa_testing')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!name.trim()) return
    setSaving(true)
    try {
      await releasesService.addPhase(releaseId, { name: name.trim(), phase_type: type, status: 'pending' })
      setName('')
      setType('qa_testing')
      setOpen(false)
      onSaved()
    } catch { toast.error('Failed to add phase') }
    finally { setSaving(false) }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full flex items-center gap-2 py-2 px-3 text-xs text-slate-500 hover:text-slate-300 border border-dashed border-slate-700 hover:border-slate-500 rounded-lg transition-colors"
      >
        <Plus className="h-3.5 w-3.5" /> Add Phase
      </button>
    )
  }

  return (
    <div className="flex items-center gap-2 p-2 bg-slate-800/50 rounded-lg border border-slate-700">
      <input value={name} onChange={e => setName(e.target.value)} placeholder="Phase name" className="input flex-1 py-1 text-xs" />
      <select value={type} onChange={e => setType(e.target.value)} className="input py-1 text-xs">
        {PHASE_TYPES.map(pt => <option key={pt.value} value={pt.value}>{pt.label}</option>)}
      </select>
      <button onClick={save} disabled={saving || !name.trim()} className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded">
        {saving ? '…' : 'Add'}
      </button>
      <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-300"><X className="h-3.5 w-3.5" /></button>
    </div>
  )
}

// ── Release Detail Panel ────────────────────────────────────────────────────

function ReleaseDetailPanel({ releaseId, onEdit, projectId }: {
  releaseId: string
  projectId: string
  onEdit: (r: Release) => void
}) {
  const navigate = useNavigate()
  const { data: detail, isLoading, mutate: refetch } = useRelease(releaseId)
  const [showLinkModal, setShowLinkModal] = useState(false)

  async function updatePhaseStatus(phaseId: string, status: string) {
    try {
      await releasesService.updatePhase(releaseId, phaseId, { status } as Partial<ReleasePhase>)
      refetch()
    } catch { toast.error('Failed to update phase') }
  }

  async function deletePhase(phaseId: string) {
    try {
      await releasesService.deletePhase(releaseId, phaseId)
      refetch()
    } catch { toast.error('Failed to delete phase') }
  }

  async function unlinkRun(runId: string) {
    try {
      await releasesService.unlinkRun(releaseId, runId)
      refetch()
    } catch { toast.error('Failed to unlink run') }
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-48"><LoadingSpinner size="lg" /></div>
  }
  if (!detail) return null

  const m = detail.metrics ?? {}
  const passRate = m.avg_pass_rate != null ? Number(m.avg_pass_rate).toFixed(1) : '—'
  const passColor = m.avg_pass_rate == null ? 'text-slate-400'
    : m.avg_pass_rate >= 90 ? 'text-emerald-400'
    : m.avg_pass_rate >= 70 ? 'text-amber-400'
    : 'text-red-400'

  return (
    <div className="space-y-5">
      {showLinkModal && (
        <LinkRunModal
          releaseId={releaseId}
          phases={detail.phases ?? []}
          onClose={() => setShowLinkModal(false)}
          onSaved={() => { refetch(); setShowLinkModal(false) }}
        />
      )}

      {/* Metrics strip */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {[
          { label: 'Runs',    value: m.total_runs ?? 0,    color: 'text-slate-300' },
          { label: 'Tests',   value: m.total_tests ?? 0,   color: 'text-slate-300' },
          { label: 'Passed',  value: m.total_passed ?? 0,  color: 'text-emerald-400' },
          { label: 'Failed',  value: m.total_failed ?? 0,  color: 'text-red-400' },
          { label: 'Pass Rate', value: `${passRate}%`,     color: passColor },
        ].map(({ label, value, color }) => (
          <div key={label} className="card py-2.5">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</p>
            <p className={clsx('text-xl font-bold tabular-nums mt-0.5', color)}>{value}</p>
          </div>
        ))}
      </div>

      {/* Phase timeline */}
      <div className="card">
        <h3 className="text-sm font-semibold text-slate-200 mb-3">Release Phases</h3>
        <div className="space-y-2">
          {(detail.phases ?? []).map((phase, i) => (
            <div key={phase.id} className="flex items-center gap-3 p-2 rounded-lg bg-slate-800/40 group">
              <div className="flex items-center justify-center h-6 w-6 rounded-full bg-slate-700 text-slate-400 text-xs font-bold flex-shrink-0">
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-slate-200">{phase.name}</span>
                  <span className="text-xs text-slate-500">{PHASE_TYPES.find(t => t.value === phase.phase_type)?.label ?? phase.phase_type}</span>
                  <span className={clsx('text-xs px-1.5 py-0.5 rounded font-medium', PHASE_STATUS_COLOR[phase.status] ?? PHASE_STATUS_COLOR.pending)}>
                    {phase.status.replace('_', ' ')}
                  </span>
                </div>
                {(phase.planned_start || phase.planned_end) && (
                  <p className="text-xs text-slate-500 mt-0.5">
                    {fmtDate(phase.planned_start)} → {fmtDate(phase.planned_end)}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <select
                  value={phase.status}
                  onChange={e => updatePhaseStatus(phase.id, e.target.value)}
                  className="text-xs bg-slate-700 border border-slate-600 rounded px-1.5 py-0.5 text-slate-200 focus:outline-none"
                >
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="skipped">Skipped</option>
                </select>
                <button onClick={() => deletePhase(phase.id)} className="text-slate-500 hover:text-red-400 transition-colors">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
          <AddPhaseRow releaseId={releaseId} onSaved={() => refetch()} />
        </div>
      </div>

      {/* Linked runs */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-200">Linked Test Runs ({detail.linked_runs?.length ?? 0})</h3>
          <button
            onClick={() => setShowLinkModal(true)}
            className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" /> Link Run
          </button>
        </div>
        {(detail.linked_runs?.length ?? 0) === 0 ? (
          <p className="text-sm text-slate-500 py-4 text-center">No test runs linked yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="th text-left">Build</th>
                  <th className="th text-right">Date</th>
                  <th className="th text-right text-emerald-400">Passed</th>
                  <th className="th text-right text-red-400">Failed</th>
                  <th className="th text-right">Pass Rate</th>
                  <th className="th"></th>
                </tr>
              </thead>
              <tbody>
                {detail.linked_runs.map((run: LinkedRun) => (
                  <tr key={run.id} className="table-row">
                    <td className="td font-mono text-slate-300 text-xs">
                      <button
                        className="text-blue-400 hover:text-blue-300"
                        onClick={() => navigate(`/runs/${run.id}`)}
                      >
                        {run.build_number ?? run.id.slice(0, 8)}
                      </button>
                    </td>
                    <td className="td text-right text-xs text-slate-400">{fmtDate(run.created_at)}</td>
                    <td className="td text-right tabular-nums text-emerald-400">{run.passed_tests}</td>
                    <td className="td text-right tabular-nums text-red-400">{run.failed_tests}</td>
                    <td className="td text-right tabular-nums text-slate-300">
                      {run.pass_rate != null ? `${Number(run.pass_rate).toFixed(1)}%` : '—'}
                    </td>
                    <td className="td text-right">
                      <button onClick={() => unlinkRun(run.id)} className="text-slate-500 hover:text-red-400 transition-colors">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function ReleasesPage() {
  const project   = useProjectStore(s => s.activeProject)
  const projectId = useProjectStore(s => s.activeProjectId)

  const { data, isLoading, mutate: refetch } = useReleases()
  const releases: Release[] = data?.items ?? []

  const [showModal, setShowModal]     = useState(false)
  const [editRelease, setEditRelease] = useState<Release | undefined>()
  const [expandedId, setExpandedId]   = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')

  async function deleteRelease(id: string) {
    if (!confirm('Delete this release and all its phases? This cannot be undone.')) return
    try {
      await releasesService.delete(id)
      toast.success('Release deleted')
      if (expandedId === id) setExpandedId(null)
      refetch()
    } catch { toast.error('Failed to delete release') }
  }

  const activeProjectId = useProjectStore(s => s.activeProjectId)
  const isAllProjects = activeProjectId === ALL_PROJECTS_ID

  if (!project) {
    return (
      <EmptyState
        icon={<Package className="h-10 w-10" />}
        title={isAllProjects ? 'Select a specific project' : 'No project selected'}
        description={
          isAllProjects
            ? 'Releases are managed per project — select a specific project from the top bar'
            : 'Select a project from the top bar'
        }
      />
    )
  }

  const filtered = statusFilter === 'all'
    ? releases
    : releases.filter(r => r.status === statusFilter)

  return (
    <>
      {showModal && projectId && (
        <ReleaseModal
          projectId={projectId}
          initial={editRelease}
          onClose={() => { setShowModal(false); setEditRelease(undefined) }}
          onSaved={() => refetch()}
        />
      )}

      <div className="space-y-6">
        <PageHeader
          title="Releases"
          subtitle={`Manage releases and track QA progress for ${project.name}`}
          actions={
            <div className="flex items-center gap-2">
              {/* Status filter */}
              <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
                {['all', 'planning', 'in_progress', 'released', 'cancelled'].map(s => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={clsx(
                      'px-3 py-1 rounded-md text-xs font-medium transition-colors capitalize',
                      statusFilter === s ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-100',
                    )}
                  >
                    {s === 'all' ? 'All' : s.replace('_', ' ')}
                  </button>
                ))}
              </div>
              <button
                onClick={() => { setEditRelease(undefined); setShowModal(true) }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium"
              >
                <Plus className="h-4 w-4" /> New Release
              </button>
            </div>
          }
        />

        {isLoading ? (
          <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>
        ) : releases.length === 0 ? (
          <EmptyState
            icon={<Package className="h-8 w-8" />}
            title="No releases yet"
            description="Create your first release to start tracking QA progress"
            action={
              <button
                onClick={() => setShowModal(true)}
                className="mt-4 flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium mx-auto"
              >
                <Plus className="h-4 w-4" /> Create Release
              </button>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<AlertCircle className="h-8 w-8" />}
            title="No releases match filter"
            description={`No ${statusFilter.replace('_', ' ')} releases found`}
          />
        ) : (
          <div className="space-y-3">
            {filtered.map(release => {
              const isExpanded = expandedId === release.id
              const cfg = STATUS_CONFIG[release.status] ?? STATUS_CONFIG.planning
              const StatusIcon = cfg.icon
              const donePhases = release.phases.filter(p => p.status === 'completed').length
              const totalPhases = release.phases.length

              return (
                <div key={release.id} className="card overflow-hidden">
                  {/* Header row */}
                  <div
                    className="flex items-center gap-3 cursor-pointer select-none"
                    onClick={() => setExpandedId(isExpanded ? null : release.id)}
                  >
                    <div className={clsx('h-9 w-9 rounded-lg flex items-center justify-center flex-shrink-0', cfg.bg)}>
                      <StatusIcon className={clsx('h-4 w-4', cfg.color)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-slate-100">{release.name}</h3>
                        {release.version && (
                          <span className="flex items-center gap-1 text-xs text-slate-400">
                            <Tag className="h-3 w-3" />{release.version}
                          </span>
                        )}
                        <StatusBadge status={release.status} />
                      </div>
                      <div className="flex items-center gap-4 mt-0.5 text-xs text-slate-500">
                        {release.planned_date && (
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />Target: {fmtDate(release.planned_date)}
                          </span>
                        )}
                        {totalPhases > 0 && (
                          <span className="flex items-center gap-1">
                            <GitBranch className="h-3 w-3" />
                            {donePhases}/{totalPhases} phases complete
                          </span>
                        )}
                        {release.test_run_count != null && release.test_run_count > 0 && (
                          <span>{release.test_run_count} run{release.test_run_count !== 1 ? 's' : ''} linked</span>
                        )}
                      </div>
                    </div>

                    {/* Phase progress bar */}
                    {totalPhases > 0 && (
                      <div className="hidden sm:flex flex-col items-end gap-1 w-24">
                        <span className="text-[10px] text-slate-500">{Math.round(donePhases / totalPhases * 100)}% done</span>
                        <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 rounded-full transition-all"
                            style={{ width: `${(donePhases / totalPhases) * 100}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-1.5 ml-2">
                      <button
                        onClick={e => { e.stopPropagation(); setEditRelease(release); setShowModal(true) }}
                        className="text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-700 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); deleteRelease(release.id) }}
                        className="text-xs text-red-500/70 hover:text-red-400 px-2 py-1 rounded hover:bg-red-500/10 transition-colors"
                      >
                        Delete
                      </button>
                      {isExpanded ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="mt-5 pt-5 border-t border-slate-800">
                      {release.description && (
                        <p className="text-sm text-slate-400 mb-4">{release.description}</p>
                      )}
                      <ReleaseDetailPanel releaseId={release.id} projectId={projectId ?? ''} onEdit={r => { setEditRelease(r); setShowModal(true) }} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
