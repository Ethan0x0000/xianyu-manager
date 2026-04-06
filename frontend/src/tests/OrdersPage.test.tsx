import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { apiClient } from '../api/client'
import OrdersPage from '../pages/OrdersPage'
import ThemeProvider from '../providers/ThemeProvider'

vi.mock('../api/client', () => ({
  apiClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
  },
}))

type MockEventSourceInstance = {
  addEventListener: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
  onerror: ((event: Event) => void) | null
  onmessage: ((event: MessageEvent<string>) => void) | null
}

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

const accountsResponse = [{ account_id: 'acc-1', username: '店铺一' }]

const ordersResponse = {
  orders: [
    {
      id: 1,
      order_id: 'order-1',
      item_id: 'item-1',
      buyer_id: 'buyer-1',
      status: 'pending',
      amount: '10.00',
      account_id: 'acc-1',
      created_at: '2026-04-06 10:00:00',
      updated_at: '2026-04-06 10:05:00',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

describe('OrdersPage', () => {
  const originalEventSource = globalThis.EventSource
  let eventSourceInstance: MockEventSourceInstance
  let eventSourceMock: Mock<[string], MockEventSourceInstance>

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()

    eventSourceInstance = {
      addEventListener: vi.fn(),
      close: vi.fn(),
      onerror: null,
      onmessage: null,
    }

    eventSourceMock = vi.fn((_url: string) => eventSourceInstance)
    Object.defineProperty(globalThis, 'EventSource', {
      configurable: true,
      value: eventSourceMock,
      writable: true,
    })
  })

  afterEach(() => {
    if (originalEventSource) {
      Object.defineProperty(globalThis, 'EventSource', {
        configurable: true,
        value: originalEventSource,
        writable: true,
      })
      return
    }

    Reflect.deleteProperty(globalThis, 'EventSource')
  })

  it('renders the orders table with fetched data', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/orders') {
        return Promise.resolve({ data: ordersResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<OrdersPage />)

    await waitFor(() => {
      expect(screen.getByText('order-1')).toBeInTheDocument()
      expect(screen.getByText('item-1')).toBeInTheDocument()
      expect(screen.getByText('buyer-1')).toBeInTheDocument()
      expect(screen.getByText('pending')).toBeInTheDocument()
      expect(screen.getByText('10.00')).toBeInTheDocument()
      expect(screen.getByText('acc-1')).toBeInTheDocument()
      expect(screen.getByText('2026-04-06 10:00:00')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '刷新' })).toBeInTheDocument()
    })
  })

  it('updates the orders request when the status filter changes', async () => {
    const user = userEvent.setup()

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/orders') {
        return Promise.resolve({ data: ordersResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<OrdersPage />)

    await screen.findByText('order-1')

    const [, statusFilter] = screen.getAllByRole('combobox')

    await user.click(statusFilter)
    await user.click(await screen.findByText('paid'))

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/orders', {
        params: {
          account_id: '',
          page: 1,
          page_size: 20,
          status: 'paid',
        },
      })
    })
  })

  it('enables batch delete after selecting a row', async () => {
    const user = userEvent.setup()

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/orders') {
        return Promise.resolve({ data: ordersResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<OrdersPage />)

    const batchDeleteButton = await screen.findByRole('button', { name: '批量删除' })
    expect(batchDeleteButton).toBeDisabled()

    await screen.findByText('order-1')

    const row = screen.getByText('order-1').closest('tr')
    expect(row).not.toBeNull()

    await user.click(within(row as HTMLElement).getByRole('checkbox'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '批量删除' })).toBeEnabled()
    })
  })

  it('creates an SSE subscription and refetches orders when a message arrives', async () => {
    let ordersCallCount = 0

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/orders') {
        ordersCallCount += 1

        return Promise.resolve({
          data:
            ordersCallCount === 1
              ? ordersResponse
              : {
                  ...ordersResponse,
                  orders: [
                    {
                      ...ordersResponse.orders[0],
                      amount: '11.00',
                      status: 'paid',
                    },
                  ],
                },
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<OrdersPage />)

    await screen.findByText('10.00')

    expect(eventSourceMock).toHaveBeenCalledWith('/api/orders/stream')

    act(() => {
      eventSourceInstance.onmessage?.(new MessageEvent('message', { data: '{"order_id":"order-1"}' }))
    })

    await waitFor(() => {
      expect(screen.getByText('11.00')).toBeInTheDocument()
      expect(screen.getByText('paid')).toBeInTheDocument()
    })
  })

  it('closes the SSE stream on unmount', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/orders') {
        return Promise.resolve({ data: ordersResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    const { unmount } = renderWithProviders(<OrdersPage />)

    await screen.findByText('order-1')

    unmount()

    expect(eventSourceInstance.close).toHaveBeenCalledTimes(1)
  })
})
