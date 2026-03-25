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

const chatService = {
  listSessions: () => api.get<ChatSession[]>('/api/v1/chat/sessions'),

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
