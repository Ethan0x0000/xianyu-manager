import { useEffect, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  BgColorsOutlined,
  CloudDownloadOutlined,
  CloudUploadOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Skeleton,
  Space,
  Switch,
  Tabs,
  Typography,
  Upload,
  message,
  theme as antdTheme,
} from 'antd'
import type { TabsProps, UploadProps } from 'antd'
import { apiClient } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { DEFAULT_THEME_COLOR, useThemeStore } from '../stores/themeStore'

type SettingsResponse = {
  settings?: Record<string, string | null>
}

type LoginInfoResponse = {
  show_default_credentials: boolean
  default_username?: string
}

type MenuSettingsItem = {
  key: string
  label: string
  visible: boolean
  order: number
}

type MenuSettingsResponse = {
  menu?: MenuSettingsItem[]
}

type ThemeSettingsResponse = {
  color?: string
}

type PasswordFormValues = {
  confirm: string
  new_password: string
}

const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string; message?: string }>
    return axiosError.response?.data?.detail ?? axiosError.response?.data?.message ?? axiosError.message ?? fallback
  }

  if (error instanceof Error) {
    return error.message
  }

  return fallback
}

function normalizeThemeColor(color: string | null | undefined) {
  return color && HEX_COLOR_PATTERN.test(color) ? color : DEFAULT_THEME_COLOR
}

function normalizeMenuItems(items: MenuSettingsItem[] | undefined) {
  return (items ?? [])
    .map((item, index) => ({
      key: String(item.key ?? ''),
      label: String(item.label ?? item.key ?? '').trim() || String(item.key ?? ''),
      order: Number.isFinite(item.order) ? item.order : index,
      visible: Boolean(item.visible),
    }))
    .filter((item) => item.key)
    .sort((left, right) => left.order - right.order)
    .map((item, index) => ({
      ...item,
      order: index,
    }))
}

function reorderMenuItems(items: MenuSettingsItem[], fromIndex: number, toIndex: number) {
  if (toIndex < 0 || toIndex >= items.length) {
    return items
  }

  const nextItems = [...items]
  const [movedItem] = nextItems.splice(fromIndex, 1)

  if (!movedItem) {
    return items
  }

  nextItems.splice(toIndex, 0, movedItem)

  return nextItems.map((item, index) => ({
    ...item,
    order: index,
  }))
}

