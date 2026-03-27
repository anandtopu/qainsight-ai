import { api } from './api'

export interface ChatSession {
  id: string
  project_id: string | null
  title: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  sources: Array<{ type: string; id?: string; label?: string }> | null
  created_at: string
}

export interface RunSummary {
  test_run_id: string
  project_id: string
  build_number: string
  executive_summary: string
  markdown_report: string | null   // null for stubs (AI analysis pending)
  anomaly_count: number
  is_regression: boolean
  analysis_count: number
  generated_at: string
  is_stub?: boolean                // true = stats-based, no LLM summary yet
}

const chatService = {
  listSessions: () => api.get<ChatSession[]>('/api/v1/chat/sessions'),

  getRunSummaries: (projectId?: string | null, days = 5) =>
    api.get<RunSummary[]>('/api/v1/chat/run-summaries', {
      params: { project_id: projectId ?? undefined, days },
    }),

  createSession: (payload: { project_id?: string; title?: string }) =>
    api.post<ChatSession>('/api/v1/chat/sessions', payload),

  deleteSession: (sessionId: string) =>
    api.delete(`/api/v1/chat/sessions/${sessionId}`),

  getMessages: (sessionId: string, limit = 50) =>
    api.get<ChatMessage[]>(`/api/v1/chat/sessions/${sessionId}/messages`, {
      params: { limit },
    }),

  sendMessage: (
    sessionId: string,
    message: string,
    projectId?: string | null,
  ) =>
    api.post<{ session_id: string; reply: string; sources: unknown[] }>(
      `/api/v1/chat/sessions/${sessionId}/messages`,
      { message, project_id: projectId ?? undefined },
    ),
}

export default chatService
