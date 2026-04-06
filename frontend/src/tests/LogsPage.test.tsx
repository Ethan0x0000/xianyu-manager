import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { apiClient } from '../api/client'
import DataManagementPage from '../pages/DataManagementPage'
import LogsPage from '../pages/LogsPage'
import RiskLogsPage from '../pages/RiskLogsPage'
import ThemeProvider from '../providers/ThemeProvider'

vi.mock('../api/client', () => ({
  apiClient: {
    delete: vi.fn(),
    get: vi.fn(),
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

describe('LogsPage family', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders the log viewer with fetched data', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/logs') {
        return Promise.resolve({
          data: {
            logs: ['[INFO] 系统启动', '[WARNING] 队列堆积'],
          },
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<LogsPage />)

    await waitFor(() => {
      expect(screen.getByText('[INFO] 系统启动')).toBeInTheDocument()
      expect(screen.getByText('[WARNING] 队列堆积')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /刷.*新/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '导出日志' })).toBeInTheDocument()
    })
  })

  it('updates the logs request when the level filter changes', async () => {
    const user = userEvent.setup()

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/logs') {
        return Promise.resolve({ data: { logs: ['[INFO] 系统启动'] } } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<LogsPage />)

    await screen.findByText('[INFO] 系统启动')

    await user.click(screen.getByRole('combobox'))
    await user.click(await screen.findByText('ERROR'))

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/logs', {
        params: {
          level: 'ERROR',
          limit: 100,
        },
      })
    })
  })

  it('refetches logs when the refresh button is clicked', async () => {
    const user = userEvent.setup()
    let refreshCount = 0

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/logs') {
        refreshCount += 1

        return Promise.resolve({
          data: {
            logs: refreshCount === 1 ? ['[INFO] 初始日志'] : ['[INFO] 刷新后的日志'],
          },
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<LogsPage />)

    await screen.findByText('[INFO] 初始日志')

    await user.click(screen.getByRole('button', { name: /刷.*新/ }))

    await waitFor(() => {
      expect(screen.getByText('[INFO] 刷新后的日志')).toBeInTheDocument()
      expect(apiClient.get).toHaveBeenCalledTimes(2)
    })
  })

  it('renders the risk log table', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/risk-logs') {
        return Promise.resolve({
          data: {
            logs: [
              {
                id: 1,
                account_id: 'acc-1',
                created_at: '2026-04-06 10:00:00',
                details: '同一 IP 触发限制',
                event_type: 'rate_limit',
              },
            ],
            page: 1,
            page_size: 20,
            total: 1,
          },
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<RiskLogsPage />)

    await waitFor(() => {
      expect(screen.getByText('acc-1')).toBeInTheDocument()
      expect(screen.getByText('rate_limit')).toBeInTheDocument()
      expect(screen.getByText('同一 IP 触发限制')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '清空全部' })).toBeInTheDocument()
    })
  })

  it('loads table data after selecting a data table', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/data/tables') {
        return Promise.resolve({ data: { tables: ['orders', 'risk_logs'] } } as never)
      }

      if (url === '/data/table/orders') {
        return Promise.resolve({
          data: {
            columns: ['id', 'order_id', 'amount'],
            page: 1,
            page_size: 20,
            rows: [{ amount: '99.00', id: 1, order_id: 'order-1' }],
            total: 1,
          },
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<DataManagementPage />)

    const tableSelect = await screen.findByRole('combobox')
    fireEvent.mouseDown(tableSelect)
    fireEvent.click((await screen.findAllByText('orders'))[1])

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/data/table/orders', {
        params: {
          page: 1,
          page_size: 20,
        },
      })
      expect(screen.getByText('order-1')).toBeInTheDocument()
      expect(screen.getByText('99.00')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '清空数据表' })).toBeInTheDocument()
    })
  })
})
