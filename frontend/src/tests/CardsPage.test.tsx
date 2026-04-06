import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { apiClient } from '../api/client'
import CardsPage from '../pages/CardsPage'
import DeliveryPage from '../pages/DeliveryPage'
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

const accountsResponse = [{ account_id: 'acc-1', username: '店铺一' }]

const cardsResponse = [
  {
    id: 1,
    name: '测试文字卡',
    content_type: 'text',
    content: '卡密-001',
    account_id: 'acc-1',
    created_at: '2026-04-06 10:00:00',
  },
]

const deliveryRulesResponse = {
  rules: [
    {
      id: 11,
      item_id: 'item-1',
      priority: 10,
      enabled: true,
      account_id: 'acc-1',
      card_id: 1,
      card_name: '测试文字卡',
      content_type: 'text',
    },
  ],
}

const deliveryLogsResponse = [
  {
    id: 21,
    order_id: 'order-1',
    card_id: 1,
    status: 'success',
    created_at: '2026-04-06 11:00:00',
  },
]

describe('CardsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders the cards table with fetched data', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/cards') {
        return Promise.resolve({ data: cardsResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<CardsPage />)

    await waitFor(() => {
      expect(screen.getByText('测试文字卡')).toBeInTheDocument()
      expect(screen.getByText('text')).toBeInTheDocument()
      expect(screen.getByText('acc-1')).toBeInTheDocument()
    })
  })

  it(
    'switches card type fields in the add card modal',
    async () => {
    const user = userEvent.setup()

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/cards') {
        return Promise.resolve({ data: cardsResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<CardsPage />)

    await screen.findByText('测试文字卡')
    await user.click(screen.getByRole('button', { name: '新增卡券' }))

    expect(screen.getByLabelText('文本内容')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'API卡券' }))
    expect(await screen.findByLabelText('API URL')).toBeInTheDocument()
    expect(screen.getByLabelText('API Key')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: '图片卡券' }))
    expect(await screen.findByRole('button', { name: '上传图片' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: '易凡配置' }))
    expect(await screen.findByLabelText('回调地址')).toBeInTheDocument()
    expect(screen.getByLabelText('商户号')).toBeInTheDocument()
    expect(screen.getByLabelText('应用密钥')).toBeInTheDocument()
    },
    15000,
  )
})

describe('DeliveryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders the delivery rules and recent logs', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/delivery/rules') {
        return Promise.resolve({ data: deliveryRulesResponse } as never)
      }

      if (url === '/delivery/logs/recent') {
        return Promise.resolve({ data: deliveryLogsResponse } as never)
      }

      if (url === '/cards') {
        return Promise.resolve({ data: cardsResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<DeliveryPage />)

    await waitFor(() => {
      expect(screen.getByText('item-1')).toBeInTheDocument()
      expect(screen.getByText('测试文字卡')).toBeInTheDocument()
      expect(screen.getByText('10')).toBeInTheDocument()
      expect(screen.getByText('order-1')).toBeInTheDocument()
      expect(screen.getByText('success')).toBeInTheDocument()
    })
  })

  it('opens the add rule modal', async () => {
    const user = userEvent.setup()

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/delivery/rules') {
        return Promise.resolve({ data: deliveryRulesResponse } as never)
      }

      if (url === '/delivery/logs/recent') {
        return Promise.resolve({ data: deliveryLogsResponse } as never)
      }

      if (url === '/cards') {
        return Promise.resolve({ data: cardsResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<DeliveryPage />)

    await screen.findByText('item-1')
    await user.click(screen.getByRole('button', { name: '新增规则' }))

    expect(await screen.findByRole('dialog', { name: '新增规则' })).toBeInTheDocument()
    expect(screen.getByLabelText('商品ID')).toBeInTheDocument()
    expect(screen.getByLabelText('卡券')).toBeInTheDocument()
    expect(screen.getByLabelText('优先级')).toBeInTheDocument()
  })
})
