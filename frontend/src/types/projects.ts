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
