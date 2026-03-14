import { NavLink } from 'react-router-dom'
import {
  BarChart3, Bug, FlaskConical, Gauge, GitBranch,
  LayoutDashboard, Search, Settings, ShieldCheck, TrendingUp,
} from 'lucide-react'
import { clsx } from 'clsx'

const NAV = [
  { to: '/overview',  icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/runs',      icon: GitBranch,       label: 'Test Runs'  },
  { to: '/coverage',  icon: ShieldCheck,     label: 'Coverage'   },
  { to: '/failures',  icon: Bug,             label: 'Failures'   },
  { to: '/trends',    icon: TrendingUp,      label: 'Trends'     },
  { to: '/defects',   icon: Gauge,           label: 'Defects'    },
  { to: '/search',    icon: Search,          label: 'Search'     },
  { to: '/projects',  icon: FlaskConical,    label: 'Projects'   },
]

export default function Sidebar() {
  return (
    <aside className="w-56 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <BarChart3 className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-100">QA Insight AI</p>
            <p className="text-[10px] text-slate-500">v3.0</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx('sidebar-link', isActive && 'active')
            }
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-slate-800">
        <NavLink
          to="/settings"
          className={({ isActive }) => clsx('sidebar-link', isActive && 'active')}
        >
          <Settings className="h-4 w-4 flex-shrink-0" />
          Settings
        </NavLink>
      </div>
    </aside>
  )
}
