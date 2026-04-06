import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { apiClient } from '../api/client'
import ItemSearchPage from '../pages/ItemSearchPage'
import OnlineImPage from '../pages/OnlineImPage'
import ThemeProvider from '../providers/ThemeProvider'

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

describe('OnlineImPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('loads account options and updates the account context after selection', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        accounts: [
          {
            id: 1,
            account_id: 'acc-1',
            username: '客服一号',
            enabled: true,
          },
          {
            id: 2,
            account_id: 'acc-2',
            username: '客服二号',
            enabled: true,
          },
        ],
      },
    } as never)

    renderWithProviders(<OnlineImPage />)

    const accountSelector = await screen.findByRole('combobox', { name: '选择客服账号' })
    await waitFor(() => {
      expect(accountSelector).not.toBeDisabled()
      expect(screen.getByText('客服一号 (acc-1)')).toBeInTheDocument()
      expect(screen.getByText('客服二号 (acc-2)')).toBeInTheDocument()
    })

    fireEvent.change(accountSelector, { target: { value: 'acc-2' } })

    await waitFor(() => {
      expect(screen.getAllByText('当前账号：客服二号（acc-2）')[0]).toBeInTheDocument()
      expect(screen.getByText('账号ID：acc-2')).toBeInTheDocument()
      expect(screen.getByText('用户名：客服二号')).toBeInTheDocument()
    })
  })

  it('renders the IM launcher for the selected account context', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        accounts: [
          {
            id: 1,
            account_id: 'acc-1',
            username: '客服一号',
            enabled: true,
          },
        ],
      },
    } as never)

    renderWithProviders(<OnlineImPage />)

    expect(await screen.findByRole('button', { name: '打开闲鱼IM' })).toBeInTheDocument()
  })
})

describe('ItemSearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('validates that the keyword is required before starting a search', async () => {
    renderWithProviders(<ItemSearchPage />)

    fireEvent.click(screen.getByRole('button', { name: '开始搜索' }))

    expect(await screen.findByText('请输入搜索关键词')).toBeInTheDocument()
    expect(apiClient.post).not.toHaveBeenCalled()
  })

  it('validates the page count range before starting a search', async () => {
    const user = userEvent.setup()

    renderWithProviders(<ItemSearchPage />)

    const pageCountInput = screen.getByRole('spinbutton', { name: '搜索页数' })
    await user.type(screen.getByRole('textbox', { name: '搜索关键词' }), '耳机')
    await user.clear(pageCountInput)
    await user.type(pageCountInput, '11')

    fireEvent.click(screen.getByRole('button', { name: '开始搜索' }))

    expect(await screen.findByText('搜索页数必须在 1-10 之间')).toBeInTheDocument()
    expect(apiClient.post).not.toHaveBeenCalled()
  })
})
