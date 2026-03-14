import { clsx } from 'clsx'

interface Props { status: string; className?: string }

const MAP: Record<string, string> = {
  PASSED:  'badge-passed',
  FAILED:  'badge-failed',
  BROKEN:  'badge-broken',
  SKIPPED: 'badge-skipped',
  FLAKY:   'badge-flaky',
  UNKNOWN: 'badge bg-slate-800 text-slate-400 border border-slate-600',
  // run statuses
  IN_PROGRESS: 'badge bg-blue-900/50 text-blue-300 border border-blue-700/50',
  PASSED_RUN:  'badge-passed',
  STOPPED:     'badge bg-slate-800 text-slate-400 border border-slate-600',
}

export default function StatusBadge({ status, className }: Props) {
  const cls = MAP[status?.toUpperCase()] ?? MAP.UNKNOWN
  return <span className={clsx(cls, className)}>{status}</span>
}
