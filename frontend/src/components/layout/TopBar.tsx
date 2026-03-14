import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '@/store/projectStore'
import { projectsService, type Project } from '@/services/projectsService'

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
    </header>
  )
}
