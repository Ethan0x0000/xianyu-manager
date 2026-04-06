import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { apiClient } from '../api/client'
import ThemeProvider from '../providers/ThemeProvider'
import ItemRepliesPage from '../pages/ItemRepliesPage'
import ItemsPage from '../pages/ItemsPage'

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

const itemsResponse = {
  items: [
    {
      id: 1,
      item_id: 'item-1',
      title: '蓝牙耳机',
      price: 88.5,
      status: 'online',
      account_id: 'acc-1',
      updated_at: '2026-04-06 11:00:00',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

describe('ItemsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders the items table with fetched data', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/items') {
        return Promise.resolve({ data: itemsResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<ItemsPage />)

    await waitFor(() => {
      expect(screen.getByText('item-1')).toBeInTheDocument()
      expect(screen.getByText('蓝牙耳机')).toBeInTheDocument()
      expect(screen.getByText('88.5')).toBeInTheDocument()
      expect(screen.getByText('online')).toBeInTheDocument()
      expect(screen.getByText('acc-1')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '编辑' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '删除' })).toBeInTheDocument()
    })
  })

  it('searches items with the q param', async () => {
    const user = userEvent.setup()

    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === '/accounts') {
        return Promise.resolve({ data: accountsResponse } as never)
      }

      if (url === '/items') {
        return Promise.resolve({ data: itemsResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<ItemsPage />)

    await screen.findByText('蓝牙耳机')

    await user.type(screen.getByPlaceholderText('搜索商品标题或商品ID'), '耳机')
    await user.click(screen.getByRole('button', { name: /搜\s*索/ }))

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/items', {
        params: {
          account_id: '',
          page: 1,
          page_size: 20,
          q: '耳机',
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

      if (url === '/items') {
        return Promise.resolve({ data: itemsResponse } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<ItemsPage />)

    const batchDeleteButton = await screen.findByRole('button', { name: '批量删除' })
    expect(batchDeleteButton).toBeDisabled()

    await screen.findByText('蓝牙耳机')

    const row = screen.getByText('蓝牙耳机').closest('tr')
    expect(row).not.toBeNull()

    await user.click(within(row as HTMLElement).getByRole('checkbox'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '批量删除' })).toBeEnabled()
    })
  })
})

describe('ItemRepliesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders the item replies table after selecting an item id', async () => {
    const user = userEvent.setup()

    vi.mocked(apiClient.get).mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
      if (url === '/replies/item-replies') {
        expect(config).toEqual({ params: { item_id: 'item-1' } })

        return Promise.resolve({
          data: [
            {
              id: 7,
              item_id: 'item-1',
              reply_content: '您好，现货可拍。',
              enabled: true,
              created_at: '2026-04-06 12:00:00',
            },
          ],
        } as never)
      }

      return Promise.reject(new Error(`Unexpected GET ${url}`))
    })

    renderWithProviders(<ItemRepliesPage />)

    await user.type(screen.getByPlaceholderText('请输入商品ID'), 'item-1')
    await user.click(screen.getByRole('button', { name: '查询回复' }))

    await waitFor(() => {
      expect(screen.getByText('item-1')).toBeInTheDocument()
      expect(screen.getByText('您好，现货可拍。')).toBeInTheDocument()
      expect(screen.getByText('启用')).toBeInTheDocument()
    })
  })
})
