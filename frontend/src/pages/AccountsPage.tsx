import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { apiClient } from '../api/client'

type AccountsEnvelope = {
  accounts?: AccountListItem[]
  data?: AccountListItem[]
}

type AccountListItem = {
  account_id: string
  username: string
  notes: string
  enabled: boolean
  show_browser: boolean
  has_cookie: boolean
  created_at?: string | null
  updated_at?: string | null
}

type AccountCompatEnvelope = {
  cookies?: AccountCompatDetail[]
  data?: AccountCompatDetail[]
}

type AccountCompatDetail = {
  id: string
  value: string
  username: string
  enabled: boolean
  show_browser: boolean
  has_cookie: boolean
  cookie_status: string
  has_password: boolean
  remark: string
  pause_duration: number
  created_at?: string | null
  updated_at?: string | null
}

type ManagedAccount = {
  account_id: string
  username: string
  notes: string
  enabled: boolean
  show_browser: boolean
  has_cookie: boolean
  cookie_status: string
  has_password: boolean
  cookie_value: string
  pause_duration: number
  created_at?: string | null
  updated_at?: string | null
}

type QrLoginCreateResponse = {
  session_id: string
  qr_code_url?: string
  qr_image_data?: string
  status?: string
  expires_at?: number
}

type QrLoginStatusResponse = {
  session_id: string
  status: string
  qr_code_url?: string
  qr_image_data?: string
  result_cookie?: string
}

type PasswordLoginCreateResponse = {
  session_id: string
  status?: string
  message?: string
}

type PasswordLoginStatusResponse = {
  session_id: string
  status: string
  message?: string
  result_cookie?: string
  cookie_valid?: boolean
  cookie_count?: number
  verification_url?: string
  qr_code_url?: string
  verification_type?: string
  verification_message?: string
}

const PASSWORD_STATUS_COLOR_MAP = {
  processing: 'processing',
  success: 'success',
  failed: 'error',
  error: 'error',
  cancelled: 'default',
  expired: 'warning',
} as const

const PASSWORD_STATUS_LABEL_MAP = {
  processing: '登录中',
  success: '登录成功',
  failed: '登录失败',
  error: '登录异常',
  cancelled: '已取消',
  expired: '已过期',
} as const

function getPasswordStatusDisplay(status?: string): keyof typeof PASSWORD_STATUS_COLOR_MAP {
  switch (status) {
    case 'success':
    case 'failed':
    case 'error':
    case 'cancelled':
    case 'expired':
      return status
    case 'processing':
    case 'pending':
    default:
      return 'processing'
  }
}

type RefreshCookieResponse = {
  message?: string
}

type AddTabKey = 'qr' | 'password' | 'manual'

type QrFormValues = {
  account_id: string
}

type PasswordFormValues = {
  account_id: string
  password: string
  show_browser: boolean
  username: string
}

type ManualFormValues = {
  account_id: string
  cookie_str: string
}

type EditFormValues = {
  pause_duration: number
  remark: string
}

function normalizeArray<T>(payload: T[] | { accounts?: T[]; cookies?: T[]; data?: T[] } | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  if (!payload) {
    return [] as T[]
  }

  return payload.accounts ?? payload.cookies ?? payload.data ?? []
}

