import useSWR from 'swr'
import { releasesService } from '@/services/releasesService'
import { useProjectStore } from '@/store/projectStore'

export function useReleases(status?: string) {
  const projectId = useProjectStore(s => s.activeProjectId)
  return useSWR(
    projectId ? ['releases-list', projectId, status ?? ''] : null,
    () => releasesService.list(projectId as string, status),
    { refreshInterval: 30_000 },
  )
}

export function useRelease(id: string | null) {
  return useSWR(
    id ? ['release-detail', id] : null,
    () => releasesService.get(id as string),
    { revalidateOnFocus: false },
  )
}
