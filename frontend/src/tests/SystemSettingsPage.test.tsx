import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { apiClient } from '../api/client'
import SystemSettingsPage from '../pages/SystemSettingsPage'
import ThemeProvider from '../providers/ThemeProvider'
import { useAuthStore } from '../stores/authStore'
import { useThemeStore } from '../stores/themeStore'

vi.mock('../api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
}

function renderWithProviders(ui: ReactElement) {
  const queryClient = createTestQueryClient()

  return render(
    <MemoryRouter
      future={{
        v7_relativeSplatPath: true,
        v7_startTransition: true,
      }}
    >
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>{ui}</ThemeProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('SystemSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    useAuthStore.setState({
      isAuthenticated: true,
      isInitializing: false,
    })
    useThemeStore.setState({
      darkMode: false,
      themeColor: '#1890ff',
    })

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/settings') {
        return Promise.resolve({
          data: {
            settings: {
              theme_color: '#722ed1',
            },
          },
        } as never)
      }

      if (url === '/settings/login-info') {
        return Promise.resolve({
          data: {
            show_default_credentials: true,
            default_username: 'admin',
          },
        } as never)
      }

      if (url === '/settings/menu') {
        return Promise.resolve({
          data: {
            menu: [
              { key: '/dashboard', label: '仪表盘', visible: true, order: 0 },
              { key: '/orders', label: '订单', visible: false, order: 1 },
            ],
          },
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as never)
  })

  it('renders settings tabs and persists theme changes through the save action', async () => {
    renderWithProviders(<SystemSettingsPage />)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: '基本设置' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: '账号安全' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: '菜单管理' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: '系统工具' })).toBeInTheDocument()
      expect(screen.getByLabelText('主题色选择')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('主题色选择'), {
      target: { value: '#ff4d4f' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存主题' }))

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/settings/theme', { color: '#ff4d4f' })
      expect(useThemeStore.getState().themeColor).toBe('#ff4d4f')
    })
  })

  it(
    'shows required validation when the password form is submitted empty',
    async () => {
    renderWithProviders(<SystemSettingsPage />)

      fireEvent.click(await screen.findByRole('tab', { name: '账号安全' }))
      fireEvent.click(screen.getByRole('button', { name: '更新密码' }))

      expect(await screen.findByText('请输入新密码', {}, { timeout: 10000 })).toBeInTheDocument()
      expect(await screen.findByText('请再次确认新密码', {}, { timeout: 10000 })).toBeInTheDocument()
    },
    10000,
  )

  it('shows mismatch validation when password confirmation does not match', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SystemSettingsPage />)

    await user.click(await screen.findByRole('tab', { name: '账号安全' }))
    fireEvent.change(screen.getByPlaceholderText('请输入新密码'), {
      target: { value: 'new-password-123' },
    })
    fireEvent.change(screen.getByPlaceholderText('请再次输入新密码'), {
      target: { value: 'different-password' },
    })
    await user.click(screen.getByRole('button', { name: '更新密码' }))

    await waitFor(() => {
      expect(screen.getByText('两次输入的密码不一致')).toBeInTheDocument()
    })
  })

  it('renders fetched menu settings in the menu management tab', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SystemSettingsPage />)

    await user.click(await screen.findByRole('tab', { name: '菜单管理' }))

    await waitFor(() => {
      expect(screen.getByText('仪表盘')).toBeInTheDocument()
      expect(screen.getByText('订单')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '保存菜单设置' })).toBeInTheDocument()
      expect(screen.getByRole('switch', { name: '切换 /orders 可见状态' })).toHaveAttribute('aria-checked', 'false')
    })
  })

  it(
    'requires restart confirmation before posting the restart action',
    async () => {
    renderWithProviders(<SystemSettingsPage />)

      fireEvent.click(await screen.findByRole('tab', { name: '系统工具' }))
      fireEvent.click(screen.getByRole('button', { name: '重启系统' }))

      expect(await screen.findByText('系统将重启，当前连接将断开', {}, { timeout: 10000 })).toBeInTheDocument()

      expect(apiClient.post).not.toHaveBeenCalled()

      fireEvent.click(screen.getByRole('button', { name: '确认重启' }))

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/runtime/restart')
      })
    },
    10000,
  )

  it('requires restore confirmation before uploading a backup file', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<SystemSettingsPage />)

    await user.click(await screen.findByRole('tab', { name: '系统工具' }))

    const input = container.querySelector('input[type="file"]') as HTMLInputElement | null
    expect(input).not.toBeNull()

    fireEvent.change(input as HTMLInputElement, {
      target: {
        files: [new File(['backup'], 'backup.db', { type: 'application/octet-stream' })],
      },
    })

    await waitFor(() => {
      expect(screen.getByText('恢复将覆盖当前数据，不可撤销')).toBeInTheDocument()
    })

    expect(apiClient.post).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: '确认恢复' }))

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/backup/import',
        expect.any(FormData),
        expect.objectContaining({
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }),
      )
    })
  })
})
