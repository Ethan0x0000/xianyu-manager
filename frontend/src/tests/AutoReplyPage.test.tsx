import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { apiClient } from '../api/client'
import AutoReplyPage from '../pages/AutoReplyPage'
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

const keywordsResponse = [
  {
    id: 1,
    pattern: '你好',
    reply_content: '您好，请问有什么可以帮您？',
    item_id: null,
    is_regex: false,
    enabled: true,
    scope: 'general',
  },
]

const defaultRepliesResponse = [
  {
    id: 9,
    content: '稍后回复您',
    enabled: true,
    created_at: '2026-04-06 12:00:00',
  },
]

const aiSettingsResponse = {
  id: 3,
  provider_type: 'openai',
  api_key: '****',
  base_url: 'https://api.openai.com/v1',
  model_name: 'gpt-4o-mini',
  system_prompt: '请用礼貌且简洁的语气回复用户。',
  max_tokens: 512,
  enabled: true,
}

const accountsResponse = [{ account_id: 'acc-1', username: '店铺一' }]

function mockInitialRequests() {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/replies/keywords') {
      return Promise.resolve({ data: keywordsResponse } as never)
    }

    if (url === '/replies/default') {
      return Promise.resolve({ data: defaultRepliesResponse } as never)
    }

    if (url === '/ai/settings') {
      return Promise.resolve({ data: aiSettingsResponse } as never)
    }

    if (url === '/accounts') {
      return Promise.resolve({ data: accountsResponse } as never)
    }

    if (url === '/items') {
      return Promise.resolve({ data: { items: [], total: 0, page: 1, page_size: 20 } } as never)
    }

    return Promise.reject(new Error(`Unexpected GET ${url}`))
  })
}

describe('AutoReplyPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    mockInitialRequests()
  })

  it('renders the keyword list on the keywords tab', async () => {
    renderWithProviders(<AutoReplyPage />)

    await waitFor(() => {
      expect(screen.getByText('你好')).toBeInTheDocument()
      expect(screen.getByText('您好，请问有什么可以帮您？')).toBeInTheDocument()
      expect(screen.getByText('general')).toBeInTheDocument()
      expect(screen.getByText('1')).toBeInTheDocument()
    })
  })

  it(
    'validates required fields when adding a keyword',
    async () => {
      const user = userEvent.setup()

      renderWithProviders(<AutoReplyPage />)

      await user.click(screen.getByRole('button', { name: '新增关键词' }))
      const dialog = screen.getByRole('dialog', { name: '新增关键词' })
      await user.click(within(dialog).getByRole('button', { name: /新\s*增/ }))

      await waitFor(() => {
        expect(screen.getByText('请输入关键词')).toBeInTheDocument()
        expect(screen.getByText('请输入回复内容')).toBeInTheDocument()
      })
    },
    15000,
  )

  it('renders the AI settings form fields', async () => {
    const user = userEvent.setup()

    renderWithProviders(<AutoReplyPage />)

    await user.click(screen.getByRole('tab', { name: 'AI设置' }))

    await waitFor(() => {
      expect(screen.getByLabelText('服务商类型')).toHaveValue('openai')
      expect(screen.getByLabelText('基础地址')).toHaveValue('https://api.openai.com/v1')
      expect(screen.getByLabelText('模型名称')).toHaveValue('gpt-4o-mini')
      expect(screen.getByLabelText('API Key')).toHaveValue('****')
      expect(screen.getByLabelText('系统提示词')).toHaveValue('请用礼貌且简洁的语气回复用户。')
      expect(screen.getByLabelText('最大 Tokens')).toHaveValue('512')
    })
  })

  it('triggers the hidden file input from the import button', async () => {
    const user = userEvent.setup()
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click')

    renderWithProviders(<AutoReplyPage />)

    await screen.findByText('你好')
    await user.click(screen.getByRole('button', { name: '导入关键词' }))

    expect(clickSpy).toHaveBeenCalled()
  })
})
