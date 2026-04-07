import axios, { type AxiosError } from 'axios'
import type { ApiError } from './types'

export const apiClient = axios.create({
  baseURL: '/api',
  withCredentials: true,
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
