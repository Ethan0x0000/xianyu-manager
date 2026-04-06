import { apiClient } from './client'
import type { LoginRequest, LoginResponse, LogoutResponse, VerifyResponse } from './types'

export async function loginApi(payload: LoginRequest) {
  const response = await apiClient.post<LoginResponse>('/auth/login', payload)
  return response.data
}

export async function logoutApi() {
  const response = await apiClient.post<LogoutResponse>('/auth/logout')
  return response.data
}

export async function verifyApi() {
  const response = await apiClient.get<VerifyResponse>('/auth/verify')
  return response.data
}
