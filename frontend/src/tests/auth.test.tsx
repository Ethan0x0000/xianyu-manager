import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import ProtectedRoute from '../components/ProtectedRoute'
import * as authApi from '../api/auth'

vi.mock('../api/auth', () => ({
  verifyApi: vi.fn(),
}))

describe('auth infrastructure', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useAuthStore.setState({
      isAuthenticated: false,
      isInitializing: false,
    })
  })

  it('redirects unauthenticated users away from protected routes', async () => {
    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
        initialEntries={['/dashboard']}
      >
        <Routes>
          <Route path="/login" element={<div>登录页</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<div>仪表盘</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('登录页')).toBeInTheDocument()
    expect(screen.queryByText('仪表盘')).not.toBeInTheDocument()
  })

  it('shows a loading gate while auth initialization is still in progress', () => {
    useAuthStore.setState({
      isAuthenticated: false,
      isInitializing: true,
    })

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
        initialEntries={['/dashboard']}
      >
        <Routes>
          <Route path="/login" element={<div>登录页</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<div>仪表盘</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('正在验证登录状态…')).toBeInTheDocument()
    expect(screen.queryByText('登录页')).not.toBeInTheDocument()
    expect(screen.queryByText('仪表盘')).not.toBeInTheDocument()
  })

  it('keeps auth state in memory after successful verification without localStorage', async () => {
    vi.mocked(authApi.verifyApi).mockResolvedValue({ is_admin: true, username: 'admin' })

    await act(async () => {
      await useAuthStore.getState().verifyToken()
    })

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
      expect(useAuthStore.getState().isInitializing).toBe(false)
      expect(localStorage.getItem('auth_token')).toBeNull()
    })
  })

  it('hydrates from the server session even when no local token exists', async () => {
    vi.mocked(authApi.verifyApi).mockResolvedValue({ is_admin: true, username: 'admin' })

    await act(async () => {
      await useAuthStore.getState().hydrate()
    })

    await waitFor(() => {
      expect(authApi.verifyApi).toHaveBeenCalledTimes(1)
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
      expect(useAuthStore.getState().isInitializing).toBe(false)
      expect(localStorage.getItem('auth_token')).toBeNull()
    })
  })

  it('clears auth state when server-side session verification fails during hydration', async () => {
    vi.mocked(authApi.verifyApi).mockRejectedValue({ response: { status: 401 } })

    await act(async () => {
      await useAuthStore.getState().hydrate()
    })

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false)
      expect(useAuthStore.getState().isInitializing).toBe(false)
      expect(localStorage.getItem('auth_token')).toBeNull()
    })
  })
})
