import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

vi.mock('./api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  AUTH_TOKEN_STORAGE_KEY: 'auth_token',
  getStoredAuthToken: vi.fn(),
}))

import { apiClient } from './api/client'

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    window.history.replaceState({}, '', '/')
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { enabled: false },
    } as never)
  })

  it('renders the login route when the user is not authenticated', async () => {
    render(<App />)

    expect(await screen.findByRole('heading', { name: '管理员登录' })).toBeInTheDocument()
    expect(screen.getByLabelText('用户名')).toBeInTheDocument()
    expect(screen.getByLabelText('密码')).toBeInTheDocument()
  })
})
