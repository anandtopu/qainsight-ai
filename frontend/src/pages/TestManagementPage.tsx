import { useState, useCallback } from 'react'
import {
  ClipboardList, Plus, Sparkles, ChevronDown, ChevronRight,
  Star, Clock, User, Tag, CheckCircle2, XCircle, AlertCircle,
  RotateCcw, Eye, MessageSquare, History, Shield, FileText,
  ChevronUp, Trash2, PlayCircle, BookOpen, BarChart2,
} from 'lucide-react'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { mutate } from 'swr'
import PageHeader from '@/components/ui/PageHeader'
import EmptyState from '@/components/ui/EmptyState'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import Pagination from '@/components/ui/Pagination'
import { useProjectStore } from '@/store/projectStore'
import {
  useTestCases, useTestPlans, useStrategies, useAuditLog,
  useTestCaseHistory, useTestCaseReviews, useTestCaseComments,
  usePlanItems,
} from '@/hooks/useTestManagement'
import {
  testManagementService,
  type ManagedTestCase, type TestPlan, type TestStrategy,
  type TestCaseVersion, type TestCaseReview, type TestCaseComment,
  type TestPlanItem, type AIReviewResult, type TestStep,
} from '@/services/testManagementService'

// ─── Constants / helpers ─────────────────────────────────────────────────────

const TABS = ['Test Cases', 'Test Plans', 'Strategy', 'Reviews', 'Audit Log'] as const
type Tab = typeof TABS[number]

const STATUS_COLORS: Record<string, string> = {
  draft:            'bg-slate-700 text-slate-300 border border-slate-600',
  review_requested: 'bg-amber-900/60 text-amber-300 border border-amber-700/50',
  under_review:     'bg-blue-900/60 text-blue-300 border border-blue-700/50',
  approved:         'bg-green-900/60 text-green-300 border border-green-700/50',
  active:           'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50',
  rejected:         'bg-red-900/60 text-red-300 border border-red-700/50',
  deprecated:       'bg-slate-800 text-slate-500 border border-slate-700',
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-900/60 text-red-300 border border-red-700/50',
  high:     'bg-orange-900/60 text-orange-300 border border-orange-700/50',
  medium:   'bg-yellow-900/60 text-yellow-300 border border-yellow-700/50',
  low:      'bg-slate-700 text-slate-400 border border-slate-600',
}

const PLAN_STATUS_COLORS: Record<string, string> = {
  draft:       'bg-slate-700 text-slate-300 border border-slate-600',
  active:      'bg-blue-900/60 text-blue-300 border border-blue-700/50',
  in_progress: 'bg-amber-900/60 text-amber-300 border border-amber-700/50',
  completed:   'bg-green-900/60 text-green-300 border border-green-700/50',
  archived:    'bg-slate-800 text-slate-500 border border-slate-700',
}

function StatusPill({ status, map }: { status: string; map: Record<string, string> }) {
  const cls = map[status] ?? 'bg-slate-700 text-slate-400 border border-slate-600'
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', cls)}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function QualityScore({ score }: { score?: number }) {
  if (score == null) return <span className="text-slate-600 text-xs">—</span>
  const color = score >= 80 ? 'text-green-400' : score >= 60 ? 'text-amber-400' : 'text-red-400'
  return <span className={clsx('text-sm font-semibold tabular-nums', color)}>{score}</span>
}

