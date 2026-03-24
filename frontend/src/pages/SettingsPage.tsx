import { Link } from 'react-router-dom'
import { Bot, Database, Key, Bell, ChevronRight } from 'lucide-react'
import PageHeader from '@/components/ui/PageHeader'

const sections = [
  {
    icon: Bot,
    title: 'AI Configuration',
    desc: 'LLM provider, model selection, offline mode toggle',
    href: null,
  },
  {
    icon: Database,
    title: 'Data & Storage',
    desc: 'PostgreSQL, MongoDB, MinIO, ChromaDB connection settings',
    href: null,
  },
  {
    icon: Key,
    title: 'Integrations',
    desc: 'Jira, Splunk, OpenShift API, Slack, Microsoft Teams',
    href: null,
  },
  {
    icon: Bell,
    title: 'Notifications',
    desc: 'Email, Slack, and Teams alert rules per project',
    href: '/settings/notifications',
  },
]

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Settings" subtitle="Application configuration and integrations" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {sections.map(({ icon: Icon, title, desc, href }) => {
          const inner = (
            <div className={`card hover:border-slate-600 transition-colors ${href ? 'cursor-pointer' : 'cursor-default'}`}>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-slate-800 rounded-lg"><Icon className="h-4 w-4 text-slate-400" /></div>
                <h3 className="font-semibold text-slate-200 flex-1">{title}</h3>
                {href && <ChevronRight className="h-4 w-4 text-slate-500" />}
              </div>
              <p className="text-sm text-slate-400 pl-11">{desc}</p>
            </div>
          )
          return href ? (
            <Link key={title} to={href} className="block">
              {inner}
            </Link>
          ) : (
            <div key={title}>{inner}</div>
          )
        })}
      </div>
      <div className="card">
        <h3 className="font-semibold text-slate-200 mb-3">LLM Provider</h3>
        <div className="space-y-2 text-sm text-slate-400">
          <p>Current provider: <span className="text-blue-400 font-mono">{import.meta.env.VITE_LLM_PROVIDER ?? 'ollama'}</span></p>
          <p>Offline mode: <span className="text-emerald-400">enabled</span> — all AI runs locally, no data leaves your network</p>
          <p className="text-slate-500 text-xs mt-3">Configure via environment variables in .env — see documentation</p>
        </div>
      </div>
    </div>
  )
}
