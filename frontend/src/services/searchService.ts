import { api } from './api'

export const searchService = {
  search: (params: {
    q: string
    project_id?: string
    status?: string
    days?: number
    page?: number
    size?: number
  }) => api.get('/api/v1/search', { params }).then(r => r.data),
}