export default function SystemSettingsPage() {
  const [messageApi, contextHolder] = message.useMessage()
  const [passwordForm] = Form.useForm<PasswordFormValues>()
  const { token } = antdTheme.useToken()

  const isAuthorized = useAuthStore((state) => state.isAuthenticated || Boolean(state.token))
  const currentThemeColor = useThemeStore((state) => state.themeColor)
  const persistThemeColor = useThemeStore((state) => state.setThemeColor)

  const [themeColor, setThemeColor] = useState(currentThemeColor)
  const [themeColorDirty, setThemeColorDirty] = useState(false)
  const [showDefaultCredentials, setShowDefaultCredentials] = useState(false)
  const [menuItems, setMenuItems] = useState<MenuSettingsItem[]>([])
  const [restoreModalOpen, setRestoreModalOpen] = useState(false)
  const [restoreFile, setRestoreFile] = useState<File | null>(null)

  const settingsQuery = useQuery({
    queryKey: ['system-settings', 'base'],
    queryFn: () => apiClient.get<SettingsResponse>('/settings').then((response) => response.data),
    enabled: isAuthorized,
    retry: false,
  })

  const loginInfoQuery = useQuery({
    queryKey: ['system-settings', 'login-info'],
    queryFn: () => apiClient.get<LoginInfoResponse>('/settings/login-info').then((response) => response.data),
    enabled: isAuthorized,
    retry: false,
  })

  const menuQuery = useQuery({
    queryKey: ['system-settings', 'menu'],
    queryFn: () => apiClient.get<MenuSettingsResponse>('/settings/menu').then((response) => response.data),
    enabled: isAuthorized,
    retry: false,
  })

  useEffect(() => {
    if (!themeColorDirty) {
      setThemeColor(normalizeThemeColor(settingsQuery.data?.settings?.theme_color ?? currentThemeColor))
    }
  }, [currentThemeColor, settingsQuery.data?.settings?.theme_color, themeColorDirty])

  useEffect(() => {
    setShowDefaultCredentials(Boolean(loginInfoQuery.data?.show_default_credentials))
  }, [loginInfoQuery.data?.show_default_credentials])

  useEffect(() => {
    setMenuItems(normalizeMenuItems(menuQuery.data?.menu))
  }, [menuQuery.data?.menu])

  const saveThemeMutation = useMutation({
    mutationFn: (color: string) => apiClient.post<ThemeSettingsResponse>('/settings/theme', { color }),
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '主题色保存失败'))
    },
    onSuccess: (response) => {
      const nextThemeColor = normalizeThemeColor(response.data.color ?? themeColor)
      setThemeColor(nextThemeColor)
      setThemeColorDirty(false)
      persistThemeColor(nextThemeColor)
      messageApi.success('主题色已保存')
    },
  })

  const loginInfoMutation = useMutation({
    mutationFn: (enabled: boolean) => apiClient.post<LoginInfoResponse>('/settings/login-info', { show_default_credentials: enabled }),
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '登录信息设置保存失败'))
    },
    onSuccess: (response) => {
      setShowDefaultCredentials(Boolean(response.data.show_default_credentials))
      messageApi.success('登录信息设置已更新')
    },
  })

  const passwordMutation = useMutation({
    mutationFn: (values: PasswordFormValues) => apiClient.post('/admin/password', { new_password: values.new_password.trim() }),
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '密码修改失败'))
    },
    onSuccess: () => {
      passwordForm.resetFields()
      messageApi.success('管理员密码已更新')
    },
  })

  const menuMutation = useMutation({
    mutationFn: (items: MenuSettingsItem[]) =>
      apiClient.post<MenuSettingsResponse>('/settings/menu', {
        menu: items.map((item, index) => ({
          ...item,
          order: index,
        })),
      }),
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '菜单设置保存失败'))
    },
    onSuccess: (response) => {
      const nextMenu = normalizeMenuItems(response.data.menu ?? menuItems)
      setMenuItems(nextMenu)
      messageApi.success('菜单设置已保存')
    },
  })

  const clearCacheMutation = useMutation({
    mutationFn: () => apiClient.post('/runtime/cache/clear'),
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '缓存清理失败'))
    },
    onSuccess: () => {
      messageApi.success('缓存已清理')
    },
  })

  const restartMutation = useMutation({
    mutationFn: () => apiClient.post('/runtime/restart'),
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '系统重启失败'))
    },
    onSuccess: () => {
      messageApi.success('系统重启指令已发送')
    },
  })

  const restoreMutation = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)

      return apiClient.post('/backup/import', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '备份恢复失败'))
    },
    onSuccess: () => {
      setRestoreModalOpen(false)
      setRestoreFile(null)
      messageApi.success('备份恢复成功')
    },
  })

  if (!isAuthorized) {
    return <Alert message="需要管理员登录后才能访问系统设置" showIcon type="warning" />
  }

  const loginUsername = loginInfoQuery.data?.default_username ?? 'admin'
  const anyQueryLoading = settingsQuery.isLoading || loginInfoQuery.isLoading || menuQuery.isLoading

  const restoreUploadProps: UploadProps = {
    accept: '.db,.sqlite,.sqlite3,.zip',
    beforeUpload: (file) => {
      setRestoreFile(file)
      setRestoreModalOpen(true)
      return Upload.LIST_IGNORE
    },
    maxCount: 1,
    showUploadList: false,
  }

  const basicSettingsContent = (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <Card title="主题设置">
        <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
          <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
            调整后台主色，保存后会立即同步到当前主题展示。
          </Typography.Paragraph>

          <Space align="center" size="middle" wrap>
            <Space size="small">
              <BgColorsOutlined aria-hidden="true" />
              <Typography.Text strong>主题色</Typography.Text>
            </Space>

            <Input
              aria-label="主题色选择"
              onChange={(event) => {
                setThemeColorDirty(true)
                setThemeColor(normalizeThemeColor(event.target.value))
              }}
              style={{ width: 64 }}
              type="color"
              value={themeColor}
            />

            <Typography.Text code>{themeColor}</Typography.Text>

            <Button
              aria-label="保存主题"
              icon={<SaveOutlined />}
              loading={saveThemeMutation.isPending}
              onClick={() => saveThemeMutation.mutate(themeColor)}
              type="primary"
            >
              保存主题
            </Button>
          </Space>
        </Space>
      </Card>

      <Card title="登录信息设置">
        <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
          <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
            控制登录页是否展示默认管理员登录提示，避免在生产环境暴露敏感信息。
          </Typography.Paragraph>

          <Space align="center" size="middle" wrap>
            <Switch
              aria-label="显示默认登录信息"
              checked={showDefaultCredentials}
              loading={loginInfoMutation.isPending}
              onChange={(checked) => {
                const previousValue = showDefaultCredentials
                setShowDefaultCredentials(checked)
                loginInfoMutation.mutate(checked, {
                  onError: () => {
                    setShowDefaultCredentials(previousValue)
                  },
                })
              }}
            />

            <Typography.Text>
              {showDefaultCredentials ? `当前默认用户名：${loginUsername}` : '默认登录信息已隐藏'}
            </Typography.Text>
          </Space>
        </Space>
      </Card>
    </Space>
  )

  const accountSecurityContent = (
    <Card title="修改管理员密码">
      <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          为保证后台安全，请设置一个新的管理员密码并妥善保管。
        </Typography.Paragraph>

        <Form<PasswordFormValues> form={passwordForm} layout="vertical" onFinish={(values) => passwordMutation.mutate(values)}>
          <Form.Item label="新密码" name="new_password" rules={[{ required: true, message: '请输入新密码' }]}> 
            <Input.Password autoComplete="new-password" placeholder="请输入新密码" />
          </Form.Item>

          <Form.Item
            dependencies={['new_password']}
            label="确认新密码"
            name="confirm"
            rules={[
              { required: true, message: '请再次确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve()
                  }

                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" placeholder="请再次输入新密码" />
          </Form.Item>

          <Button htmlType="submit" loading={passwordMutation.isPending} type="primary">
            更新密码
          </Button>
        </Form>
      </Space>
    </Card>
  )

  const menuManagementContent = (
    <Card
      extra={
        <Button
          aria-label="保存菜单设置"
          icon={<SaveOutlined />}
          loading={menuMutation.isPending}
          onClick={() => menuMutation.mutate(menuItems)}
          type="primary"
        >
          保存菜单设置
        </Button>
      }
      title="菜单显示与排序"
    >
      {menuQuery.isLoading ? <Skeleton active paragraph={{ rows: 5 }} /> : null}

      {!menuQuery.isLoading && menuItems.length === 0 ? (
        <Empty description="暂无菜单配置" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : null}

      {!menuQuery.isLoading && menuItems.length > 0 ? (
        <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
          {menuItems.map((item, index) => (
            <Card key={item.key} size="small">
              <Space align="center" size="middle" style={{ display: 'flex', justifyContent: 'space-between' }} wrap>
                <Space direction="vertical" size={2}>
                  <Typography.Text strong>{item.label}</Typography.Text>
                  <Typography.Text code>{item.key}</Typography.Text>
                  <Typography.Text type="secondary">排序：{index + 1}</Typography.Text>
                </Space>

                <Space align="center" wrap>
                  <Switch
                    aria-label={`切换 ${item.key} 可见状态`}
                    checked={item.visible}
                    onChange={(checked) => {
                      setMenuItems((currentItems) =>
                        currentItems.map((currentItem, currentIndex) =>
                          currentIndex === index
                            ? {
                                ...currentItem,
                                visible: checked,
                              }
                            : currentItem,
                        ),
                      )
                    }}
                  />

                  <Button
                    aria-label={`上移 ${item.label}`}
                    disabled={index === 0}
                    icon={<ArrowUpOutlined />}
                    onClick={() => setMenuItems((currentItems) => reorderMenuItems(currentItems, index, index - 1))}
                  />

                  <Button
                    aria-label={`下移 ${item.label}`}
                    disabled={index === menuItems.length - 1}
                    icon={<ArrowDownOutlined />}
                    onClick={() => setMenuItems((currentItems) => reorderMenuItems(currentItems, index, index + 1))}
                  />
                </Space>
              </Space>
            </Card>
          ))}
        </Space>
      ) : null}
    </Card>
  )

  const systemToolsContent = (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <Card title="备份与恢复">
        <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
          <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
            导出当前系统数据备份，或上传已有备份文件进行恢复。恢复操作会覆盖现有数据。
          </Typography.Paragraph>

          <Space wrap>
            <Button
              aria-label="导出备份"
              icon={<CloudDownloadOutlined />}
              onClick={() => {
                if (typeof window !== 'undefined') {
                  window.location.assign('/api/backup/export')
                }
              }}
            >
              导出备份
            </Button>

            <Upload {...restoreUploadProps}>
              <Button aria-label="导入恢复" icon={<CloudUploadOutlined />}>导入恢复</Button>
            </Upload>
          </Space>
        </Space>
      </Card>

      <Card title="运行时工具">
        <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
          <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
            使用以下操作维护系统运行状态，危险操作均需要二次确认。
          </Typography.Paragraph>

          <Space wrap>
            <Popconfirm
              cancelText="取消"
              description="清理后系统将重新建立缓存"
              okText="确认清理"
              onConfirm={() => clearCacheMutation.mutate()}
              title="确认清理系统缓存吗？"
            >
              <Button icon={<ReloadOutlined />} loading={clearCacheMutation.isPending}>
                清理缓存
              </Button>
            </Popconfirm>

            <Popconfirm
              cancelText="取消"
              description="系统将重启，当前连接将断开"
              okButtonProps={{ danger: true }}
              okText="确认重启"
              onConfirm={() => restartMutation.mutate()}
              title="确认重启系统吗？"
            >
              <Button aria-label="重启系统" danger icon={<SafetyCertificateOutlined />} loading={restartMutation.isPending}>
                重启系统
              </Button>
            </Popconfirm>
          </Space>
        </Space>
      </Card>
    </Space>
  )

  const tabItems: TabsProps['items'] = [
    {
      key: 'basic',
      label: '基本设置',
      children: basicSettingsContent,
    },
    {
      key: 'security',
      label: '账号安全',
      children: accountSecurityContent,
    },
    {
      key: 'menu',
      label: '菜单管理',
      children: menuManagementContent,
    },
    {
      key: 'tools',
      label: '系统工具',
      children: systemToolsContent,
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      {contextHolder}

      <div>
        <Typography.Title level={3} style={{ marginBottom: token.marginXS, marginTop: 0 }}>
          系统设置
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          统一管理后台主题、账号安全、菜单展示以及备份恢复等系统级配置。
        </Typography.Paragraph>
      </div>

      {settingsQuery.isError ? (
        <Alert description={getErrorMessage(settingsQuery.error, '请稍后重试')} message="基础设置加载失败" showIcon type="error" />
      ) : null}

      {loginInfoQuery.isError ? (
        <Alert description={getErrorMessage(loginInfoQuery.error, '请稍后重试')} message="登录信息设置加载失败" showIcon type="error" />
      ) : null}

      {menuQuery.isError ? (
        <Alert description={getErrorMessage(menuQuery.error, '请稍后重试')} message="菜单设置加载失败" showIcon type="error" />
      ) : null}

      <Tabs
        items={tabItems}
        tabBarStyle={{ marginBottom: token.marginLG }}
        tabPosition="top"
      />

      <Modal
        cancelText="取消"
        confirmLoading={restoreMutation.isPending}
        okButtonProps={{ danger: true }}
        okText="确认恢复"
        onCancel={() => {
          setRestoreModalOpen(false)
          setRestoreFile(null)
        }}
        onOk={() => {
          if (restoreFile) {
            restoreMutation.mutate(restoreFile)
          }
        }}
        open={restoreModalOpen}
        title="确认恢复备份"
      >
        <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
          <Alert message="恢复将覆盖当前数据，不可撤销" showIcon type="warning" />
          <Typography.Text type="secondary">
            {restoreFile ? `待恢复文件：${restoreFile.name}` : '请选择需要恢复的备份文件。'}
          </Typography.Text>
        </Space>
      </Modal>

      {anyQueryLoading ? <Skeleton active paragraph={{ rows: 2 }} title={false} /> : null}
    </Space>
  )
}
