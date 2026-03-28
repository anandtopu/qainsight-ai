import useSWR, { type SWRConfiguration } from 'swr'
import { useProjectStore } from '@/store/projectStore'

export function useActiveProjectId() {
  return useProjectStore((state) => state.activeProjectId)
}

export function useProjectScopedSWR<Data>(
  baseKey: string,
  fetcher: (projectId: string) => Promise<Data>,
  options?: SWRConfiguration<Data>,
  deps: unknown[] = [],
) {
  const projectId = useActiveProjectId()

  return useSWR<Data>(
    projectId ? [baseKey, projectId, ...deps] : null,
    () => fetcher(projectId as string),
    options,
  )
}
