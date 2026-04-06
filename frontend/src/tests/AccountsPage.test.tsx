import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import AccountsPage from '../pages/AccountsPage'
import { apiClient } from '../api/client'
import ThemeProvider from '../providers/ThemeProvider'

vi.mock('../api/client', () => ({
  apiClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
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

describe('AccountsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders the account table with merged account details and actions', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({
          data: [
            {
              account_id: 'seller-1',
              username: '店铺A',
              notes: '主账号',
              enabled: true,
              show_browser: false,
              has_cookie: true,
              created_at: '2026-04-06 10:00:00',
            },
          ],
        } as never)
      }

      if (url === '/cookies/details') {
        return Promise.resolve({
          data: [
            {
              id: 'seller-1',
              value: 'cookie=value',
              username: '店铺A',
              enabled: true,
              show_browser: false,
              has_cookie: true,
              cookie_status: 'available',
              has_password: true,
              remark: '主账号',
              pause_duration: 15,
              created_at: '2026-04-06 10:00:00',
            },
          ],
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<AccountsPage />)

    await waitFor(() => {
      expect(screen.getByText('seller-1')).toBeInTheDocument()
      expect(screen.getByText('店铺A')).toBeInTheDocument()
      expect(screen.getByText('主账号')).toBeInTheDocument()
      expect(screen.getByText('15 分钟')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /禁.*用/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /刷.*新.*Cookie/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /备.*注/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /删.*除/ })).toBeInTheDocument()
    })
  })

  it('opens and closes the add-account modal with all login tabs', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: [] } as never)
      }

      if (url === '/cookies/details') {
        return Promise.resolve({ data: [] } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<AccountsPage />)

    fireEvent.click(await screen.findByRole('button', { name: '添加账号' }))

    expect(screen.getByRole('dialog', { name: '添加账号' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'QR登录' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '密码登录' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '手动Cookie' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /取.*消/ }))

    await waitFor(
      () => {
        expect(screen.queryByRole('dialog', { name: '添加账号' })).not.toBeInTheDocument()
      },
      { timeout: 15000 },
    )
  })

  it('submits the manual cookie flow and refreshes the table', async () => {
    let manualAdded = false

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({
          data: manualAdded
            ? [
                {
                    account_id: 'seller-2',
                    username: '',
                    notes: '',
                    enabled: true,
                    show_browser: false,
                    has_cookie: true,
                    created_at: '2026-04-06 12:00:00',
                  },
              ]
            : [],
        } as never)
      }

      if (url === '/cookies/details') {
        return Promise.resolve({
          data: manualAdded
            ? [
                {
                    id: 'seller-2',
                    value: 'foo=bar; a=1',
                    username: '',
                    enabled: true,
                    show_browser: false,
                    has_cookie: true,
                    cookie_status: 'available',
                    has_password: false,
                    remark: '',
                    pause_duration: 10,
                    created_at: '2026-04-06 12:00:00',
                  },
              ]
            : [],
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    vi.mocked(apiClient.post).mockImplementation((url: string, payload?: unknown) => {
      if (url === '/accounts') {
        manualAdded = true
        return Promise.resolve({ data: payload } as never)
      }

      return Promise.reject(new Error(`Unexpected POST ${url}`))
    })

    renderWithProviders(<AccountsPage />)

    fireEvent.click(await screen.findByRole('button', { name: '添加账号' }))
    fireEvent.click(screen.getByRole('tab', { name: '手动Cookie' }))

    const panel = screen.getByRole('tabpanel', { name: /手动Cookie/ })
    fireEvent.change(within(panel).getByPlaceholderText('请输入账号ID'), {
      target: { value: 'seller-2' },
    })
    fireEvent.change(within(panel).getByLabelText('Cookie'), {
      target: { value: 'foo=bar; a=1' },
    })
    fireEvent.click(within(panel).getByRole('button', { name: /保.*存.*Cookie/i }))

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/accounts', {
        account_id: 'seller-2',
        cookie_str: 'foo=bar; a=1',
        enabled: true,
        notes: '',
        password: '',
        show_browser: false,
        username: '',
      })
    })

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledTimes(4)
    })
  })
})
