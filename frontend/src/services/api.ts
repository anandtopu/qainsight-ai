import axios, { AxiosError } from 'axios'
import toast from 'react-hot-toast'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

// Response interceptor: surface API errors as toasts
api.interceptors.response.use(
  (res) => res,
  (error: AxiosError<{ detail?: string }>) => {
    const msg = error.response?.data?.detail || error.message || 'Request failed'
    if (error.response?.status !== 404) toast.error(msg)
    return Promise.reject(error)
  }
)
