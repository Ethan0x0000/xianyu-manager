import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import LoginPage from '../pages/LoginPage'
import * as authApi from '../api/auth'
import * as client from '../api/client'

vi.mock('../api/auth', () => ({
  loginApi: vi.fn(),
  verifyApi: vi.fn(),
  logoutApi: vi.fn(),
}))

vi.mock('../api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useAuthStore.setState({
      isAuthenticated: false,
      isInitializing: false,
    })
    // Mock login-info-status endpoint to return disabled by default
    vi.mocked(client.apiClient.get).mockResolvedValue({
      data: { enabled: false },
    } as any)
  })

  it('renders login form with username and password fields', async () => {
    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
      >
        <LoginPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('管理员登录')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('admin')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('请输入密码')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /登.*录/ })).toBeInTheDocument()
    })
  })

  it('shows default credentials hint when login-info-status.enabled is true', async () => {
    vi.mocked(client.apiClient.get).mockResolvedValue({
      data: { enabled: true },
    } as any)

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
      >
        <LoginPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('默认凭证已启用')).toBeInTheDocument()
      expect(screen.getByText(/默认用户名: admin/)).toBeInTheDocument()
      expect(screen.getByText(/默认密码: admin123/)).toBeInTheDocument()
    })
  })

  it('does not show default credentials hint when login-info-status.enabled is false', async () => {
    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
      >
        <LoginPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.queryByText('默认凭证已启用')).not.toBeInTheDocument()
    })
  })

  it('submits form with valid credentials and navigates to dashboard', async () => {
    const user = userEvent.setup()
    vi.mocked(authApi.loginApi).mockResolvedValue({ token: '' })
    vi.mocked(authApi.verifyApi).mockResolvedValue({ is_admin: true, username: 'admin' })

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
        initialEntries={['/login']}
      >
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<div>Dashboard</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByPlaceholderText('admin')).toBeInTheDocument()
    })

    const usernameInput = screen.getByPlaceholderText('admin')
    const passwordInput = screen.getByPlaceholderText('请输入密码')
    const submitButton = screen.getByRole('button', { name: /登.*录/ })

    await user.type(usernameInput, 'admin')
    await user.type(passwordInput, 'admin123')
    await user.click(submitButton)

    await waitFor(() => {
      expect(authApi.loginApi).toHaveBeenCalledWith({
        username: 'admin',
        password: 'admin123',
      })
    })

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })
  })

  it('shows error alert on login failure', async () => {
    const user = userEvent.setup()
    vi.mocked(authApi.loginApi).mockRejectedValue({
      response: {
        status: 401,
        data: {
          detail: 'Invalid credentials',
        },
      },
    })

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
      >
        <LoginPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByPlaceholderText('admin')).toBeInTheDocument()
    })

    const usernameInput = screen.getByPlaceholderText('admin')
    const passwordInput = screen.getByPlaceholderText('请输入密码')
    const submitButton = screen.getByRole('button', { name: /登.*录/ })

    await user.type(usernameInput, 'wronguser')
    await user.type(passwordInput, 'wrongpass')
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
    })
  })

  it('disables form inputs while loading', async () => {
    const user = userEvent.setup()
    let resolveLogin: (value: any) => void
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve
    })
    vi.mocked(authApi.loginApi).mockReturnValue(loginPromise as any)

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
      >
        <LoginPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByPlaceholderText('admin')).toBeInTheDocument()
    })

    const usernameInput = screen.getByPlaceholderText('admin') as HTMLInputElement
    const passwordInput = screen.getByPlaceholderText('请输入密码') as HTMLInputElement
    const submitButton = screen.getByRole('button', { name: /登.*录/ })

    await user.type(usernameInput, 'admin')
    await user.type(passwordInput, 'admin123')
    await user.click(submitButton)

    await waitFor(() => {
      expect(usernameInput.disabled).toBe(true)
      expect(passwordInput.disabled).toBe(true)
    })

    await act(async () => {
      resolveLogin!({ token: '' })
    })

    await waitFor(() => {
      expect(usernameInput.disabled).toBe(false)
      expect(passwordInput.disabled).toBe(false)
    })
  })

  it('redirects to dashboard if already authenticated', async () => {
    useAuthStore.setState({
      isAuthenticated: true,
      isInitializing: false,
    })

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
        initialEntries={['/login']}
      >
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<div>Dashboard</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })
  })

  it('closes error alert when close button is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(authApi.loginApi).mockRejectedValue({
      response: {
        status: 401,
        data: {
          detail: 'Invalid credentials',
        },
      },
    })

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
      >
        <LoginPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByPlaceholderText('admin')).toBeInTheDocument()
    })

    const usernameInput = screen.getByPlaceholderText('admin')
    const passwordInput = screen.getByPlaceholderText('请输入密码')
    const submitButton = screen.getByRole('button', { name: /登.*录/ })

    await user.type(usernameInput, 'wronguser')
    await user.type(passwordInput, 'wrongpass')
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
    })

    const closeButton = screen.getByRole('button', { name: /close/i })
    await user.click(closeButton)

    await waitFor(() => {
      expect(screen.queryByText('Invalid credentials')).not.toBeInTheDocument()
    })
  })

  it('handles generic error message when no detail provided', async () => {
    const user = userEvent.setup()
    vi.mocked(authApi.loginApi).mockRejectedValue(new Error('Network error'))

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
      >
        <LoginPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByPlaceholderText('admin')).toBeInTheDocument()
    })

    const usernameInput = screen.getByPlaceholderText('admin')
    const passwordInput = screen.getByPlaceholderText('请输入密码')
    const submitButton = screen.getByRole('button', { name: /登.*录/ })

    await user.type(usernameInput, 'admin')
    await user.type(passwordInput, 'admin123')
    await user.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText('登录失败，请重试')).toBeInTheDocument()
    })
  })

  it('shows loading spinner while fetching login info', async () => {
    let resolveLoginInfo: (value: any) => void
    const loginInfoPromise = new Promise((resolve) => {
      resolveLoginInfo = resolve
    })
    vi.mocked(client.apiClient.get).mockReturnValue(loginInfoPromise as any)

    render(
      <MemoryRouter
        future={{
          v7_relativeSplatPath: true,
          v7_startTransition: true,
        }}
      >
        <LoginPage />
      </MemoryRouter>,
    )

    // Should show spinner while loading - check for aria-busy attribute
    await waitFor(() => {
      const spinElement = document.querySelector('[aria-busy="true"]')
      expect(spinElement).toBeInTheDocument()
    })

    await act(async () => {
      resolveLoginInfo!({ data: { enabled: false } })
    })

    await waitFor(() => {
      expect(screen.getByText('管理员登录')).toBeInTheDocument()
    })
  })
})
