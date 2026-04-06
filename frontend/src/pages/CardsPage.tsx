import { useEffect, useMemo, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
import type { UploadProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { apiClient } from '../api/client'

type CardContentType = 'text' | 'data' | 'api' | 'image' | 'yifan'

type AccountOption = {
  account_id: string
  username?: string
}

type AccountsResponse = AccountOption[] | { accounts?: AccountOption[]; data?: AccountOption[] }

type CardRecord = {
  id: number
  name: string
  content_type: CardContentType
  content: string
  account_id: string
  created_at?: string | null
}

type CardsResponse = CardRecord[] | { cards?: CardRecord[]; data?: CardRecord[] }

type UploadImageResponse = {
  data?: {
    image_url?: string
    path?: string
    url?: string
  }
  image_url?: string
  path?: string
  url?: string
}

type CardFormValues = {
  account_id: string
  api_key?: string
  api_url?: string
  app_key?: string
  callback_url?: string
  data_content?: string
  image_content?: string
  merchant_id?: string
  name: string
  text_content?: string
}

const CARD_TYPE_TABS: Array<{ key: CardContentType; label: string }> = [
  { key: 'text', label: '文本卡券' },
  { key: 'data', label: '批量数据' },
  { key: 'api', label: 'API卡券' },
  { key: 'image', label: '图片卡券' },
  { key: 'yifan', label: '易凡配置' },
]

function normalizeAccounts(payload: AccountsResponse | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  return payload?.accounts ?? payload?.data ?? []
}

function normalizeCards(payload: CardsResponse | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  return payload?.cards ?? payload?.data ?? []
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

function parseJsonObject(content: string) {
  try {
    const parsed = JSON.parse(content) as Record<string, unknown>
    return typeof parsed === 'object' && parsed !== null ? parsed : {}
  } catch {
    return {}
  }
}

function buildCardContent(values: CardFormValues, contentType: CardContentType) {
  switch (contentType) {
    case 'text':
      return values.text_content?.trim() ?? ''
    case 'data':
      return values.data_content?.trim() ?? ''
    case 'api':
      return JSON.stringify({
        api_key: values.api_key?.trim() ?? '',
        url: values.api_url?.trim() ?? '',
      })
    case 'image':
      return values.image_content?.trim() ?? ''
    case 'yifan':
      return JSON.stringify({
        app_key: values.app_key?.trim() ?? '',
        callback_url: values.callback_url?.trim() ?? '',
        merchant_id: values.merchant_id?.trim() ?? '',
      })
    default:
      return ''
  }
}

function buildFormValues(card: CardRecord): CardFormValues {
  const values: CardFormValues = {
    account_id: card.account_id,
    name: card.name,
  }

  if (card.content_type === 'text') {
    values.text_content = card.content
    return values
  }

  if (card.content_type === 'data') {
    values.data_content = card.content
    return values
  }

  if (card.content_type === 'image') {
    values.image_content = card.content
    return values
  }

  const parsed = parseJsonObject(card.content)

  if (card.content_type === 'api') {
    values.api_url = typeof parsed.url === 'string' ? parsed.url : card.content
    values.api_key = typeof parsed.api_key === 'string' ? parsed.api_key : ''
    return values
  }

  values.callback_url = typeof parsed.callback_url === 'string' ? parsed.callback_url : ''
  values.merchant_id = typeof parsed.merchant_id === 'string' ? parsed.merchant_id : ''
  values.app_key = typeof parsed.app_key === 'string' ? parsed.app_key : ''
  return values
}

function getUploadedImagePath(payload: UploadImageResponse | undefined) {
  return (
    payload?.path ??
    payload?.url ??
    payload?.image_url ??
    payload?.data?.path ??
    payload?.data?.url ??
    payload?.data?.image_url ??
    ''
  )
}

export default function CardsPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [editingCard, setEditingCard] = useState<CardRecord | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [activeType, setActiveType] = useState<CardContentType>('text')
  const [form] = Form.useForm<CardFormValues>()

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const response = await apiClient.get<AccountsResponse>('/accounts')
      return normalizeAccounts(response.data)
    },
    retry: false,
  })

  useEffect(() => {
    if (!selectedAccountId && accountsQuery.data?.length) {
      setSelectedAccountId(accountsQuery.data[0].account_id)
    }
  }, [accountsQuery.data, selectedAccountId])

  const cardsQuery = useQuery({
    queryKey: ['cards', selectedAccountId],
    queryFn: async () => {
      const response = await apiClient.get<CardsResponse>('/cards', {
        params: { account_id: selectedAccountId },
      })

      return normalizeCards(response.data)
    },
    enabled: Boolean(selectedAccountId),
    placeholderData: (previousData) => previousData,
    retry: false,
  })

  const accountOptions = useMemo(
    () =>
      (accountsQuery.data ?? []).map((account) => ({
        label: account.username ? `${account.username} (${account.account_id})` : account.account_id,
        value: account.account_id,
      })),
    [accountsQuery.data],
  )

  const refreshCards = async () => {
    await queryClient.invalidateQueries({ queryKey: ['cards'] })
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingCard(null)
    setActiveType('text')
    form.resetFields()
  }

  const createCardMutation = useMutation({
    mutationFn: async (payload: { account_id: string; content: string; content_type: CardContentType; name: string }) => {
      await apiClient.post('/cards', payload)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '新增卡券失败'))
    },
    onSuccess: async () => {
      messageApi.success('卡券已新增')
      closeModal()
      await refreshCards()
    },
  })

  const updateCardMutation = useMutation({
    mutationFn: async (payload: { account_id: string; card_id: number; content: string; content_type: CardContentType; name: string }) => {
      await apiClient.put(`/cards/${payload.card_id}`, {
        account_id: payload.account_id,
        content: payload.content,
        content_type: payload.content_type,
        name: payload.name,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '更新卡券失败'))
    },
    onSuccess: async () => {
      messageApi.success('卡券已更新')
      closeModal()
      await refreshCards()
    },
  })

  const deleteCardMutation = useMutation({
    mutationFn: async (cardId: number) => {
      await apiClient.delete(`/cards/${cardId}`)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '删除卡券失败'))
    },
    onSuccess: async () => {
      messageApi.success('卡券已删除')
      await refreshCards()
    },
  })

  const uploadProps: UploadProps = {
    accept: 'image/*',
    beforeUpload: async (file) => {
      const formData = new FormData()
      formData.append('file', file)

      try {
        const response = await apiClient.post<UploadImageResponse>('/upload/image', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        })

        const imagePath = getUploadedImagePath(response.data)
        if (!imagePath) {
          throw new Error('图片上传成功但未返回可用地址')
        }

        form.setFieldValue('image_content', imagePath)
        messageApi.success('图片上传成功')
      } catch (error) {
        messageApi.error(getErrorMessage(error, '图片上传失败'))
      }

      return Upload.LIST_IGNORE
    },
    maxCount: 1,
    showUploadList: false,
  }

  const openAddModal = () => {
    setEditingCard(null)
    setActiveType('text')
    form.setFieldsValue({
      account_id: selectedAccountId,
      data_content: '',
      image_content: '',
      name: '',
      text_content: '',
    })
    setIsModalOpen(true)
  }

  const openEditModal = (card: CardRecord) => {
    setEditingCard(card)
    setActiveType(card.content_type)
    form.setFieldsValue(buildFormValues(card))
    setIsModalOpen(true)
  }

  const handleTypeChange = (key: string) => {
    setActiveType(key as CardContentType)
  }

  const submitForm = async () => {
    const values = await form.validateFields()
    const payload = {
      account_id: values.account_id,
      content: buildCardContent(values, activeType),
      content_type: activeType,
      name: values.name.trim(),
    }

    if (editingCard) {
      updateCardMutation.mutate({ ...payload, card_id: editingCard.id })
      return
    }

    createCardMutation.mutate(payload)
  }

  const columns: ColumnsType<CardRecord> = [
    {
      dataIndex: 'name',
      key: 'name',
      title: '卡券名称',
    },
    {
      dataIndex: 'content_type',
      key: 'content_type',
      title: '类型',
      width: 140,
      render: (value: CardContentType) => <Tag color="blue">{value}</Tag>,
    },
    {
      dataIndex: 'account_id',
      key: 'account_id',
      title: '账号ID',
      width: 180,
    },
    {
      dataIndex: 'created_at',
      key: 'created_at',
      title: '创建时间',
      width: 190,
      render: (value?: string | null) => value || '-',
    },
    {
      key: 'actions',
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space size="small">
          <Button onClick={() => openEditModal(record)} size="small" type="link">
            编辑
          </Button>
          <Popconfirm
            cancelText="取消"
            okText="确认"
            title="确认删除该卡券吗？"
            onConfirm={() => deleteCardMutation.mutate(record.id)}
          >
            <Button danger size="small" type="link">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      {contextHolder}
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Card>
          <Statistic title="卡券总数" value={cardsQuery.data?.length ?? 0} />
        </Card>

        <Card
          title="卡券管理"
          extra={
            <Space wrap>
              <Select
                allowClear
                loading={accountsQuery.isLoading}
                onChange={(value) => setSelectedAccountId(value ?? '')}
                options={accountOptions}
                placeholder="选择账号"
                style={{ width: 240 }}
                value={selectedAccountId || undefined}
              />
              <Button onClick={openAddModal} type="primary">
                新增卡券
              </Button>
            </Space>
          }
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Typography.Text type="secondary">按账号筛选卡券，并支持文本、批量数据、API、图片、易凡配置五种类型。</Typography.Text>
            <Table<CardRecord>
              columns={columns}
              dataSource={cardsQuery.data ?? []}
              loading={cardsQuery.isLoading || cardsQuery.isFetching}
              pagination={false}
              rowKey="id"
              scroll={{ x: 920 }}
            />
          </Space>
        </Card>
      </Space>

      <Modal
        destroyOnHidden
        cancelText="取消"
        confirmLoading={createCardMutation.isPending || updateCardMutation.isPending}
        okText={editingCard ? '保存' : '新增'}
        open={isModalOpen}
        title={editingCard ? '编辑卡券' : '新增卡券'}
        onCancel={closeModal}
        onOk={() => {
          void submitForm()
        }}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="卡券名称" name="name" rules={[{ message: '请输入卡券名称', required: true }]}>
            <Input />
          </Form.Item>

          <Form.Item label="账号ID" name="account_id" rules={[{ message: '请选择账号', required: true }]}>
            <Select options={accountOptions} placeholder="选择账号" />
          </Form.Item>

          <Tabs
            activeKey={activeType}
            animated={false}
            items={CARD_TYPE_TABS.map((item) => ({ key: item.key, label: item.label }))}
            onChange={handleTypeChange}
          />

          {activeType === 'text' && (
            <Form.Item label="文本内容" name="text_content" rules={[{ message: '请输入文本内容', required: true }]}>
              <Input.TextArea rows={5} />
            </Form.Item>
          )}

          {activeType === 'data' && (
            <Form.Item label="批量数据" name="data_content" rules={[{ message: '请输入批量数据', required: true }]}>
              <Input.TextArea placeholder="每行一条数据" rows={6} />
            </Form.Item>
          )}

          {activeType === 'api' && (
            <>
              <Form.Item label="API URL" name="api_url" rules={[{ message: '请输入 API URL', required: true }]}>
                <Input placeholder="https://example.com/deliver" />
              </Form.Item>
              <Form.Item label="API Key" name="api_key">
                <Input placeholder="可选" />
              </Form.Item>
            </>
          )}

          {activeType === 'image' && (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Form.Item label="图片地址" name="image_content" rules={[{ message: '请先上传图片', required: true }]}>
                <Input placeholder="上传后自动填充" readOnly />
              </Form.Item>
              <Upload {...uploadProps}>
                <Button>上传图片</Button>
              </Upload>
            </Space>
          )}

          {activeType === 'yifan' && (
            <>
              <Form.Item label="回调地址" name="callback_url" rules={[{ message: '请输入回调地址', required: true }]}>
                <Input placeholder="https://vendor.example.com/callback" />
              </Form.Item>
              <Form.Item label="商户号" name="merchant_id" rules={[{ message: '请输入商户号', required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item label="应用密钥" name="app_key">
                <Input />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </>
  )
}