function buildAccounts(
  accountsPayload: AccountListItem[] | AccountsEnvelope,
  detailsPayload: AccountCompatDetail[] | AccountCompatEnvelope,
) {
  const accounts = normalizeArray(accountsPayload)
  const details = normalizeArray(detailsPayload)
  const merged = new Map<string, ManagedAccount>()

  accounts.forEach((account) => {
    merged.set(account.account_id, {
      account_id: account.account_id,
      username: account.username ?? '',
      notes: account.notes ?? '',
      enabled: Boolean(account.enabled),
      show_browser: Boolean(account.show_browser),
      has_cookie: Boolean(account.has_cookie),
      cookie_status: account.has_cookie ? 'available' : 'missing',
      has_password: false,
      cookie_value: '',
      pause_duration: 10,
      created_at: account.created_at ?? null,
      updated_at: account.updated_at ?? null,
    })
  })

  details.forEach((detail) => {
    const existing = merged.get(detail.id)

    merged.set(detail.id, {
      account_id: detail.id,
      username: detail.username ?? existing?.username ?? '',
      notes: detail.remark ?? existing?.notes ?? '',
      enabled: Boolean(detail.enabled ?? existing?.enabled),
      show_browser: Boolean(detail.show_browser ?? existing?.show_browser),
      has_cookie: Boolean(detail.has_cookie ?? existing?.has_cookie),
      cookie_status: detail.cookie_status ?? existing?.cookie_status ?? 'missing',
      has_password: Boolean(detail.has_password),
      cookie_value: detail.value ?? '',
      pause_duration: detail.pause_duration ?? existing?.pause_duration ?? 10,
      created_at: detail.created_at ?? existing?.created_at ?? null,
      updated_at: detail.updated_at ?? existing?.updated_at ?? null,
    })
  })

  return Array.from(merged.values()).sort((left, right) => left.account_id.localeCompare(right.account_id))
}

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

function isConflictError(error: unknown) {
  return axios.isAxiosError(error) && error.response?.status === 409
}

function getQrImageSource(session?: QrLoginCreateResponse | QrLoginStatusResponse | null) {
  if (!session) {
    return ''
  }

  if (session.qr_image_data) {
    return session.qr_image_data.startsWith('data:')
      ? session.qr_image_data
      : `data:image/png;base64,${session.qr_image_data}`
  }

  return session.qr_code_url ?? ''
}

async function createAccountRecord(payload: {
  account_id: string
  cookie_str?: string
  enabled?: boolean
  notes?: string
  password?: string
  show_browser?: boolean
  username?: string
}) {
  return apiClient.post('/accounts', {
    account_id: payload.account_id,
    cookie_str: payload.cookie_str ?? '',
    enabled: payload.enabled ?? true,
    notes: payload.notes ?? '',
    password: payload.password ?? '',
    show_browser: payload.show_browser ?? false,
    username: payload.username ?? '',
  })
}