function fmtDate(iso?: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function fmtDateTime(iso?: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ─── Sub-components (Modals) ──────────────────────────────────────────────────

interface ModalWrapProps { onClose: () => void; title: string; children: React.ReactNode; width?: string }
function ModalWrap({ onClose, title, children, width = 'max-w-2xl' }: ModalWrapProps) {
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className={clsx('bg-slate-900 border border-slate-700 rounded-xl w-full shadow-2xl flex flex-col max-h-[90vh]', width)}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 flex-shrink-0">
          <h2 className="text-base font-semibold text-slate-100">{title}</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200 transition-colors text-xl leading-none">&times;</button>
        </div>
        <div className="overflow-y-auto flex-1 px-6 py-4">
          {children}
        </div>
      </div>
    </div>
  )
}

// ── Create Test Case Modal ────────────────────────────────────────────────────

interface CreateCaseModalProps { projectId: string; onClose: () => void; onCreated: () => void }

function CreateCaseModal({ projectId, onClose, onCreated }: CreateCaseModalProps) {
  const [title, setTitle] = useState('')
  const [testType, setTestType] = useState('functional')
  const [priority, setPriority] = useState('medium')
  const [featureArea, setFeatureArea] = useState('')
  const [objective, setObjective] = useState('')
  const [preconditions, setPreconditions] = useState('')
  const [steps, setSteps] = useState<TestStep[]>([{ step_number: 1, action: '', expected_result: '' }])
  const [expectedResult, setExpectedResult] = useState('')
  const [testData, setTestData] = useState('')
  const [estimatedDuration, setEstimatedDuration] = useState('')
  const [saving, setSaving] = useState(false)

  const addStep = () => setSteps(s => [...s, { step_number: s.length + 1, action: '', expected_result: '' }])
  const removeStep = (i: number) => setSteps(s => s.filter((_, idx) => idx !== i).map((st, idx) => ({ ...st, step_number: idx + 1 })))
  const updateStep = (i: number, field: keyof TestStep, value: string) =>
    setSteps(s => s.map((st, idx) => idx === i ? { ...st, [field]: value } : st))

  const handleSubmit = async () => {
    if (title.trim().length < 3) { toast.error('Title must be at least 3 characters'); return }
    setSaving(true)
    try {
      await testManagementService.createCase({
        project_id: projectId,
        title: title.trim(),
        test_type: testType,
        priority,
        feature_area: featureArea || undefined,
        objective: objective || undefined,
        preconditions: preconditions || undefined,
        steps: steps.filter(s => s.action.trim()),
        expected_result: expectedResult || undefined,
        test_data: testData || undefined,
        estimated_duration_minutes: estimatedDuration ? Math.max(1, Math.round(Number(estimatedDuration))) : undefined,
        severity: 'medium',
        is_automated: false,
        automation_status: 'not_automated',
      })
      toast.success('Test case created')
      onCreated()
      onClose()
    } catch {
      toast.error('Failed to create test case')
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalWrap onClose={onClose} title="New Test Case" width="max-w-3xl">
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Title *</label>
          <input className="input w-full" value={title} onChange={e => setTitle(e.target.value)} placeholder="Describe what this test verifies" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Test Type</label>
            <select className="input w-full" value={testType} onChange={e => setTestType(e.target.value)}>
              {['functional','integration','e2e','regression','smoke','performance','security','usability','accessibility','api'].map(t => (
                <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Priority</label>
            <select className="input w-full" value={priority} onChange={e => setPriority(e.target.value)}>
              {['critical','high','medium','low'].map(p => (
                <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Feature Area</label>
          <input className="input w-full" value={featureArea} onChange={e => setFeatureArea(e.target.value)} placeholder="e.g. Authentication, Checkout" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Objective</label>
          <textarea className="input w-full h-16 resize-none" value={objective} onChange={e => setObjective(e.target.value)} placeholder="What is the goal of this test?" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Preconditions</label>
          <textarea className="input w-full h-16 resize-none" value={preconditions} onChange={e => setPreconditions(e.target.value)} placeholder="Required state before executing" />
        </div>

        {/* Steps editor */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-slate-400">Test Steps</label>
            <button onClick={addStep} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              <Plus className="h-3 w-3" /> Add Step
            </button>
          </div>
          <div className="space-y-2">
            {steps.map((step, i) => (
              <div key={i} className="flex gap-2 items-start bg-slate-800 rounded-lg p-2">
                <span className="text-xs text-slate-500 w-6 mt-2 flex-shrink-0">#{i + 1}</span>
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <input
                    className="input text-xs"
                    value={step.action}
                    onChange={e => updateStep(i, 'action', e.target.value)}
                    placeholder="Action"
                  />
                  <input
                    className="input text-xs"
                    value={step.expected_result}
                    onChange={e => updateStep(i, 'expected_result', e.target.value)}
                    placeholder="Expected result"
                  />
                </div>
                {steps.length > 1 && (
                  <button onClick={() => removeStep(i)} className="text-slate-600 hover:text-red-400 mt-2">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1">Overall Expected Result</label>
          <textarea className="input w-full h-16 resize-none" value={expectedResult} onChange={e => setExpectedResult(e.target.value)} placeholder="Overall expected outcome" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Test Data</label>
            <textarea className="input w-full h-16 resize-none" value={testData} onChange={e => setTestData(e.target.value)} placeholder="Test data or data setup notes" />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Estimated Duration (min)</label>
            <input className="input w-full" type="number" min="1" step="1" value={estimatedDuration} onChange={e => setEstimatedDuration(e.target.value)} placeholder="e.g. 5" />
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-slate-800">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={handleSubmit} disabled={saving} className="btn-primary flex items-center gap-2">
            {saving && <LoadingSpinner size="sm" />}
            {saving ? 'Saving…' : 'Create Test Case'}
          </button>
        </div>
      </div>
    </ModalWrap>
  )
}

// ── AI Generate Modal ─────────────────────────────────────────────────────────

interface AIGenerateModalProps { projectId: string; onClose: () => void; onCreated: () => void }

function AIGenerateModal({ projectId, onClose, onCreated }: AIGenerateModalProps) {
  const [requirements, setRequirements] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ test_cases: Partial<ManagedTestCase>[]; coverage_summary?: string; gaps_noted: string[]; created_ids: string[] } | null>(null)
  const [saving, setSaving] = useState(false)

  const handleGenerate = async () => {
    if (!requirements.trim()) { toast.error('Requirements text is required'); return }
    setLoading(true)
    try {
      const res = await testManagementService.aiGenerate({ project_id: projectId, requirements: requirements.trim(), persist: false })
      setResult(res)
    } catch {
      toast.error('AI generation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveAll = async () => {
    if (!result) return
    setSaving(true)
    try {
      await testManagementService.aiGenerate({ project_id: projectId, requirements: requirements.trim(), persist: true })
      toast.success(`${result.test_cases.length} test cases saved as drafts`)
      onCreated()
      onClose()
    } catch {
      toast.error('Failed to save test cases')
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalWrap onClose={onClose} title="AI Generate Test Cases" width="max-w-3xl">
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Requirements / Feature Description</label>
          <textarea
            className="input w-full h-36 resize-none"
            value={requirements}
            onChange={e => setRequirements(e.target.value)}
            placeholder="Describe the feature or paste requirements text. The AI will generate comprehensive test cases covering happy paths, edge cases, and error scenarios."
            disabled={loading}
          />
        </div>
        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={handleGenerate} disabled={loading || !requirements.trim()} className="btn-primary flex items-center gap-2">
            {loading ? <LoadingSpinner size="sm" /> : <Sparkles className="h-4 w-4" />}
            {loading ? 'Generating…' : 'Generate'}
          </button>
        </div>

        {result && (
          <div className="border-t border-slate-800 pt-4 space-y-3">
            {result.coverage_summary && (
              <div className="bg-slate-800 rounded-lg p-3 text-sm text-slate-300">
                <span className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Coverage Summary</span>
                {result.coverage_summary}
              </div>
            )}
            {result.gaps_noted.length > 0 && (
              <div className="bg-amber-900/20 border border-amber-800/40 rounded-lg p-3">
                <span className="text-xs text-amber-400 uppercase tracking-wider block mb-1">Gaps Noted</span>
                <ul className="space-y-0.5">
                  {result.gaps_noted.map((g, i) => <li key={i} className="text-xs text-amber-300">{g}</li>)}
                </ul>
              </div>
            )}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-200">{result.test_cases.length} test cases generated</span>
                <button onClick={handleSaveAll} disabled={saving} className="btn-primary flex items-center gap-2 text-sm">
                  {saving && <LoadingSpinner size="sm" />}
                  {saving ? 'Saving…' : 'Save All as Draft'}
                </button>
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {result.test_cases.map((tc, i) => (
                  <div key={i} className="bg-slate-800 rounded-lg p-3 border border-slate-700">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-slate-200 font-medium">{tc.title ?? `Test Case ${i + 1}`}</p>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <StatusPill status={tc.priority ?? 'medium'} map={PRIORITY_COLORS} />
                        <span className="text-xs text-slate-500">{tc.test_type ?? 'functional'}</span>
                      </div>
                    </div>
                    {tc.objective && <p className="text-xs text-slate-400 mt-1">{tc.objective}</p>}
                    {tc.steps && tc.steps.length > 0 && (
                      <p className="text-xs text-slate-500 mt-1">{tc.steps.length} steps</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </ModalWrap>
  )
}

// ── Case Detail Panel ─────────────────────────────────────────────────────────

type DetailTab = 'details' | 'history' | 'reviews' | 'comments' | 'ai_review'

interface CaseDetailPanelProps { caseItem: ManagedTestCase; onClose: () => void; onRefresh: () => void }

function CaseDetailPanel({ caseItem, onClose, onRefresh }: CaseDetailPanelProps) {
  const [activeTab, setActiveTab] = useState<DetailTab>('details')
  const [comment, setComment] = useState('')
  const [addingComment, setAddingComment] = useState(false)
  const [runningAiReview, setRunningAiReview] = useState(false)
  const [aiResult, setAiResult] = useState<AIReviewResult | null>(caseItem.ai_review_notes ?? null)
  const [requestingReview, setRequestingReview] = useState(false)

  const { data: history, isLoading: histLoading } = useTestCaseHistory(activeTab === 'history' ? caseItem.id : undefined)
  const { data: reviews, isLoading: revLoading, mutate: mutateReviews } = useTestCaseReviews(activeTab === 'reviews' ? caseItem.id : undefined)
  const { data: comments, isLoading: commLoading, mutate: mutateComments } = useTestCaseComments(
    activeTab === 'comments' ? caseItem.id : undefined
  )

  const DETAIL_TABS: { id: DetailTab; label: string; icon: React.ReactNode }[] = [
    { id: 'details',   label: 'Details',    icon: <FileText className="h-3.5 w-3.5" /> },
    { id: 'history',   label: 'History',    icon: <History className="h-3.5 w-3.5" /> },
    { id: 'reviews',   label: 'Reviews',    icon: <Shield className="h-3.5 w-3.5" /> },
    { id: 'comments',  label: 'Comments',   icon: <MessageSquare className="h-3.5 w-3.5" /> },
    { id: 'ai_review', label: 'AI Review',  icon: <Sparkles className="h-3.5 w-3.5" /> },
  ]

  const handleAddComment = async () => {
    if (!comment.trim()) return
    setAddingComment(true)
    try {
      await testManagementService.addComment(caseItem.id, { content: comment.trim(), comment_type: 'general' })
      setComment('')
      mutateComments()
      toast.success('Comment added')
    } catch {
      toast.error('Failed to add comment')
    } finally {
      setAddingComment(false)
    }
  }

  const handleAiReview = async () => {
    setRunningAiReview(true)
    try {
      const result = await testManagementService.aiReview(caseItem.id)
      setAiResult(result)
      onRefresh()
      toast.success('AI review complete')
    } catch {
      toast.error('AI review failed')
    } finally {
      setRunningAiReview(false)
    }
  }

  const handleRequestReview = async () => {
    setRequestingReview(true)
    try {
      await testManagementService.requestReview(caseItem.id)
      onRefresh()
      mutateReviews()
      toast.success('Review requested')
    } catch {
      toast.error('Failed to request review')
    } finally {
      setRequestingReview(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-start justify-end">
      <div className="bg-slate-900 border-l border-slate-800 h-full w-full max-w-2xl flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex-shrink-0">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h2 className="text-base font-semibold text-slate-100 leading-snug">{caseItem.title}</h2>
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                <StatusPill status={caseItem.status} map={STATUS_COLORS} />
                <StatusPill status={caseItem.priority} map={PRIORITY_COLORS} />
                <span className="text-xs text-slate-500">{caseItem.test_type}</span>
                {caseItem.ai_generated && (
                  <span className="text-xs text-purple-400 flex items-center gap-0.5"><Sparkles className="h-3 w-3" /> AI</span>
                )}
              </div>
            </div>
            <button onClick={onClose} className="text-slate-500 hover:text-slate-200 text-xl leading-none flex-shrink-0">&times;</button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 px-4 pt-3 border-b border-slate-800 flex-shrink-0 overflow-x-auto">
          {DETAIL_TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-t border-b-2 transition-colors whitespace-nowrap',
                activeTab === t.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              )}
            >
              {t.icon}{t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Details tab */}
          {activeTab === 'details' && (
            <div className="space-y-4">
              {caseItem.objective && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Objective</p>
                  <p className="text-sm text-slate-300">{caseItem.objective}</p>
                </div>
              )}
              {caseItem.preconditions && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Preconditions</p>
                  <p className="text-sm text-slate-300">{caseItem.preconditions}</p>
                </div>
              )}
              {caseItem.steps && caseItem.steps.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Test Steps</p>
                  <div className="space-y-2">
                    {caseItem.steps.map(step => (
                      <div key={step.step_number} className="bg-slate-800 rounded-lg p-3">
                        <div className="flex items-start gap-3">
                          <span className="text-xs text-slate-500 w-5 flex-shrink-0 mt-0.5">#{step.step_number}</span>
                          <div className="flex-1 grid grid-cols-2 gap-3 text-sm">
                            <div>
                              <span className="text-xs text-slate-500 block mb-0.5">Action</span>
                              <span className="text-slate-300">{step.action}</span>
                            </div>
                            <div>
                              <span className="text-xs text-slate-500 block mb-0.5">Expected</span>
                              <span className="text-slate-300">{step.expected_result}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {caseItem.expected_result && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Expected Result</p>
                  <p className="text-sm text-slate-300">{caseItem.expected_result}</p>
                </div>
              )}
              {caseItem.test_data && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Test Data</p>
                  <pre className="text-xs text-slate-300 bg-slate-800 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">{caseItem.test_data}</pre>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ['Feature Area', caseItem.feature_area ?? '—'],
                  ['Severity', caseItem.severity],
                  ['Version', String(caseItem.version)],
                  ['Automation', caseItem.automation_status.replace(/_/g, ' ')],
                  ['Est. Duration', caseItem.estimated_duration_minutes ? `${caseItem.estimated_duration_minutes} min` : '—'],
                  ['Last Executed', fmtDate(caseItem.last_executed_at)],
                ].map(([label, value]) => (
                  <div key={label} className="bg-slate-800 rounded-lg p-3">
                    <p className="text-xs text-slate-500 mb-0.5">{label}</p>
                    <p className="text-slate-300 capitalize">{value}</p>
                  </div>
                ))}
              </div>
              {caseItem.tags && caseItem.tags.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Tags</p>
                  <div className="flex flex-wrap gap-1.5">
                    {caseItem.tags.map(tag => (
                      <span key={tag} className="bg-slate-800 text-slate-400 text-xs px-2 py-0.5 rounded-full border border-slate-700">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {caseItem.status !== 'review_requested' && caseItem.status !== 'under_review' && (
                <div className="pt-2">
                  <button
                    onClick={handleRequestReview}
                    disabled={requestingReview}
                    className="btn-secondary flex items-center gap-2 text-sm"
                  >
                    {requestingReview ? <LoadingSpinner size="sm" /> : <Eye className="h-4 w-4" />}
                    Request Review
                  </button>
                </div>
              )}
            </div>
          )}

          {/* History tab */}
          {activeTab === 'history' && (
            histLoading ? <div className="flex justify-center py-12"><LoadingSpinner /></div> :
            !history || history.length === 0 ? (
              <EmptyState icon={<History className="h-8 w-8" />} title="No history yet" description="Changes to this test case will appear here" />
            ) : (
              <div className="space-y-3">
                {(history as TestCaseVersion[]).map(v => (
                  <div key={v.id} className="bg-slate-800 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-slate-200">v{v.version} — {v.change_type.replace(/_/g, ' ')}</span>
                      <span className="text-xs text-slate-500">{fmtDateTime(v.created_at)}</span>
                    </div>
                    {v.change_summary && <p className="text-xs text-slate-400">{v.change_summary}</p>}
                  </div>
                ))}
              </div>
            )
          )}

          {/* Reviews tab */}
          {activeTab === 'reviews' && (
            revLoading ? <div className="flex justify-center py-12"><LoadingSpinner /></div> :
            !reviews || reviews.length === 0 ? (
              <EmptyState icon={<Shield className="h-8 w-8" />} title="No reviews" description="Request a review to get feedback on this test case" />
            ) : (
              <div className="space-y-3">
                {(reviews as TestCaseReview[]).map(r => (
                  <div key={r.id} className="bg-slate-800 rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <StatusPill status={r.status} map={STATUS_COLORS} />
                      <span className="text-xs text-slate-500">{fmtDateTime(r.created_at)}</span>
                    </div>
                    {r.ai_review_completed && r.ai_quality_score != null && (
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                        <span className="text-xs text-slate-400">AI Score:</span>
                        <QualityScore score={r.ai_quality_score} />
                      </div>
                    )}
                    {r.human_notes && (
                      <p className="text-xs text-slate-300 border-t border-slate-700 pt-2">{r.human_notes}</p>
                    )}
                  </div>
                ))}
              </div>
            )
          )}

          {/* Comments tab */}
          {activeTab === 'comments' && (
            <div className="space-y-4">
              {commLoading ? <div className="flex justify-center py-8"><LoadingSpinner /></div> :
               !comments || comments.length === 0 ? (
                <EmptyState icon={<MessageSquare className="h-8 w-8" />} title="No comments yet" description="Start a discussion about this test case" />
               ) : (
                <div className="space-y-3">
                  {(comments as TestCaseComment[]).map(c => (
                    <div key={c.id} className={clsx('bg-slate-800 rounded-lg p-3', c.is_resolved && 'opacity-60')}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400">{c.comment_type}</span>
                        <span className="text-xs text-slate-500">{fmtDateTime(c.created_at)}</span>
                      </div>
                      <p className="text-sm text-slate-300">{c.content}</p>
                      {c.step_number && <p className="text-xs text-slate-500 mt-1">Step #{c.step_number}</p>}
                    </div>
                  ))}
                </div>
               )
              }
              <div className="border-t border-slate-800 pt-3">
                <textarea
                  className="input w-full h-20 resize-none text-sm"
                  value={comment}
                  onChange={e => setComment(e.target.value)}
                  placeholder="Add a comment…"
                />
                <div className="flex justify-end mt-2">
                  <button onClick={handleAddComment} disabled={addingComment || !comment.trim()} className="btn-primary text-sm flex items-center gap-2">
                    {addingComment && <LoadingSpinner size="sm" />}
                    Post Comment
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* AI Review tab */}
          {activeTab === 'ai_review' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-300">Run AI analysis to score this test case and get improvement suggestions.</p>
                <button onClick={handleAiReview} disabled={runningAiReview} className="btn-primary flex items-center gap-2 text-sm flex-shrink-0">
                  {runningAiReview ? <LoadingSpinner size="sm" /> : <Sparkles className="h-4 w-4" />}
                  {runningAiReview ? 'Reviewing…' : 'Run AI Review'}
                </button>
              </div>
              {aiResult && (
                <div className="space-y-3">
                  <div className="flex items-center gap-4 bg-slate-800 rounded-lg p-4">
                    <div className="text-center">
                      <p className="text-3xl font-bold tabular-nums text-blue-400">{aiResult.quality_score ?? '—'}</p>
                      <p className="text-xs text-slate-500">Quality Score</p>
                    </div>
                    {aiResult.grade && (
                      <div className="text-center">
                        <p className="text-3xl font-bold text-green-400">{aiResult.grade}</p>
                        <p className="text-xs text-slate-500">Grade</p>
                      </div>
                    )}
                    {aiResult.summary && <p className="text-sm text-slate-300 flex-1">{aiResult.summary}</p>}
                  </div>
                  {aiResult.issues && aiResult.issues.length > 0 && (
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Issues Found</p>
                      <div className="space-y-1.5">
                        {aiResult.issues.map((issue, i) => (
                          <div key={i} className="flex items-start gap-2 bg-slate-800 rounded p-2.5">
                            <AlertCircle className={clsx('h-3.5 w-3.5 mt-0.5 flex-shrink-0',
                              issue.severity === 'critical' ? 'text-red-400' : issue.severity === 'major' ? 'text-orange-400' : 'text-amber-400'
                            )} />
                            <div>
                              <p className="text-xs font-medium text-slate-300">{issue.category}{issue.step ? ` (Step #${issue.step})` : ''}</p>
                              <p className="text-xs text-slate-400">{issue.description}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {aiResult.suggestions && aiResult.suggestions.length > 0 && (
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Suggestions</p>
                      <div className="space-y-1.5">
                        {aiResult.suggestions.map((s, i) => (
                          <div key={i} className="bg-slate-800 rounded p-2.5">
                            <p className="text-xs font-medium text-blue-400 capitalize">{s.field}</p>
                            <p className="text-xs text-slate-300 mt-0.5">{s.suggestion}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {aiResult.positive_aspects && aiResult.positive_aspects.length > 0 && (
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Positive Aspects</p>
                      <ul className="space-y-1">
                        {aiResult.positive_aspects.map((p, i) => (
                          <li key={i} className="flex items-center gap-2 text-xs text-green-300">
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                            {p}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Create Plan Modal ─────────────────────────────────────────────────────────

interface CreatePlanModalProps { projectId: string; onClose: () => void; onCreated: () => void }

function CreatePlanModal({ projectId, onClose, onCreated }: CreatePlanModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [objective, setObjective] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async () => {
    if (!name.trim()) { toast.error('Name is required'); return }
    setSaving(true)
    try {
      await testManagementService.createPlan({
        project_id: projectId,
        name: name.trim(),
        description: description || undefined,
        objective: objective || undefined,
        planned_start_date: startDate || undefined,
        planned_end_date: endDate || undefined,
        status: 'draft',
        ai_generated: false,
        total_cases: 0,
        executed_cases: 0,
        passed_cases: 0,
        failed_cases: 0,
        blocked_cases: 0,
      })
      toast.success('Test plan created')
      onCreated()
      onClose()
    } catch {
      toast.error('Failed to create plan')
    } finally {
      setSaving(false)
    }
  }

  return (
    <ModalWrap onClose={onClose} title="New Test Plan">
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Plan Name *</label>
          <input className="input w-full" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Sprint 42 Regression" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Description</label>
          <textarea className="input w-full h-20 resize-none" value={description} onChange={e => setDescription(e.target.value)} placeholder="What does this plan cover?" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Objective</label>
          <textarea className="input w-full h-16 resize-none" value={objective} onChange={e => setObjective(e.target.value)} placeholder="Goals for this test plan" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Planned Start</label>
            <input type="date" className="input w-full" value={startDate} onChange={e => setStartDate(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Planned End</label>
            <input type="date" className="input w-full" value={endDate} onChange={e => setEndDate(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-2 border-t border-slate-800">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={handleSubmit} disabled={saving} className="btn-primary flex items-center gap-2">
            {saving && <LoadingSpinner size="sm" />}
            {saving ? 'Creating…' : 'Create Plan'}
          </button>
        </div>
      </div>
    </ModalWrap>
  )
}

// ── Generate Strategy Modal ───────────────────────────────────────────────────

interface GenerateStrategyModalProps { projectId: string; onClose: () => void; onCreated: () => void }

function GenerateStrategyModal({ projectId, onClose, onCreated }: GenerateStrategyModalProps) {
  const [context, setContext] = useState('')
  const [strategyName, setStrategyName] = useState('')
  const [loading, setLoading] = useState(false)

  const handleGenerate = async () => {
    if (!context.trim()) { toast.error('Project context is required'); return }
    setLoading(true)
    try {
      await testManagementService.aiGenerateStrategy({
        project_id: projectId,
        project_context: context.trim(),
        strategy_name: strategyName || undefined,
      })
      toast.success('Test strategy generated')
      onCreated()
      onClose()
    } catch {
      toast.error('Strategy generation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <ModalWrap onClose={onClose} title="Generate Test Strategy with AI">
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1">Strategy Name (optional)</label>
          <input className="input w-full" value={strategyName} onChange={e => setStrategyName(e.target.value)} placeholder="e.g. v2.0 Release Strategy" />
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1">Project Context *</label>
          <textarea
            className="input w-full h-40 resize-none"
            value={context}
            onChange={e => setContext(e.target.value)}
            placeholder="Describe your project: technology stack, team size, release cadence, key features, compliance requirements, known risks, etc. The more context, the better the strategy."
            disabled={loading}
          />
        </div>
        <div className="bg-slate-800 rounded-lg p-3 text-xs text-slate-400">
          The AI will generate a complete test strategy covering: objectives, scope, test types, risk assessment, entry/exit criteria, environments, and automation approach.
        </div>
        <div className="flex justify-end gap-3 pt-2 border-t border-slate-800">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={handleGenerate} disabled={loading || !context.trim()} className="btn-primary flex items-center gap-2">
            {loading ? <LoadingSpinner size="sm" /> : <Sparkles className="h-4 w-4" />}
            {loading ? 'Generating…' : 'Generate Strategy'}
          </button>
        </div>
      </div>
    </ModalWrap>
  )
}

// ─── Tab: Test Cases ──────────────────────────────────────────────────────────

interface TestCasesTabProps { projectId: string }

function TestCasesTab({ projectId }: TestCasesTabProps) {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [testType, setTestType] = useState('')
  const [priority, setPriority] = useState('')
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showAiGen, setShowAiGen] = useState(false)
  const [selectedCase, setSelectedCase] = useState<ManagedTestCase | null>(null)

  const params: Record<string, unknown> = { page, size: 20 }
  if (status) params.status = status
  if (testType) params.test_type = testType
  if (priority) params.priority = priority
  if (search) params.search = search

  const { data, isLoading, mutate: mutateCases } = useTestCases(params)

  const handleRefresh = useCallback(() => {
    mutateCases()
  }, [mutateCases])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this test case?')) return
    try {
      await testManagementService.deleteCase(id)
      toast.success('Test case deleted')
      mutateCases()
    } catch {
      toast.error('Failed to delete test case')
    }
  }

  const cases = data?.items ?? []

  return (
    <>
      <div className="space-y-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3">
          <input
            className="input flex-1 min-w-40"
            placeholder="Search test cases…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
          />
          <select className="input" value={status} onChange={e => { setStatus(e.target.value); setPage(1) }}>
            <option value="">All Statuses</option>
            {['draft','review_requested','under_review','approved','active','rejected','deprecated'].map(s => (
              <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
            ))}
          </select>
          <select className="input" value={testType} onChange={e => { setTestType(e.target.value); setPage(1) }}>
            <option value="">All Types</option>
            {['functional','integration','e2e','regression','smoke','performance','security','usability','api'].map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select className="input" value={priority} onChange={e => { setPriority(e.target.value); setPage(1) }}>
            <option value="">All Priorities</option>
            {['critical','high','medium','low'].map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <button onClick={() => setShowAiGen(true)} className="btn-secondary flex items-center gap-2 whitespace-nowrap">
            <Sparkles className="h-4 w-4" /> AI Generate
          </button>
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2 whitespace-nowrap">
            <Plus className="h-4 w-4" /> New Test Case
          </button>
        </div>

        {/* Table */}
        <div className="card p-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-48"><LoadingSpinner size="lg" /></div>
          ) : cases.length === 0 ? (
            <EmptyState
              icon={<ClipboardList className="h-10 w-10" />}
              title="No test cases found"
              description="Create your first test case or use AI to generate them from requirements"
              action={
                <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
                  <Plus className="h-4 w-4" /> New Test Case
                </button>
              }
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className="th text-left">Title</th>
                      <th className="th text-left">Type</th>
                      <th className="th text-left">Priority</th>
                      <th className="th text-left">Status</th>
                      <th className="th text-center">AI Score</th>
                      <th className="th text-left">Updated</th>
                      <th className="th text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map(tc => (
                      <tr
                        key={tc.id}
                        className="table-row cursor-pointer"
                        onClick={() => setSelectedCase(tc)}
                      >
                        <td className="td max-w-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-200 truncate">{tc.title}</span>
                            {tc.ai_generated && <Sparkles className="h-3 w-3 text-purple-400 flex-shrink-0" title="AI generated" />}
                          </div>
                          {tc.feature_area && <span className="text-xs text-slate-500">{tc.feature_area}</span>}
                        </td>
                        <td className="td text-slate-400 capitalize">{tc.test_type}</td>
                        <td className="td"><StatusPill status={tc.priority} map={PRIORITY_COLORS} /></td>
                        <td className="td"><StatusPill status={tc.status} map={STATUS_COLORS} /></td>
                        <td className="td text-center"><QualityScore score={tc.ai_quality_score} /></td>
                        <td className="td text-slate-500 whitespace-nowrap">{fmtDate(tc.updated_at)}</td>
                        <td className="td text-right">
                          <button
                            onClick={(e) => handleDelete(tc.id, e)}
                            className="text-slate-600 hover:text-red-400 transition-colors p-1"
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data && <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />}
            </>
          )}
        </div>
      </div>

      {showCreate && (
        <CreateCaseModal
          projectId={projectId}
          onClose={() => setShowCreate(false)}
          onCreated={handleRefresh}
        />
      )}
      {showAiGen && (
        <AIGenerateModal
          projectId={projectId}
          onClose={() => setShowAiGen(false)}
          onCreated={handleRefresh}
        />
      )}
      {selectedCase && (
        <CaseDetailPanel
          caseItem={selectedCase}
          onClose={() => setSelectedCase(null)}
          onRefresh={handleRefresh}
        />
      )}
    </>
  )
}

// ─── Plan Items Expanded View ─────────────────────────────────────────────────

interface PlanItemsViewProps { planId: string; onMutate: () => void }

function PlanItemsView({ planId, onMutate }: PlanItemsViewProps) {
  const { data: items, isLoading, mutate } = usePlanItems(planId)
  const [executing, setExecuting] = useState<string | null>(null)

  const handleExecute = async (itemId: string, execStatus: string) => {
    setExecuting(itemId)
    try {
      await testManagementService.executeItem(planId, itemId, { execution_status: execStatus })
      mutate()
      onMutate()
      toast.success('Execution recorded')
    } catch {
      toast.error('Failed to record execution')
    } finally {
      setExecuting(null)
    }
  }

  const EXEC_COLORS: Record<string, string> = {
    not_run: 'text-slate-400',
    passed:  'text-green-400',
    failed:  'text-red-400',
    blocked: 'text-orange-400',
    skipped: 'text-slate-500',
  }

  if (isLoading) return <div className="flex justify-center py-4"><LoadingSpinner size="sm" /></div>
  if (!items || items.length === 0) return <p className="text-sm text-slate-500 text-center py-4">No test cases in this plan yet</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="th text-left">#</th>
            <th className="th text-left">Test Case</th>
            <th className="th text-left">Status</th>
            <th className="th text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {(items as TestPlanItem[]).map((item, idx) => (
            <tr key={item.id} className="table-row">
              <td className="td text-slate-500">{idx + 1}</td>
              <td className="td text-slate-300">{item.test_case_id.slice(0, 8)}…</td>
              <td className="td">
                <span className={clsx('text-xs font-medium capitalize', EXEC_COLORS[item.execution_status] ?? 'text-slate-400')}>
                  {item.execution_status.replace(/_/g, ' ')}
                </span>
              </td>
              <td className="td text-right">
                <div className="flex items-center justify-end gap-1">
                  {['passed','failed','blocked'].map(s => (
                    <button
                      key={s}
                      disabled={executing === item.id}
                      onClick={() => handleExecute(item.id, s)}
                      className={clsx(
                        'text-xs px-2 py-0.5 rounded transition-colors',
                        s === 'passed'  ? 'bg-green-900/40 text-green-400 hover:bg-green-900/70' :
                        s === 'failed'  ? 'bg-red-900/40 text-red-400 hover:bg-red-900/70' :
                                          'bg-orange-900/40 text-orange-400 hover:bg-orange-900/70'
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Tab: Test Plans ──────────────────────────────────────────────────────────

interface TestPlansTabProps { projectId: string }

function TestPlansTab({ projectId }: TestPlansTabProps) {
  const [page, setPage] = useState(1)
  const [showCreate, setShowCreate] = useState(false)
  const [expandedPlan, setExpandedPlan] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  const { data, isLoading, mutate } = useTestPlans({ page, size: 10 })

  const handleAiCreatePlan = async () => {
    setAiLoading(true)
    try {
      await testManagementService.aiCreatePlan({ project_id: projectId })
      toast.success('AI test plan created')
      mutate()
    } catch {
      toast.error('AI plan creation failed')
    } finally {
      setAiLoading(false)
    }
  }

  const plans = data?.items ?? []

  const PlanProgressBar = ({ plan }: { plan: TestPlan }) => {
    const total = plan.total_cases || 1
    const passedPct = (plan.passed_cases / total) * 100
    const failedPct = (plan.failed_cases / total) * 100
    const blockedPct = (plan.blocked_cases / total) * 100
    const notRunPct = ((total - plan.executed_cases) / total) * 100
    return (
      <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden flex">
        <div className="h-full bg-green-500" style={{ width: `${passedPct}%` }} title={`Passed: ${plan.passed_cases}`} />
        <div className="h-full bg-red-500" style={{ width: `${failedPct}%` }} title={`Failed: ${plan.failed_cases}`} />
        <div className="h-full bg-orange-500" style={{ width: `${blockedPct}%` }} title={`Blocked: ${plan.blocked_cases}`} />
        <div className="h-full bg-slate-600" style={{ width: `${notRunPct}%` }} title="Not run" />
      </div>
    )
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-end gap-3">
          <button
            onClick={handleAiCreatePlan}
            disabled={aiLoading}
            className="btn-secondary flex items-center gap-2"
          >
            {aiLoading ? <LoadingSpinner size="sm" /> : <Sparkles className="h-4 w-4" />}
            AI Create Plan
          </button>
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
            <Plus className="h-4 w-4" /> New Plan
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-48"><LoadingSpinner size="lg" /></div>
        ) : plans.length === 0 ? (
          <EmptyState
            icon={<BookOpen className="h-10 w-10" />}
            title="No test plans"
            description="Create a test plan to organize and track test execution"
            action={
              <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
                <Plus className="h-4 w-4" /> New Plan
              </button>
            }
          />
        ) : (
          <div className="space-y-3">
            {plans.map(plan => (
              <div key={plan.id} className="card p-0">
                <div
                  className="p-4 cursor-pointer hover:bg-slate-800/50 transition-colors rounded-xl"
                  onClick={() => setExpandedPlan(expandedPlan === plan.id ? null : plan.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="text-sm font-semibold text-slate-100 truncate">{plan.name}</h3>
                        <StatusPill status={plan.status} map={PLAN_STATUS_COLORS} />
                        {plan.ai_generated && <Sparkles className="h-3.5 w-3.5 text-purple-400" title="AI generated" />}
                      </div>
                      {plan.description && <p className="text-xs text-slate-400 mb-2 truncate">{plan.description}</p>}
                      <div className="space-y-1">
                        <PlanProgressBar plan={plan} />
                        <div className="flex items-center gap-4 text-xs text-slate-500">
                          <span className="text-green-400">{plan.passed_cases} passed</span>
                          <span className="text-red-400">{plan.failed_cases} failed</span>
                          <span className="text-orange-400">{plan.blocked_cases} blocked</span>
                          <span>{plan.total_cases - plan.executed_cases} not run</span>
                          <span className="ml-auto">{plan.executed_cases}/{plan.total_cases} executed</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <div className="text-right text-xs text-slate-500">
                        {plan.planned_start_date && <p>Start: {fmtDate(plan.planned_start_date)}</p>}
                        {plan.planned_end_date && <p>End: {fmtDate(plan.planned_end_date)}</p>}
                      </div>
                      {expandedPlan === plan.id
                        ? <ChevronUp className="h-4 w-4 text-slate-400" />
                        : <ChevronDown className="h-4 w-4 text-slate-400" />
                      }
                    </div>
                  </div>
                </div>
                {expandedPlan === plan.id && (
                  <div className="border-t border-slate-700/50 p-4">
                    <PlanItemsView planId={plan.id} onMutate={mutate} />
                  </div>
                )}
              </div>
            ))}
            {data && <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />}
          </div>
        )}
      </div>

      {showCreate && (
        <CreatePlanModal
          projectId={projectId}
          onClose={() => setShowCreate(false)}
          onCreated={mutate}
        />
      )}
    </>
  )
}

// ─── Tab: Strategy ────────────────────────────────────────────────────────────

interface StrategyTabProps { projectId: string }

function StrategyTab({ projectId }: StrategyTabProps) {
  const [showGenerate, setShowGenerate] = useState(false)
  const [expandedSection, setExpandedSection] = useState<string | null>('objective')
  const { data: strategies, isLoading, mutate } = useStrategies()

  const strategy = strategies?.[0] as TestStrategy | undefined

  const AccordionSection = ({
    id, title, children
  }: { id: string; title: string; children: React.ReactNode }) => (
    <div className="border border-slate-700 rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/50 transition-colors"
        onClick={() => setExpandedSection(expandedSection === id ? null : id)}
      >
        <span className="text-sm font-medium text-slate-200">{title}</span>
        {expandedSection === id
          ? <ChevronUp className="h-4 w-4 text-slate-400" />
          : <ChevronRight className="h-4 w-4 text-slate-400" />
        }
      </button>
      {expandedSection === id && (
        <div className="p-4 border-t border-slate-700/50 bg-slate-800/30">
          {children}
        </div>
      )}
    </div>
  )

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-end">
          <button onClick={() => setShowGenerate(true)} className="btn-primary flex items-center gap-2">
            <Sparkles className="h-4 w-4" /> Generate Strategy
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-48"><LoadingSpinner size="lg" /></div>
        ) : !strategy ? (
          <EmptyState
            icon={<BarChart2 className="h-10 w-10" />}
            title="No test strategy"
            description="Generate a comprehensive AI-powered test strategy for your project"
            action={
              <button onClick={() => setShowGenerate(true)} className="btn-primary flex items-center gap-2">
                <Sparkles className="h-4 w-4" /> Generate Strategy
              </button>
            }
          />
        ) : (
          <div className="space-y-3">
            {/* Header card */}
            <div className="card">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-base font-semibold text-slate-100">{strategy.name}</h3>
                  <div className="flex items-center gap-3 mt-1">
                    <StatusPill status={strategy.status} map={PLAN_STATUS_COLORS} />
                    <span className="text-xs text-slate-500">v{strategy.version_label}</span>
                    {strategy.ai_generated && (
                      <span className="text-xs text-purple-400 flex items-center gap-1">
                        <Sparkles className="h-3 w-3" /> AI Generated
                      </span>
                    )}
                    <span className="text-xs text-slate-500">Created {fmtDate(strategy.created_at)}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Accordion sections */}
            {strategy.objective && (
              <AccordionSection id="objective" title="Objective">
                <p className="text-sm text-slate-300 whitespace-pre-wrap">{strategy.objective}</p>
              </AccordionSection>
            )}
            {(strategy.scope || strategy.out_of_scope) && (
              <AccordionSection id="scope" title="Scope">
                {strategy.scope && (
                  <div className="mb-3">
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">In Scope</p>
                    <p className="text-sm text-slate-300 whitespace-pre-wrap">{strategy.scope}</p>
                  </div>
                )}
                {strategy.out_of_scope && (
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Out of Scope</p>
                    <p className="text-sm text-slate-300 whitespace-pre-wrap">{strategy.out_of_scope}</p>
                  </div>
                )}
              </AccordionSection>
            )}
            {strategy.test_types && strategy.test_types.length > 0 && (
              <AccordionSection id="test_types" title="Test Types">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr>
                        <th className="th text-left">Type</th>
                        <th className="th text-left">Priority</th>
                        <th className="th text-left">Tools</th>
                        <th className="th text-right">Coverage Target</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategy.test_types.map((tt, i) => (
                        <tr key={i} className="table-row">
                          <td className="td font-medium text-slate-200 capitalize">{tt.type}</td>
                          <td className="td"><StatusPill status={tt.priority} map={PRIORITY_COLORS} /></td>
                          <td className="td text-slate-400">{tt.tools.join(', ')}</td>
                          <td className="td text-right tabular-nums text-blue-400">{tt.coverage_target_pct}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </AccordionSection>
            )}
            {strategy.risk_assessment && strategy.risk_assessment.length > 0 && (
              <AccordionSection id="risks" title="Risk Assessment">
                <div className="space-y-2">
                  {strategy.risk_assessment.map((r, i) => (
                    <div key={i} className="bg-slate-800 rounded-lg p-3 grid grid-cols-2 gap-3 text-sm">
                      <div className="col-span-2 font-medium text-slate-200">{r.risk}</div>
                      <div><span className="text-xs text-slate-500">Likelihood: </span><span className="text-slate-300 capitalize">{r.likelihood}</span></div>
                      <div><span className="text-xs text-slate-500">Impact: </span><span className="text-slate-300 capitalize">{r.impact}</span></div>
                      <div className="col-span-2 text-xs text-slate-400"><span className="text-slate-500">Mitigation: </span>{r.mitigation}</div>
                    </div>
                  ))}
                </div>
              </AccordionSection>
            )}
            {(strategy.entry_criteria?.length || strategy.exit_criteria?.length) && (
              <AccordionSection id="criteria" title="Entry / Exit Criteria">
                <div className="grid grid-cols-2 gap-4">
                  {strategy.entry_criteria && strategy.entry_criteria.length > 0 && (
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Entry Criteria</p>
                      <ul className="space-y-1">
                        {strategy.entry_criteria.map((c, i) => (
                          <li key={i} className="flex items-center gap-2 text-xs text-slate-300">
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />{c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {strategy.exit_criteria && strategy.exit_criteria.length > 0 && (
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Exit Criteria</p>
                      <ul className="space-y-1">
                        {strategy.exit_criteria.map((c, i) => (
                          <li key={i} className="flex items-center gap-2 text-xs text-slate-300">
                            <CheckCircle2 className="h-3.5 w-3.5 text-blue-500 flex-shrink-0" />{c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </AccordionSection>
            )}
            {strategy.environments && strategy.environments.length > 0 && (
              <AccordionSection id="envs" title="Test Environments">
                <div className="grid grid-cols-3 gap-3">
                  {strategy.environments.map((env, i) => (
                    <div key={i} className="bg-slate-800 rounded-lg p-3">
                      <p className="text-sm font-medium text-slate-200">{env.name}</p>
                      <p className="text-xs text-slate-500 capitalize mt-0.5">{env.type}</p>
                      <p className="text-xs text-slate-400 mt-1">{env.purpose}</p>
                    </div>
                  ))}
                </div>
              </AccordionSection>
            )}
            {strategy.automation_approach && (
              <AccordionSection id="automation" title="Automation Approach">
                <p className="text-sm text-slate-300 whitespace-pre-wrap">{strategy.automation_approach}</p>
              </AccordionSection>
            )}
          </div>
        )}
      </div>

      {showGenerate && (
        <GenerateStrategyModal
          projectId={projectId}
          onClose={() => setShowGenerate(false)}
          onCreated={mutate}
        />
      )}
    </>
  )
}

// ─── Tab: Reviews ─────────────────────────────────────────────────────────────

interface ReviewsTabProps { projectId: string }

function ReviewsTab({ projectId: _projectId }: ReviewsTabProps) {
  const [reviewingId, setReviewingId] = useState<string | null>(null)
  const { data, isLoading, mutate } = useTestCases({ status: 'review_requested', size: 50 })

  const cases = data?.items ?? []

  const handleAiReview = async (tc: ManagedTestCase) => {
    setReviewingId(tc.id)
    try {
      await testManagementService.aiReview(tc.id)
      toast.success('AI review complete')
      mutate()
    } catch {
      toast.error('AI review failed')
    } finally {
      setReviewingId(null)
    }
  }

  const handleReviewAction = async (tc: ManagedTestCase, action: string) => {
    try {
      await testManagementService.reviewAction(tc.id, action)
      toast.success(`Test case ${action}`)
      mutate()
    } catch {
      toast.error('Action failed')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">{cases.length} test cases awaiting review</p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-48"><LoadingSpinner size="lg" /></div>
      ) : cases.length === 0 ? (
        <EmptyState
          icon={<Shield className="h-10 w-10" />}
          title="No pending reviews"
          description="Test cases submitted for review will appear here"
        />
      ) : (
        <div className="space-y-3">
          {cases.map(tc => (
            <div key={tc.id} className="card">
              <div className="flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="text-sm font-medium text-slate-200 truncate">{tc.title}</h4>
                    <StatusPill status={tc.priority} map={PRIORITY_COLORS} />
                    <span className="text-xs text-slate-500 capitalize">{tc.test_type}</span>
                  </div>
                  {tc.feature_area && <p className="text-xs text-slate-500 mb-2">{tc.feature_area}</p>}
                  {tc.objective && <p className="text-xs text-slate-400 line-clamp-2">{tc.objective}</p>}
                  <div className="flex items-center gap-4 mt-2">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Clock className="h-3.5 w-3.5" />
                      Requested {fmtDate(tc.updated_at)}
                    </div>
                    {tc.ai_quality_score != null && (
                      <div className="flex items-center gap-1.5 text-xs text-slate-500">
                        <Star className="h-3.5 w-3.5" />
                        AI Score: <QualityScore score={tc.ai_quality_score} />
                      </div>
                    )}
                    {tc.steps && (
                      <span className="text-xs text-slate-500">{tc.steps.length} steps</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleAiReview(tc)}
                    disabled={reviewingId === tc.id}
                    className="btn-secondary flex items-center gap-1.5 text-xs"
                  >
                    {reviewingId === tc.id ? <LoadingSpinner size="sm" /> : <Sparkles className="h-3.5 w-3.5" />}
                    AI Review
                  </button>
                  <button
                    onClick={() => handleReviewAction(tc, 'approve')}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-green-900/40 text-green-400 hover:bg-green-900/70 transition-colors"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                  </button>
                  <button
                    onClick={() => handleReviewAction(tc, 'request_changes')}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-amber-900/40 text-amber-400 hover:bg-amber-900/70 transition-colors"
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Changes
                  </button>
                  <button
                    onClick={() => handleReviewAction(tc, 'reject')}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-red-900/40 text-red-400 hover:bg-red-900/70 transition-colors"
                  >
                    <XCircle className="h-3.5 w-3.5" /> Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Tab: Audit Log ───────────────────────────────────────────────────────────

interface AuditTabProps { projectId: string }

function AuditTab({ projectId }: AuditTabProps) {
  const [page, setPage] = useState(1)
  const [entityType, setEntityType] = useState('')

  const { data, isLoading } = useAuditLog({
    page,
    size: 25,
    entity_type: entityType || undefined,
  })

  const entries = data?.items ?? []

  const ACTION_COLORS: Record<string, string> = {
    created:          'text-green-400',
    updated:          'text-blue-400',
    deleted:          'text-red-400',
    status_changed:   'text-amber-400',
    review_requested: 'text-purple-400',
    approved:         'text-emerald-400',
    rejected:         'text-red-400',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select className="input" value={entityType} onChange={e => { setEntityType(e.target.value); setPage(1) }}>
          <option value="">All Entity Types</option>
          {['test_case','test_plan','test_strategy','test_case_review'].map(t => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      <div className="card p-0">
        {isLoading ? (
          <div className="flex items-center justify-center h-48"><LoadingSpinner size="lg" /></div>
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<History className="h-10 w-10" />}
            title="No audit log entries"
            description="All changes to test cases, plans and strategies are tracked here"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="th text-left">Timestamp</th>
                    <th className="th text-left">Entity Type</th>
                    <th className="th text-left">Action</th>
                    <th className="th text-left">Actor</th>
                    <th className="th text-left">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map(entry => (
                    <tr key={entry.id} className="table-row">
                      <td className="td text-slate-500 whitespace-nowrap text-xs">{fmtDateTime(entry.created_at)}</td>
                      <td className="td">
                        <span className="text-xs text-slate-400 capitalize">{entry.entity_type.replace(/_/g, ' ')}</span>
                      </td>
                      <td className="td">
                        <span className={clsx('text-xs font-medium capitalize', ACTION_COLORS[entry.action] ?? 'text-slate-400')}>
                          {entry.action.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="td">
                        <div className="flex items-center gap-1.5 text-xs text-slate-400">
                          <User className="h-3.5 w-3.5" />
                          {entry.actor_name ?? entry.actor_id?.slice(0, 8) ?? 'System'}
                        </div>
                      </td>
                      <td className="td text-xs text-slate-500 max-w-xs truncate">{entry.details ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data && <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />}
          </>
        )}
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function TestManagementPage() {
  const [activeTab, setActiveTab] = useState<Tab>('Test Cases')
  const project = useProjectStore(s => s.activeProject)
  const projectId = useProjectStore(s => s.activeProjectId)

  if (!project || !projectId) {
    return (
      <EmptyState
        icon={<ClipboardList className="h-10 w-10" />}
        title="No project selected"
        description="Select a project from the top bar to manage test cases"
      />
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Test Case Management"
        subtitle={`Manage test cases, plans, strategies and reviews for ${project.name}`}
      />

      {/* Tab navigation */}
      <div className="flex items-center gap-1 border-b border-slate-800 pb-0">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors -mb-px border-b-2',
              activeTab === tab
                ? 'border-blue-500 text-blue-400 bg-slate-800/40'
                : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-slate-800/20'
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'Test Cases'  && <TestCasesTab projectId={projectId} />}
        {activeTab === 'Test Plans'  && <TestPlansTab projectId={projectId} />}
        {activeTab === 'Strategy'    && <StrategyTab projectId={projectId} />}
        {activeTab === 'Reviews'     && <ReviewsTab projectId={projectId} />}
        {activeTab === 'Audit Log'   && <AuditTab projectId={projectId} />}
      </div>
    </div>
  )
}
