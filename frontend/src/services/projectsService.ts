import type { Project } from '@/types/projects'
import { deleteData, getData, postData } from './http'

export const projectsService = {
  list: (): Promise<Project[]> => getData('/api/v1/projects'),
  get: (id: string): Promise<Project> => getData(`/api/v1/projects/${id}`),
  create: (data: Partial<Project>) => postData<Project, Partial<Project>>('/api/v1/projects', data),
  delete: (id: string) => deleteData(`/api/v1/projects/${id}`),
}
