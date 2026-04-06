import { useMemo, useState } from 'react'
import {
  AppstoreOutlined,
  BgColorsOutlined,
  CreditCardOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  InfoCircleOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
  MoonOutlined,
  ReconciliationOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SettingOutlined,
  ShoppingOutlined,
  ShoppingCartOutlined,
  SunOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Button, Input, Layout, Menu, Space, Typography, theme as antdTheme } from 'antd'
import type { MenuProps } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useThemeStore } from '../stores/themeStore'

const { Header, Content, Sider } = Layout

const SIDEBAR_WIDTH = 240
const SIDEBAR_COLLAPSED_WIDTH = 80

type AppMenuItem = NonNullable<MenuProps['items']>[number] & {
  key: string
  label: string
}

const APP_MENU_ITEMS: AppMenuItem[] = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/accounts', icon: <TeamOutlined />, label: '账号管理' },
  { key: '/items', icon: <ShoppingOutlined />, label: '商品管理' },
  { key: '/item-replies', icon: <MessageOutlined />, label: '商品回复' },
  { key: '/orders', icon: <ReconciliationOutlined />, label: '订单' },
  { key: '/auto-reply', icon: <MessageOutlined />, label: '自动回复' },
  { key: '/cards', icon: <CreditCardOutlined />, label: '卡券' },
  { key: '/delivery', icon: <ShoppingCartOutlined />, label: '自动发货' },
  { key: '/logs', icon: <AppstoreOutlined />, label: '日志' },
  { key: '/risk-logs', icon: <SafetyCertificateOutlined />, label: '风控日志' },
  { key: '/online-im', icon: <MessageOutlined />, label: '在线客服' },
  { key: '/item-search', icon: <SearchOutlined />, label: '商品搜索' },
  { key: '/system-settings', icon: <SettingOutlined />, label: '系统设置' },
  { key: '/data-management', icon: <DatabaseOutlined />, label: '数据管理' },
  { key: '/about', icon: <InfoCircleOutlined />, label: '关于' },
]

function getSelectedMenuKey(pathname: string) {
  if (pathname === '/') {
    return '/dashboard'
  }

  const matchedItem = APP_MENU_ITEMS.find((item) => {
    return pathname === item.key || pathname.startsWith(`${item.key}/`)
  })

  return matchedItem?.key ?? '/dashboard'
}

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = antdTheme.useToken()
  const [collapsed, setCollapsed] = useState(false)
  const [mobile, setMobile] = useState(false)

  const darkMode = useThemeStore((state) => state.darkMode)
  const themeColor = useThemeStore((state) => state.themeColor)
  const toggleDark = useThemeStore((state) => state.toggleDark)
  const setThemeColor = useThemeStore((state) => state.setThemeColor)

  const selectedKey = useMemo(() => getSelectedMenuKey(location.pathname), [location.pathname])
  const currentPageLabel = useMemo(() => {
    const currentItem = APP_MENU_ITEMS.find((item) => item?.key === selectedKey)
    return currentItem?.label ?? '闲鱼管理系统'
  }, [selectedKey])

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        breakpoint="lg"
        collapsed={collapsed}
        collapsedWidth={mobile ? 0 : SIDEBAR_COLLAPSED_WIDTH}
        onBreakpoint={(broken) => {
          setMobile(broken)
          setCollapsed(broken)
        }}
        onCollapse={(nextCollapsed) => setCollapsed(nextCollapsed)}
        trigger={null}
        width={SIDEBAR_WIDTH}
        style={{
          background: token.colorBgContainer,
          borderInlineEnd: `${token.lineWidth}px solid ${token.colorBorderSecondary}`,
        }}
      >
        <div
          style={{
            alignItems: 'center',
            borderBlockEnd: `${token.lineWidth}px solid ${token.colorBorderSecondary}`,
            display: 'flex',
            gap: token.marginXS,
            justifyContent: collapsed ? 'center' : 'space-between',
            padding: token.padding,
          }}
        >
          {!collapsed ? (
            <Typography.Title level={5} style={{ margin: 0 }}>
              闲鱼管理系统
            </Typography.Title>
          ) : null}
          <Button
            aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed((value) => !value)}
            type="text"
          />
        </div>

        <Menu
          items={APP_MENU_ITEMS}
          mode="inline"
          onClick={({ key }) => {
            navigate(String(key))
            if (mobile) {
              setCollapsed(true)
            }
          }}
          selectedKeys={[selectedKey]}
          style={{
            borderInlineEnd: 0,
            paddingBlock: token.paddingXS,
          }}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            alignItems: 'center',
            background: token.colorBgContainer,
            borderBlockEnd: `${token.lineWidth}px solid ${token.colorBorderSecondary}`,
            display: 'flex',
            gap: token.margin,
            height: 'auto',
            justifyContent: 'space-between',
            padding: `${token.paddingSM}px ${token.paddingLG}px`,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <Typography.Text type="secondary">当前页面</Typography.Text>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {currentPageLabel}
            </Typography.Title>
          </div>

          <Space size={token.marginSM} wrap>
            <Button
              aria-label="切换深色模式"
              icon={darkMode ? <SunOutlined /> : <MoonOutlined />}
              onClick={toggleDark}
              type="default"
            >
              {darkMode ? '浅色模式' : '深色模式'}
            </Button>

            <Space size={token.marginXS}>
              <BgColorsOutlined aria-hidden="true" />
              <Typography.Text>主题色</Typography.Text>
              <Input
                aria-label="选择主题色"
                onChange={(event) => setThemeColor(event.target.value)}
                style={{ width: 56 }}
                type="color"
                value={themeColor}
              />
            </Space>
          </Space>
        </Header>

        <Content
          style={{
            background: token.colorBgLayout,
            padding: token.paddingLG,
          }}
        >
          <div
            style={{
              background: token.colorBgContainer,
              borderRadius: token.borderRadiusLG,
              minHeight: '100%',
              padding: token.paddingLG,
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}
