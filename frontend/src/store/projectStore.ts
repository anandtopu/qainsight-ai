import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Project } from '@/services/projectsService'

interface ProjectStore {
  activeProjectId: string | null
  activeProject: Project | null
  setActiveProject: (project: Project | null) => void
}

export const useProjectStore = create<ProjectStore>()(
  persist(
    (set) => ({
      activeProjectId: null,
      activeProject: null,
      setActiveProject: (project) =>
        set({ activeProject: project, activeProjectId: project?.id ?? null }),
    }),
    { name: 'qainsight-active-project' }
  )
)
