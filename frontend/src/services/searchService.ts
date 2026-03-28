import type { SearchResponse } from '@/types/search'
import { getData } from './http'

export const searchService = {
  search: (params: {
    q: string
    project_id?: string
    status?: string
    days?: number
    page?: number
    size?: number
  }) => getData<SearchResponse>('/api/v1/search', { params }),
}
