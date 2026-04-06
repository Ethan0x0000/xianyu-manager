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
      token: null,
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

  it('keeps a stored token after successful verification', async () => {
    vi.mocked(authApi.verifyApi).mockResolvedValue({ username: 'admin' })

    await act(async () => {
      useAuthStore.getState().login('valid-token')
      await useAuthStore.getState().verifyToken()
    })

    await waitFor(() => {
      expect(useAuthStore.getState().token).toBe('valid-token')
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
      expect(localStorage.getItem('auth_token')).toBe('valid-token')
    })
  })

  it('clears an invalid stored token during hydration', async () => {
    localStorage.setItem('auth_token', 'expired-token')
    vi.mocked(authApi.verifyApi).mockRejectedValue({ response: { status: 401 } })

    await act(async () => {
      await useAuthStore.getState().hydrate()
    })

    await waitFor(() => {
      expect(useAuthStore.getState().token).toBeNull()
      expect(useAuthStore.getState().isAuthenticated).toBe(false)
      expect(localStorage.getItem('auth_token')).toBeNull()
    })
  })
})
