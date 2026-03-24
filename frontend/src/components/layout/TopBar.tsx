import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '@/store/projectStore'
import { projectsService, type Project } from '@/services/projectsService'
import { useAuthStore } from '@/store/authStore'
import { UserCircle, LogOut } from 'lucide-react'

export default function TopBar() {
  const navigate = useNavigate()
  const { activeProject, setActiveProject } = useProjectStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [searchVal, setSearchVal] = useState('')

  useEffect(() => {
    projectsService.list().then(setProjects).catch(() => {})
  }, [])

  const handleSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchVal.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchVal.trim())}`)
      setSearchVal('')
    }
  }

  return (
    <header className="h-14 border-b border-slate-800 bg-slate-900/80 backdrop-blur flex items-center px-6 gap-4 flex-shrink-0">
      {/* Global search */}
      <div className="flex-1 max-w-md relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
        <input
          type="text"
          placeholder="Search tests, errors… (Enter)"
          className="input pl-9 h-9 text-sm"
          value={searchVal}
          onChange={e => setSearchVal(e.target.value)}
          onKeyDown={handleSearch}
        />
      </div>

      {/* Project selector */}
      <select
        className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        value={activeProject?.id ?? ''}
        onChange={e => {
          const p = projects.find(x => x.id === e.target.value) ?? null
          setActiveProject(p)
        }}
      >
        <option value="">— Select project —</option>
        {projects.map(p => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>

      {/* User profile */}
      <div className="flex items-center gap-3 ml-4 border-l border-slate-700 pl-4 relative group cursor-pointer h-full">
        <UserCircle className="w-8 h-8 text-slate-400" />
        <div className="flex flex-col justify-center">
          <span className="text-sm font-medium text-slate-200 leading-none">
            {useAuthStore(s => s.user?.full_name || s.user?.username || 'User')}
          </span>
          <span className="text-xs text-slate-500 mt-1 leading-none">{useAuthStore(s => s.user?.role || '')}</span>
        </div>
        
        {/* Dropdown on hover */}
        <div className="absolute right-0 top-12 mt-2 w-48 bg-slate-800 border border-slate-700 rounded-md shadow-lg py-1 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity z-50">
          <div className="px-4 py-2 border-b border-slate-700">
            <p className="text-sm text-slate-300 font-medium">{useAuthStore(s => s.user?.email || '')}</p>
          </div>
          <button 
            onClick={() => useAuthStore.getState().logout()}
            className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-slate-700/50 flex items-center gap-2 transition-colors mt-1"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </div>
    </header>
  )
}
