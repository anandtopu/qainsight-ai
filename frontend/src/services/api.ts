import axios, { AxiosError } from 'axios'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/authStore'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: attach token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config;
})

// Response interceptor: surface API errors as toasts
api.interceptors.response.use(
  (res) => res,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      // Auto logout on 401
      useAuthStore.getState().logout()
    }
    
    const msg = error.response?.data?.detail || error.message || 'Request failed'
    if (error.response?.status !== 404 && error.response?.status !== 401) {
      toast.error(msg)
    }
    return Promise.reject(error)
  }
)
