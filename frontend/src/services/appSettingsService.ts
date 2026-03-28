import type { AxiosResponse } from 'axios'
import { api } from './api'

export interface SmtpConfigRead {
  enabled: boolean
  host: string
  port: number
  user: string | null
  from_address: string
  tls: boolean
  password_set: boolean
}

export interface SmtpConfigUpdate {
  enabled: boolean
  host: string
  port: number
  user: string | null
  password: string | null  // null = keep existing
  from_address: string
  tls: boolean
}

export interface SmtpTestResult {
  success: boolean
  message: string
}

export const appSettingsService = {
  getSmtpConfig(): Promise<SmtpConfigRead> {
    return api.get<SmtpConfigRead>('/api/v1/settings/smtp').then((r: AxiosResponse<SmtpConfigRead>) => r.data)
  },

  updateSmtpConfig(payload: SmtpConfigUpdate): Promise<SmtpConfigRead> {
    return api.put<SmtpConfigRead>('/api/v1/settings/smtp', payload).then((r: AxiosResponse<SmtpConfigRead>) => r.data)
  },

  testSmtpConfig(): Promise<SmtpTestResult> {
    return api.post<SmtpTestResult>('/api/v1/settings/smtp/test').then((r: AxiosResponse<SmtpTestResult>) => r.data)
  },
}