export default function AccountsPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [activeAddTab, setActiveAddTab] = useState<AddTabKey>('qr')
  const [editingAccount, setEditingAccount] = useState<ManagedAccount | null>(null)
  const [qrSession, setQrSession] = useState<QrLoginCreateResponse | null>(null)
  const [qrPendingAccountId, setQrPendingAccountId] = useState('')
  const [qrPollingEnabled, setQrPollingEnabled] = useState(false)
  const [passwordSession, setPasswordSession] = useState<PasswordLoginCreateResponse | null>(null)
  const [passwordPollingEnabled, setPasswordPollingEnabled] = useState(false)
  const [passwordElapsed, setPasswordElapsed] = useState(0)
  const handledQrSessionRef = useRef<string | null>(null)
  const handledPasswordSessionRef = useRef<string | null>(null)

  useEffect(() => {
    if (!passwordPollingEnabled) {
      return
    }
    setPasswordElapsed(0)
    const interval = setInterval(() => {
      setPasswordElapsed((prev) => prev + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [passwordPollingEnabled])

  const [editForm] = Form.useForm<EditFormValues>()

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const [accountsResponse, detailsResponse] = await Promise.all([
        apiClient.get<AccountListItem[] | AccountsEnvelope>('/accounts'),
        apiClient.get<AccountCompatDetail[] | AccountCompatEnvelope>('/cookies/details'),
      ])

      return buildAccounts(accountsResponse.data, detailsResponse.data)
    },
    retry: false,
  })

  const qrStatusQuery = useQuery({
    queryKey: ['accounts', 'qr-login-status', qrSession?.session_id],
    queryFn: () =>
      apiClient
        .get<QrLoginStatusResponse>(`/qr-login/check/${qrSession?.session_id}`)
        .then((response) => response.data),
    enabled: Boolean(qrSession?.session_id) && qrPollingEnabled,
    refetchInterval: qrPollingEnabled ? 2000 : false,
    retry: false,
  })

  const passwordStatusQuery = useQuery({
    queryKey: ['accounts', 'password-login-status', passwordSession?.session_id],
    queryFn: () =>
      apiClient
        .get<PasswordLoginStatusResponse>(`/password-login/check/${passwordSession?.session_id}`)
        .then((response) => response.data),
    enabled: Boolean(passwordSession?.session_id) && passwordPollingEnabled,
    refetchInterval: passwordPollingEnabled ? 2000 : false,
    retry: false,
  })

  const refreshAccounts = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['accounts'] })
  }, [queryClient])

  const closeAddModal = useCallback(() => {
    setIsAddModalOpen(false)
    setActiveAddTab('qr')
    setQrSession(null)
    setQrPendingAccountId('')
    setQrPollingEnabled(false)
    setPasswordSession(null)
    setPasswordPollingEnabled(false)
    setPasswordElapsed(0)
    handledQrSessionRef.current = null
    handledPasswordSessionRef.current = null
  }, [])

  const closeEditModal = useCallback(() => {
    setIsEditModalOpen(false)
    setEditingAccount(null)
    editForm.resetFields()
  }, [editForm])

  const toggleStatusMutation = useMutation({
    mutationFn: async (account: ManagedAccount) => {
      await apiClient.put(`/cookies/${account.account_id}/status`, {
        enabled: !account.enabled,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '更新账号状态失败'))
    },
    onSuccess: async (_, account) => {
      messageApi.success(account.enabled ? '账号已禁用' : '账号已启用')
      await refreshAccounts()
    },
  })

  const refreshCookieMutation = useMutation({
    mutationFn: async (account: ManagedAccount) => {
      const cookieValue = account.cookie_value ?? ''
      if (!cookieValue.trim()) {
        throw new Error('当前账号没有可刷新的 Cookie')
      }

      const response = await apiClient.post<RefreshCookieResponse>('/qr-login/refresh-cookies', {
        cookie_id: account.account_id,
        qr_cookies: cookieValue,
      })

      return response.data
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '刷新 Cookie 失败'))
    },
    onSuccess: async (payload) => {
      messageApi.success(payload.message === 'cookie_refreshed' ? 'Cookie 刷新成功' : payload.message ?? 'Cookie 刷新成功')
      await refreshAccounts()
    },
  })

  const deleteAccountMutation = useMutation({
    mutationFn: async (accountId: string) => {
      await apiClient.delete(`/accounts/${accountId}`)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '删除账号失败'))
    },
    onSuccess: async () => {
      messageApi.success('账号已删除')
      await refreshAccounts()
    },
  })

  const updateRemarkPauseMutation = useMutation({
    mutationFn: async (values: { account_id: string; pause_duration: number; remark: string }) => {
      await Promise.all([
        apiClient.put(`/cookies/${values.account_id}/remark`, {
          remark: values.remark,
        }),
        apiClient.put(`/cookies/${values.account_id}/pause-duration`, {
          pause_duration: values.pause_duration,
        }),
      ])
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '更新备注失败'))
    },
    onSuccess: async () => {
      messageApi.success('备注与暂停时长已更新')
      closeEditModal()
      await refreshAccounts()
    },
  })

  const manualAddMutation = useMutation({
    mutationFn: async (values: ManualFormValues) => {
      await createAccountRecord({
        account_id: values.account_id.trim(),
        cookie_str: values.cookie_str.trim(),
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '保存 Cookie 失败'))
    },
    onSuccess: async () => {
      messageApi.success('账号已添加')
      closeAddModal()
      await refreshAccounts()
    },
  })

  const qrStartMutation = useMutation({
    mutationFn: async (values: QrFormValues) => {
      const response = await apiClient.post<QrLoginCreateResponse>('/qr-login/generate')
      return {
        accountId: values.account_id.trim(),
        session: response.data,
      }
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '生成二维码失败'))
    },
    onSuccess: ({ accountId, session }) => {
      handledQrSessionRef.current = null
      setQrPendingAccountId(accountId)
      setQrSession(session)
      setQrPollingEnabled(true)
      messageApi.success('二维码已生成，请使用闲鱼扫码登录')
    },
  })

  const passwordStartMutation = useMutation({
    mutationFn: async (values: PasswordFormValues) => {
      const normalizedValues = {
        account_id: values.account_id.trim(),
        password: values.password.trim(),
        show_browser: Boolean(values.show_browser),
        username: values.username.trim(),
      }

      try {
        await createAccountRecord({
          account_id: normalizedValues.account_id,
          password: normalizedValues.password,
          show_browser: normalizedValues.show_browser,
          username: normalizedValues.username,
        })
      } catch (error) {
        if (!isConflictError(error)) {
          throw error
        }
      }

      const response = await apiClient.post<PasswordLoginCreateResponse>('/password-login', {
        account: normalizedValues.username,
        account_id: normalizedValues.account_id,
        password: normalizedValues.password,
        show_browser: normalizedValues.show_browser,
        username: normalizedValues.username,
      })

      return response.data
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '密码登录启动失败'))
    },
    onSuccess: (payload) => {
      handledPasswordSessionRef.current = null
      setPasswordSession(payload)
      setPasswordPollingEnabled(true)
      messageApi.success('密码登录已启动，正在等待结果')
    },
  })

  useEffect(() => {
    if (!qrSession?.session_id) {
      return
    }

    const statusPayload = qrStatusQuery.data
    if (!statusPayload) {
      return
    }

    if (statusPayload.status === 'expired' && handledQrSessionRef.current !== `expired:${qrSession.session_id}`) {
      handledQrSessionRef.current = `expired:${qrSession.session_id}`
      setQrPollingEnabled(false)
      messageApi.error('二维码已过期，请重新生成')
      return
    }

    if (statusPayload.status !== 'success' || handledQrSessionRef.current === qrSession.session_id) {
      return
    }

    handledQrSessionRef.current = qrSession.session_id
    setQrPollingEnabled(false)

    void (async () => {
      if (!statusPayload.result_cookie?.trim()) {
        messageApi.error('二维码登录成功，但未获取到 Cookie')
        return
      }

      try {
        await createAccountRecord({
          account_id: qrPendingAccountId,
          cookie_str: statusPayload.result_cookie,
        })
        messageApi.success('二维码登录成功，账号已添加')
        closeAddModal()
        await refreshAccounts()
      } catch (error) {
        messageApi.error(getErrorMessage(error, '二维码登录成功，但保存账号失败'))
      }
    })()
  }, [closeAddModal, messageApi, qrPendingAccountId, qrSession, qrStatusQuery.data, refreshAccounts])

  useEffect(() => {
    if (!passwordSession?.session_id) {
      return
    }

    const statusPayload = passwordStatusQuery.data
    if (!statusPayload) {
      return
    }

    if (statusPayload.status === 'expired' && handledPasswordSessionRef.current !== `expired:${passwordSession.session_id}`) {
      handledPasswordSessionRef.current = `expired:${passwordSession.session_id}`
      setPasswordSession((current) =>
        current
          ? {
              ...current,
              message: statusPayload.message ?? current.message ?? '密码登录会话已过期，请重新发起',
              status: 'expired',
            }
          : current,
      )
      setPasswordPollingEnabled(false)
      messageApi.error('密码登录会话已过期，请重新发起')
      return
    }

    if (statusPayload.status === 'cancelled' && handledPasswordSessionRef.current !== `cancelled:${passwordSession.session_id}`) {
      handledPasswordSessionRef.current = `cancelled:${passwordSession.session_id}`
      setPasswordSession((current) =>
        current
          ? {
              ...current,
              message: statusPayload.message ?? current.message ?? '登录已取消',
              status: 'cancelled',
            }
          : current,
      )
      setPasswordPollingEnabled(false)
      return
    }

    if (statusPayload.status === 'success' && handledPasswordSessionRef.current !== passwordSession.session_id) {
      handledPasswordSessionRef.current = passwordSession.session_id
      setPasswordPollingEnabled(false)

      void (async () => {
        if (!statusPayload.result_cookie || statusPayload.result_cookie.trim() === '') {
          messageApi.warning('登录状态为成功但未获得有效Cookie，请重试')
        } else {
          messageApi.success(statusPayload.message || '密码登录成功，Cookie 已写入账号')
        }
        closeAddModal()
        await refreshAccounts()
      })()

      return
    }

    const isPasswordFailureStatus = statusPayload.status === 'failed' || statusPayload.status === 'error'
    const isUnhandledPasswordStatus = !['pending', 'processing', 'success', 'failed', 'error', 'cancelled', 'expired'].includes(
      statusPayload.status,
    )

    if ((isPasswordFailureStatus || isUnhandledPasswordStatus) && handledPasswordSessionRef.current !== `error:${passwordSession.session_id}`) {
      handledPasswordSessionRef.current = `error:${passwordSession.session_id}`
      setPasswordSession((current) =>
        current
          ? {
              ...current,
              message: statusPayload.message ?? statusPayload.verification_message ?? current.message ?? '密码登录失败',
              status: isPasswordFailureStatus ? statusPayload.status : 'error',
            }
          : current,
      )
      setPasswordPollingEnabled(false)
      messageApi.error(statusPayload.message || statusPayload.verification_message || '密码登录失败')
    }
  }, [closeAddModal, messageApi, passwordSession, passwordStatusQuery.data, refreshAccounts])

  const columns = useMemo<ColumnsType<ManagedAccount>>(
    () => [
      {
        dataIndex: 'account_id',
        key: 'account_id',
        title: '账号ID',
        width: 160,
      },
      {
        dataIndex: 'username',
        key: 'username',
        render: (value: string) => value || '—',
        title: '用户名',
        width: 160,
      },
      {
        dataIndex: 'notes',
        key: 'notes',
        render: (value: string) => value || '—',
        title: '备注',
      },
      {
        dataIndex: 'enabled',
        key: 'enabled',
        render: (value: boolean) => <Tag color={value ? 'success' : 'default'}>{value ? '启用' : '停用'}</Tag>,
        title: '状态',
        width: 100,
      },
      {
        dataIndex: 'pause_duration',
        key: 'pause_duration',
        render: (value: number) => `${value} 分钟`,
        title: '暂停时长',
        width: 120,
      },
      {
        dataIndex: 'created_at',
        key: 'created_at',
        render: (value?: string | null) => value || '—',
        title: '创建时间',
        width: 180,
      },
      {
        key: 'actions',
        render: (_, record) => (
          <Space size={[8, 8]} wrap>
            <Button
              loading={toggleStatusMutation.isPending && toggleStatusMutation.variables?.account_id === record.account_id}
              onClick={() => toggleStatusMutation.mutate(record)}
              size="small"
            >
              {record.enabled ? '禁用' : '启用'}
            </Button>
            <Button
              loading={refreshCookieMutation.isPending && refreshCookieMutation.variables?.account_id === record.account_id}
              onClick={() => refreshCookieMutation.mutate(record)}
              size="small"
            >
              刷新Cookie
            </Button>
            <Button
              onClick={() => {
                setEditingAccount(record)
                setIsEditModalOpen(true)
                editForm.setFieldsValue({
                  pause_duration: record.pause_duration,
                  remark: record.notes,
                })
              }}
              size="small"
            >
              备注
            </Button>
            <Popconfirm
              cancelText="取消"
              okText="删除"
              onConfirm={() => deleteAccountMutation.mutate(record.account_id)}
              title={`确认删除账号 ${record.account_id}？`}
            >
              <Button
                danger
                loading={deleteAccountMutation.isPending && deleteAccountMutation.variables === record.account_id}
                size="small"
              >
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
        title: '操作',
        width: 260,
      },
    ],
    [deleteAccountMutation, editForm, refreshCookieMutation, toggleStatusMutation],
  )

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      {contextHolder}

      <div>
        <Typography.Title level={3} style={{ marginBottom: 8, marginTop: 0 }}>
          账号管理
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          统一维护闲鱼账号的登录方式、Cookie、暂停时长与启用状态。
        </Typography.Paragraph>
      </div>

      {accountsQuery.isError ? (
        <Alert message="账号数据加载失败" showIcon type="error" description={getErrorMessage(accountsQuery.error, '请稍后重试')} />
      ) : null}

      <Card
        extra={
          <Button onClick={() => setIsAddModalOpen(true)} type="primary">
            添加账号
          </Button>
        }
        title="账号列表"
      >
        <Table
          columns={columns}
          dataSource={accountsQuery.data ?? []}
          loading={accountsQuery.isLoading}
          locale={{
            emptyText: <Empty description="暂无账号" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
          }}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
          }}
          rowKey="account_id"
          scroll={{ x: 1100 }}
        />
      </Card>

      <Modal
        destroyOnHidden
        footer={<Button onClick={closeAddModal}>取消</Button>}
        onCancel={closeAddModal}
        open={isAddModalOpen}
        title="添加账号"
      >
        <Tabs
          activeKey={activeAddTab}
          items={[
            {
              key: 'qr',
              label: 'QR登录',
              children: (
                <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
                  <Form layout="vertical" onFinish={(values: QrFormValues) => qrStartMutation.mutate(values)}>
                    <Form.Item label="账号ID" name="account_id" rules={[{ message: '请输入账号ID', required: true }]}>
                      <Input placeholder="请输入账号ID" />
                    </Form.Item>
                    <Button htmlType="submit" loading={qrStartMutation.isPending} type="primary">
                      生成二维码
                    </Button>
                  </Form>

                  {qrSession ? (
                    <Card size="small" title="扫码状态">
                      <Space align="start" direction="vertical" size="middle" style={{ display: 'flex' }}>
                        <Tag color={qrStatusQuery.data?.status === 'success' ? 'success' : qrStatusQuery.data?.status === 'expired' ? 'warning' : 'processing'}>
                          {qrStatusQuery.data?.status === 'success'
                            ? '登录成功'
                            : qrStatusQuery.data?.status === 'expired'
                              ? '已过期'
                              : '等待扫码'}
                        </Tag>
                        {getQrImageSource(qrStatusQuery.data ?? qrSession) ? (
                          <img
                            alt="登录二维码"
                            src={getQrImageSource(qrStatusQuery.data ?? qrSession)}
                            style={{ borderRadius: 8, maxWidth: 240, width: '100%' }}
                          />
                        ) : null}
                        <Typography.Text type="secondary">扫码成功后会自动保存新账号 Cookie。</Typography.Text>
                      </Space>
                    </Card>
                  ) : null}
                </Space>
              ),
            },
            {
              key: 'password',
              label: '密码登录',
              children: (
                <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
                  <Alert
                    message="密码登录会先保存账号，再异步获取 Cookie。"
                    showIcon
                    type="info"
                  />
                  <Form
                    initialValues={{ show_browser: false, username: '' }}
                    layout="vertical"
                    onFinish={(values: PasswordFormValues) => passwordStartMutation.mutate(values)}
                  >
                    <Form.Item label="账号ID" name="account_id" rules={[{ message: '请输入账号ID', required: true }]}>
                      <Input placeholder="请输入账号ID" />
                    </Form.Item>
                    <Form.Item label="用户名" name="username">
                      <Input placeholder="可选，默认沿用账号ID" />
                    </Form.Item>
                    <Form.Item label="密码" name="password" rules={[{ message: '请输入密码', required: true }]}>
                      <Input.Password placeholder="请输入密码" />
                    </Form.Item>
                    <Form.Item label="显示浏览器" name="show_browser" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                    <Button htmlType="submit" loading={passwordStartMutation.isPending} type="primary">
                      开始登录
                    </Button>
                  </Form>

                  {passwordSession ? (
                    <Card size="small" title="登录状态">
                      <Space direction="vertical" size="small" style={{ display: 'flex' }}>
                        <Tag
                          color={
                            PASSWORD_STATUS_COLOR_MAP[
                              getPasswordStatusDisplay(
                                passwordSession.status === 'cancelled'
                                  ? passwordSession.status
                                  : passwordStatusQuery.data?.status ?? passwordSession.status,
                              )
                            ]
                          }
                        >
                          {
                            PASSWORD_STATUS_LABEL_MAP[
                              getPasswordStatusDisplay(
                                passwordSession.status === 'cancelled'
                                  ? passwordSession.status
                                  : passwordStatusQuery.data?.status ?? passwordSession.status,
                              )
                            ]
                          }
                        </Tag>
                        {passwordPollingEnabled ? (
                          <Typography.Text type="secondary">
                            已等待 {Math.floor(passwordElapsed / 60)}:{String(passwordElapsed % 60).padStart(2, '0')}
                          </Typography.Text>
                        ) : null}
                        <Typography.Text
                          type={
                            ['failed', 'error'].includes(
                              passwordSession.status === 'cancelled'
                                ? passwordSession.status
                                : passwordStatusQuery.data?.status ?? passwordSession.status ?? 'processing',
                            )
                              ? 'danger'
                              : undefined
                          }
                        >
                          {passwordSession.status === 'cancelled'
                            ? passwordSession.message || '登录已取消'
                            : passwordStatusQuery.data?.message ||
                              passwordStatusQuery.data?.verification_message ||
                              passwordSession.message ||
                              '等待登录结果…'}
                        </Typography.Text>
                        {passwordStatusQuery.data?.verification_message ? (
                          <Typography.Text type="secondary">{passwordStatusQuery.data.verification_message}</Typography.Text>
                        ) : null}
                        {passwordStatusQuery.data?.verification_type ? (
                          <Typography.Text type="secondary">验证类型：{passwordStatusQuery.data.verification_type}</Typography.Text>
                        ) : null}
                        {passwordStatusQuery.data?.verification_url ? (
                          <Typography.Link href={passwordStatusQuery.data.verification_url} target="_blank">
                            打开验证页面
                          </Typography.Link>
                        ) : null}
                        {passwordPollingEnabled ? (
                          <Button
                            danger
                            onClick={async () => {
                              if (!passwordSession?.session_id) return
                              try {
                                await apiClient.delete(`/password-login/${passwordSession.session_id}`)
                                setPasswordSession((current) =>
                                  current
                                    ? {
                                        ...current,
                                        message: '登录已取消',
                                        status: 'cancelled',
                                      }
                                    : current,
                                )
                                setPasswordPollingEnabled(false)
                                messageApi.info('登录已取消')
                              } catch {
                                messageApi.error('取消失败')
                              }
                            }}
                            size="small"
                          >
                            取消登录
                          </Button>
                        ) : null}
                      </Space>
                    </Card>
                  ) : null}
                </Space>
              ),
            },
            {
              key: 'manual',
              label: '手动Cookie',
              children: (
                <Form layout="vertical" onFinish={(values: ManualFormValues) => manualAddMutation.mutate(values)}>
                  <Form.Item label="账号ID" name="account_id" rules={[{ message: '请输入账号ID', required: true }]}>
                    <Input placeholder="请输入账号ID" />
                  </Form.Item>
                  <Form.Item label="Cookie" name="cookie_str" rules={[{ message: '请输入 Cookie', required: true }]}>
                    <Input.TextArea placeholder="请输入完整 Cookie 字符串" rows={5} />
                  </Form.Item>
                  <Button htmlType="submit" loading={manualAddMutation.isPending} type="primary">
                    保存 Cookie
                  </Button>
                </Form>
              ),
            },
          ]}
          onChange={(key) => setActiveAddTab(key as AddTabKey)}
        />
      </Modal>

      <Modal
        footer={null}
        onCancel={closeEditModal}
        open={isEditModalOpen}
        title={editingAccount ? `编辑账号：${editingAccount.account_id}` : '编辑账号'}
      >
        <Form form={editForm} layout="vertical" onFinish={(values) => editingAccount && updateRemarkPauseMutation.mutate({ ...values, account_id: editingAccount.account_id })}>
          <Form.Item label="备注" name="remark" rules={[{ max: 100, message: '备注最多 100 个字符' }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item label="暂停时长（分钟）" name="pause_duration" rules={[{ message: '请输入暂停时长', required: true }]}>
            <InputNumber max={60} min={0} precision={0} style={{ width: '100%' }} />
          </Form.Item>
          <Space>
            <Button htmlType="submit" loading={updateRemarkPauseMutation.isPending} type="primary">
              保存
            </Button>
            <Button onClick={closeEditModal}>取消</Button>
          </Space>
        </Form>
      </Modal>
    </Space>
  )
}
