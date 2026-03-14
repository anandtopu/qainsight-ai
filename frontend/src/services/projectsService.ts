import { api } from './api'

export interface Project {
  id: string
  name: string
  slug: string
  description?: string
  jira_project_key?: string
  ocp_namespace?: string
  is_active: boolean
  created_at: string
}

export const projectsService = {
  list: (): Promise<Project[]> => api.get('/api/v1/projects').then(r => r.data),
  get:  (id: string): Promise<Project> => api.get(`/api/v1/projects/${id}`).then(r => r.data),
  create: (data: Partial<Project>) => api.post('/api/v1/projects', data).then(r => r.data),
  delete: (id: string) => api.delete(`/api/v1/projects/${id}`),
}
