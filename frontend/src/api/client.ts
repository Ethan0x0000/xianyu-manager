import axios, { AxiosHeaders, type AxiosError } from 'axios'
import type { ApiError } from './types'

export const AUTH_TOKEN_STORAGE_KEY = 'auth_token'

export function getStoredAuthToken() {
  if (typeof window === 'undefined') {
    return null
  }

  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
}

export const apiClient = axios.create({
  baseURL: '/api',
})

apiClient.interceptors.request.use((config) => {
  const token = getStoredAuthToken()
  const headers = AxiosHeaders.from(config.headers)

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  config.headers = headers
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      const { handleUnauthorized } = await import('../stores/authStore')
      handleUnauthorized()
    }

    return Promise.reject(error)
  },
)
