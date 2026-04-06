import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import ThemeProvider from '../providers/ThemeProvider'
import AboutPage from '../pages/AboutPage'
import DashboardPage from '../pages/DashboardPage'
import { apiClient } from '../api/client'

vi.mock('../api/client', () => ({
  apiClient: {
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

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders KPI cards from the sales summary response', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({
        data: {
          today_amount: '88.90',
          today_orders: 3,
          total_amount: '666.00',
          total_orders: 18,
        },
      } as never)
      .mockResolvedValueOnce({
        data: [
          { date: '2026-04-01', amount: '20.00', count: 1 },
          { date: '2026-04-02', amount: '68.90', count: 2 },
        ],
      } as never)
      .mockResolvedValueOnce({
        data: {
          logs: [
            {
              id: 1,
              order_id: 'ORDER-1001',
              card_id: 'CARD-9',
              status: 'delivered',
              created_at: '2026-04-06 10:00:00',
            },
          ],
        },
      } as never)

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('今日订单')).toBeInTheDocument()
      expect(screen.getByText('总订单')).toBeInTheDocument()
      expect(screen.getByText('今日成交额')).toBeInTheDocument()
      expect(screen.getByText('累计成交额')).toBeInTheDocument()
      expect(screen.getByText('88.90')).toBeInTheDocument()
      expect(screen.getByText('666.00')).toBeInTheDocument()
    })
  })

  it('renders the sales trend section and recent delivery log table', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({
        data: {
          today_amount: '12.00',
          today_orders: 1,
          total_amount: '120.00',
          total_orders: 10,
        },
      } as never)
      .mockResolvedValueOnce({
        data: [
          { date: '2026-04-01', amount: '10.00', count: 1 },
          { date: '2026-04-02', amount: '30.00', count: 2 },
          { date: '2026-04-03', amount: '80.00', count: 4 },
        ],
      } as never)
      .mockResolvedValueOnce({
        data: {
          logs: [
            {
              id: 8,
              order_id: 'ORDER-2008',
              card_id: 'CARD-12',
              status: 'queued',
              created_at: '2026-04-06 09:30:00',
            },
          ],
        },
      } as never)

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('最近 7 天销售趋势')).toBeInTheDocument()
      expect(screen.getByText('最近发货日志')).toBeInTheDocument()
      expect(screen.getByText('ORDER-2008')).toBeInTheDocument()
      expect(screen.getByText('CARD-12')).toBeInTheDocument()
      expect(screen.getByText('2026-04-03')).toBeInTheDocument()
    })
  })
})

describe('AboutPage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders OSS-safe project information only', () => {
    const { container } = renderWithProviders(<AboutPage />)

    expect(screen.getByRole('heading', { name: '闲鱼管理系统' })).toBeInTheDocument()
    expect(screen.getByText('v0.1.0')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /github 仓库/i })).toHaveAttribute(
      'href',
      'https://github.com/Ethan0x0000/xianyu-manager',
    )
    expect(container).not.toHaveTextContent(/donate|捐|赞助|二维码|coffee|sponsor/i)
  })
})
