import { api } from './api'

export type NotificationChannel = 'email' | 'slack' | 'teams'

export type NotificationEventType =
  | 'run_failed'
  | 'run_passed'
  | 'high_failure_rate'
  | 'ai_analysis_complete'
  | 'quality_gate_failed'
  | 'flaky_test_detected'

export interface NotificationPreference {
  id: string
  user_id: string
  project_id: string | null
  channel: NotificationChannel
  enabled: boolean
  events: NotificationEventType[]
  failure_rate_threshold: number
  email_override: string | null
  slack_webhook_url: string | null
  teams_webhook_url: string | null
  created_at: string
  updated_at: string | null
}

export interface NotificationPreferencePayload {
  project_id?: string | null
  channel: NotificationChannel
  enabled: boolean
  events: NotificationEventType[]
  failure_rate_threshold: number
  email_override?: string | null
  slack_webhook_url?: string | null
  teams_webhook_url?: string | null
}

export interface NotificationLog {
  id: string
  channel: NotificationChannel
  event_type: NotificationEventType
  title: string
  body: string
  status: 'pending' | 'sent' | 'failed'
  is_read: boolean
  sent_at: string | null
  created_at: string
}

export const notificationService = {
  listPreferences: () =>
    api.get<NotificationPreference[]>('/api/v1/notifications/preferences').then(r => r.data),

  upsertPreference: (data: NotificationPreferencePayload) =>
    api.post<NotificationPreference>('/api/v1/notifications/preferences', data).then(r => r.data),

  updatePreference: (id: string, data: NotificationPreferencePayload) =>
    api.put<NotificationPreference>(`/api/v1/notifications/preferences/${id}`, data).then(r => r.data),

  deletePreference: (id: string) =>
    api.delete(`/api/v1/notifications/preferences/${id}`),

  listHistory: (unreadOnly = false, limit = 50) =>
    api
      .get<NotificationLog[]>('/api/v1/notifications/history', {
        params: { unread_only: unreadOnly, limit },
      })
      .then(r => r.data),

  unreadCount: () =>
    api.get<{ unread: number }>('/api/v1/notifications/history/unread-count').then(r => r.data),

  markRead: (id: string) =>
    api.post(`/api/v1/notifications/history/${id}/read`),

  markAllRead: () =>
    api.post('/api/v1/notifications/history/read-all'),

  sendTest: (channel: NotificationChannel, preferenceId?: string) =>
    api
      .post('/api/v1/notifications/test', { channel, preference_id: preferenceId ?? null })
      .then(r => r.data),
}
