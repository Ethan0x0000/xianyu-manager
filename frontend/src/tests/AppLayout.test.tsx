import { describe, it, expect, beforeEach } from 'vitest'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ThemeProvider from '../providers/ThemeProvider'
import AppLayout from '../layouts/AppLayout'
import { useThemeStore } from '../stores/themeStore'

const MENU_LABELS = [
  '仪表盘',
  '账号管理',
  '商品管理',
  '商品回复',
  '订单',
  '自动回复',
  '卡券',
  '自动发货',
  '日志',
  '风控日志',
  '在线客服',
  '商品搜索',
  '系统设置',
  '数据管理',
  '关于',
]

function ThemeProbe() {
  const themeColor = useThemeStore((state) => state.themeColor)

  return <span data-testid="theme-color-value">{themeColor}</span>
}

function renderAppLayout(initialPath = '/dashboard') {
  return render(
    <MemoryRouter
      future={{
        v7_relativeSplatPath: true,
        v7_startTransition: true,
      }}
      initialEntries={[initialPath]}
    >
      <ThemeProvider>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<div>首页内容</div>} />
            <Route path="dashboard" element={<div>仪表盘内容</div>} />
            <Route path="orders" element={<div>订单内容</div>} />
            <Route path="about" element={<div>关于内容</div>} />
          </Route>
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('AppLayout', () => {
  beforeEach(() => {
    localStorage.clear()
    useThemeStore.setState({
      darkMode: false,
      themeColor: '#1890ff',
    })
  })

  it('renders all 15 sidebar menu items and highlights the current route', async () => {
    const { container } = renderAppLayout('/orders')
    const menu = container.querySelector('[role="menu"]')

    expect(menu).not.toBeNull()

    for (const label of MENU_LABELS) {
      await waitFor(() => {
        expect(within(menu as HTMLElement).getByText(label)).toBeInTheDocument()
      })
    }

    await waitFor(() => {
      const selectedItem = container.querySelector('.ant-menu-item-selected')
      expect(selectedItem).toHaveTextContent('订单')
    })
  })

  it('persists dark mode changes to localStorage through the toggle button', async () => {
    const user = userEvent.setup()

    renderAppLayout('/dashboard')

    await act(async () => {
      await user.click(screen.getByRole('button', { name: '切换深色模式' }))
    })

    await waitFor(() => {
      expect(localStorage.getItem('darkMode')).toBe('true')
      expect(useThemeStore.getState().darkMode).toBe(true)
    })
  })

  it('falls back to the default theme color when storage contains an invalid hex value', () => {
    localStorage.setItem('themeColor', 'invalid-color')

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    )

    expect(screen.getByTestId('theme-color-value')).toHaveTextContent('#1890ff')
    expect(localStorage.getItem('themeColor')).toBe('#1890ff')
  })
})
