import { useEffect, useMemo, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  AutoComplete,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { UploadProps } from 'antd'
import { apiClient } from '../api/client'

type KeywordRecord = {
  id: number
  pattern: string
  reply_content: string
  item_id?: string | null
  is_regex: boolean
  enabled: boolean
  scope: string
}

type DefaultReplyRecord = {
  id: number
  content: string
  enabled: boolean
  created_at?: string | null
}

type AISettingsRecord = {
  id?: number
  provider_type: string
  api_key: string
  base_url: string
  model_name: string
  system_prompt: string
  max_tokens: number
  enabled: boolean
}

type KeywordFormValues = {
  pattern: string
  reply_content: string
  is_regex: boolean
  enabled: boolean
  scope: string
  account_id?: string
  item_id?: string
}

type DefaultReplyFormValues = {
  content: string
  enabled: boolean
}

type AISettingsFormValues = {
  provider_type: string
  api_key: string
  base_url: string
  model_name: string
  system_prompt: string
  max_tokens: number
  enabled: boolean
}

type AccountOption = {
  account_id: string
  username?: string
}

type AccountsResponse = AccountOption[] | { accounts?: AccountOption[]; data?: AccountOption[] }

type ItemOption = {
  item_id: string
  title?: string
  item_title?: string
}

type ItemsResponse = {
  items: ItemOption[]
}

type KeywordImportPayload = {
  pattern: string
  reply_content: string
  item_id?: string | null
  is_regex?: boolean
  enabled?: boolean
  scope?: string
}

type KeywordExportResponse = {
  keywords?: KeywordImportPayload[]
  item_keywords?: KeywordImportPayload[]
}

type AITestResponse = {
  success: boolean
  message: string
}

const DEFAULT_AI_SETTINGS: AISettingsRecord = {
  provider_type: 'openai',
  api_key: '',
  base_url: '',
  model_name: '',
  system_prompt: '',
  max_tokens: 512,
  enabled: false,
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

function normalizeAccounts(payload: AccountsResponse | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  return payload?.accounts ?? payload?.data ?? []
}

function normalizeImportPayload(payload: KeywordExportResponse | KeywordImportPayload[] | undefined) {
  if (!payload) {
    return []
  }

  if (Array.isArray(payload)) {
    return payload
  }

  return [...(payload.keywords ?? []), ...(payload.item_keywords ?? [])]
    .filter((entry) => entry.pattern?.trim())
    .map((entry) => ({
      pattern: entry.pattern.trim(),
      reply_content: entry.reply_content?.trim() ?? '',
      item_id: entry.item_id?.trim() || undefined,
      is_regex: Boolean(entry.is_regex),
      enabled: entry.enabled ?? true,
    }))
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  window.URL.revokeObjectURL(url)
}

function buildAISettingsPayload(values: AISettingsFormValues, hasMaskedApiKey: boolean) {
  const trimmedApiKey = values.api_key.trim()
  const payload: Record<string, string | number | boolean> = {
    provider_type: values.provider_type.trim(),
    base_url: values.base_url.trim(),
    model_name: values.model_name.trim(),
    system_prompt: values.system_prompt.trim(),
    max_tokens: values.max_tokens,
    enabled: values.enabled,
  }

  if (trimmedApiKey && (!hasMaskedApiKey || trimmedApiKey !== '****')) {
    payload.api_key = trimmedApiKey
  }

  return payload
}

export default function AutoReplyPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [activeTab, setActiveTab] = useState('keywords')
  const [keywordModalOpen, setKeywordModalOpen] = useState(false)
  const [defaultReplyModalOpen, setDefaultReplyModalOpen] = useState(false)
  const [editingKeyword, setEditingKeyword] = useState<KeywordRecord | null>(null)
  const [editingDefaultReply, setEditingDefaultReply] = useState<DefaultReplyRecord | null>(null)
  const [keywordAccountId, setKeywordAccountId] = useState('')
  const [keywordScope, setKeywordScope] = useState('general')
  const [hasMaskedApiKey, setHasMaskedApiKey] = useState(false)
  const [aiTestResult, setAiTestResult] = useState<AITestResponse | null>(null)
  const [keywordForm] = Form.useForm<KeywordFormValues>()
  const [defaultReplyForm] = Form.useForm<DefaultReplyFormValues>()
  const [aiSettingsForm] = Form.useForm<AISettingsFormValues>()

  const keywordsQuery = useQuery({
    queryKey: ['reply-keywords'],
    queryFn: async () => {
      const response = await apiClient.get<KeywordRecord[]>('/replies/keywords')
      return response.data
    },
    retry: false,
  })

  const defaultRepliesQuery = useQuery({
    queryKey: ['default-replies'],
    queryFn: async () => {
      const response = await apiClient.get<DefaultReplyRecord[]>('/replies/default')
      return response.data
    },
    retry: false,
  })

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const response = await apiClient.get<AccountsResponse>('/accounts')
      return normalizeAccounts(response.data)
    },
    retry: false,
  })

  const accountItemsQuery = useQuery({
    queryKey: ['keyword-items', keywordAccountId],
    queryFn: async () => {
      const response = await apiClient.get<ItemsResponse>('/items', {
        params: {
          account_id: keywordAccountId,
          page: 1,
          page_size: 100,
          q: '',
        },
      })

      return response.data.items ?? []
    },
    enabled: Boolean(keywordAccountId),
    retry: false,
  })

  const aiSettingsQuery = useQuery({
    queryKey: ['ai-settings'],
    queryFn: async () => {
      try {
        const response = await apiClient.get<AISettingsRecord>('/ai/settings')
        return response.data
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          return DEFAULT_AI_SETTINGS
        }

        throw error
      }
    },
    retry: false,
  })

  useEffect(() => {
    if (!aiSettingsQuery.data || activeTab !== 'ai-settings') {
      return
    }

    const nextValues = {
      provider_type: aiSettingsQuery.data.provider_type || DEFAULT_AI_SETTINGS.provider_type,
      api_key: aiSettingsQuery.data.api_key || '',
      base_url: aiSettingsQuery.data.base_url || '',
      model_name: aiSettingsQuery.data.model_name || '',
      system_prompt: aiSettingsQuery.data.system_prompt || '',
      max_tokens: aiSettingsQuery.data.max_tokens || DEFAULT_AI_SETTINGS.max_tokens,
      enabled: aiSettingsQuery.data.enabled,
    }

    aiSettingsForm.setFieldsValue(nextValues)
    setHasMaskedApiKey(aiSettingsQuery.data.api_key === '****')
  }, [activeTab, aiSettingsForm, aiSettingsQuery.data])

  const accountOptions = useMemo(
    () =>
      (accountsQuery.data ?? []).map((account) => ({
        label: account.username ? `${account.username} (${account.account_id})` : account.account_id,
        value: account.account_id,
      })),
    [accountsQuery.data],
  )

  const itemOptions = useMemo(
    () =>
      (accountItemsQuery.data ?? []).map((item) => ({
        label: item.title || item.item_title ? `${item.item_id} - ${item.title || item.item_title}` : item.item_id,
        value: item.item_id,
      })),
    [accountItemsQuery.data],
  )

  const refreshKeywords = async () => {
    await queryClient.invalidateQueries({ queryKey: ['reply-keywords'] })
  }

  const refreshDefaultReplies = async () => {
    await queryClient.invalidateQueries({ queryKey: ['default-replies'] })
  }

  const refreshAISettings = async () => {
    await queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
  }

  const closeKeywordModal = () => {
    setKeywordModalOpen(false)
    setEditingKeyword(null)
    setKeywordScope('general')
    keywordForm.resetFields()
  }

  const closeDefaultReplyModal = () => {
    setDefaultReplyModalOpen(false)
    setEditingDefaultReply(null)
    defaultReplyForm.resetFields()
  }

  const createKeywordMutation = useMutation({
    mutationFn: async (values: KeywordFormValues) => {
      await apiClient.post('/replies/keywords', {
        pattern: values.pattern.trim(),
        reply_content: values.reply_content.trim(),
        item_id: values.scope === 'item' ? values.item_id?.trim() || undefined : undefined,
        is_regex: values.is_regex,
        enabled: values.enabled,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '新增关键词失败'))
    },
    onSuccess: async () => {
      messageApi.success('关键词已新增')
      closeKeywordModal()
      await refreshKeywords()
    },
  })

  const updateKeywordMutation = useMutation({
    mutationFn: async (payload: { id: number; values: KeywordFormValues }) => {
      await apiClient.put(`/replies/keywords/${payload.id}`, {
        pattern: payload.values.pattern.trim(),
        reply_content: payload.values.reply_content.trim(),
        is_regex: payload.values.is_regex,
        enabled: payload.values.enabled,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '更新关键词失败'))
    },
    onSuccess: async () => {
      messageApi.success('关键词已更新')
      closeKeywordModal()
      await refreshKeywords()
    },
  })

  const deleteKeywordMutation = useMutation({
    mutationFn: async (record: KeywordRecord) => {
      await apiClient.delete(`/replies/keywords/${record.id}`)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '删除关键词失败'))
    },
    onSuccess: async () => {
      messageApi.success('关键词已删除')
      await refreshKeywords()
    },
  })

  const importKeywordsMutation = useMutation({
    mutationFn: async (entries: KeywordImportPayload[]) => {
      await apiClient.post('/replies/keywords/import', entries)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '导入关键词失败'))
    },
    onSuccess: async () => {
      messageApi.success('关键词导入成功')
      await refreshKeywords()
    },
  })

  const createDefaultReplyMutation = useMutation({
    mutationFn: async (values: DefaultReplyFormValues) => {
      await apiClient.post('/replies/default', {
        content: values.content.trim(),
        enabled: values.enabled,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '新增默认回复失败'))
    },
    onSuccess: async () => {
      messageApi.success('默认回复已新增')
      closeDefaultReplyModal()
      await refreshDefaultReplies()
    },
  })

  const updateDefaultReplyMutation = useMutation({
    mutationFn: async (payload: { id: number; values: DefaultReplyFormValues }) => {
      await apiClient.put(`/replies/default/${payload.id}`, {
        content: payload.values.content.trim(),
        enabled: payload.values.enabled,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '更新默认回复失败'))
    },
    onSuccess: async () => {
      messageApi.success('默认回复已更新')
      closeDefaultReplyModal()
      await refreshDefaultReplies()
    },
  })

  const deleteDefaultReplyMutation = useMutation({
    mutationFn: async (record: DefaultReplyRecord) => {
      await apiClient.delete(`/replies/default/${record.id}`)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '删除默认回复失败'))
    },
    onSuccess: async () => {
      messageApi.success('默认回复已删除')
      await refreshDefaultReplies()
    },
  })

  const saveAISettingsMutation = useMutation({
    mutationFn: async (values: AISettingsFormValues) => {
      const response = await apiClient.put<AISettingsRecord>('/ai/settings', buildAISettingsPayload(values, hasMaskedApiKey))
      return response.data
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '保存 AI 设置失败'))
    },
    onSuccess: async (data) => {
      messageApi.success('AI 设置已保存')
      setAiTestResult(null)
      aiSettingsForm.setFieldsValue({ ...data, api_key: data.api_key || '' })
      setHasMaskedApiKey(data.api_key === '****')
      await refreshAISettings()
    },
  })

  const testAISettingsMutation = useMutation({
    mutationFn: async (values: AISettingsFormValues) => {
      const response = await apiClient.post<AITestResponse>('/ai/test', buildAISettingsPayload(values, hasMaskedApiKey))
      return response.data
    },
    onError: (error) => {
      const errorMessage = getErrorMessage(error, 'AI 连接测试失败')
      setAiTestResult({ success: false, message: errorMessage })
      messageApi.error(errorMessage)
    },
    onSuccess: (result) => {
      setAiTestResult(result)
      messageApi[result.success ? 'success' : 'error'](result.message)
    },
  })

  const openCreateKeywordModal = () => {
    setEditingKeyword(null)
    setKeywordScope('general')
    keywordForm.setFieldsValue({
      pattern: '',
      reply_content: '',
      is_regex: false,
      enabled: true,
      scope: 'general',
      account_id: keywordAccountId || undefined,
      item_id: undefined,
    })
    setKeywordModalOpen(true)
  }

  const openEditKeywordModal = (record: KeywordRecord) => {
    setEditingKeyword(record)
    setKeywordScope(record.item_id ? 'item' : 'general')
    keywordForm.setFieldsValue({
      pattern: record.pattern,
      reply_content: record.reply_content,
      is_regex: record.is_regex,
      enabled: record.enabled,
      scope: record.item_id ? 'item' : 'general',
      item_id: record.item_id || undefined,
      account_id: undefined,
    })
    setKeywordModalOpen(true)
  }

  const openCreateDefaultReplyModal = () => {
    setEditingDefaultReply(null)
    defaultReplyForm.setFieldsValue({
      content: '',
      enabled: true,
    })
    setDefaultReplyModalOpen(true)
  }

  const openEditDefaultReplyModal = (record: DefaultReplyRecord) => {
    setEditingDefaultReply(record)
    defaultReplyForm.setFieldsValue({
      content: record.content,
      enabled: record.enabled,
    })
    setDefaultReplyModalOpen(true)
  }

  const handleExportKeywords = async () => {
    try {
      const response = await apiClient.get<KeywordExportResponse>('/replies/keywords/export')
      downloadJson('reply-keywords.json', response.data)
      messageApi.success('关键词导出成功')
    } catch (error) {
      messageApi.error(getErrorMessage(error, '导出关键词失败'))
    }
  }

  const uploadProps: UploadProps = {
    accept: '.json,application/json',
    beforeUpload: async (file) => {
      try {
        const fileText = await file.text()
        const rawPayload = JSON.parse(fileText) as KeywordExportResponse | KeywordImportPayload[]
        const entries = normalizeImportPayload(rawPayload)

        if (!entries.length) {
          messageApi.error('导入文件中没有可用的关键词数据')
          return Upload.LIST_IGNORE
        }

        importKeywordsMutation.mutate(entries)
      } catch (error) {
        messageApi.error(getErrorMessage(error, '解析导入文件失败'))
      }

      return Upload.LIST_IGNORE
    },
    maxCount: 1,
    showUploadList: false,
  }

  const keywordColumns: ColumnsType<KeywordRecord> = [
    {
      dataIndex: 'id',
      key: 'id',
      title: 'ID',
      width: 90,
    },
    {
      dataIndex: 'pattern',
      key: 'pattern',
      title: '关键词',
      width: 180,
    },
    {
      dataIndex: 'reply_content',
      key: 'reply_content',
      title: '回复内容',
    },
    {
      dataIndex: 'is_regex',
      key: 'is_regex',
      title: '正则',
      width: 110,
      render: (value: boolean) => (value ? <Tag color="purple">是</Tag> : <Tag>否</Tag>),
    },
    {
      dataIndex: 'enabled',
      key: 'enabled',
      title: '状态',
      width: 110,
      render: (value: boolean) => (value ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
    },
    {
      dataIndex: 'scope',
      key: 'scope',
      title: '作用域',
      width: 120,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    {
      dataIndex: 'item_id',
      key: 'item_id',
      title: '商品ID',
      width: 180,
      render: (value?: string | null) => value || '-',
    },
    {
      key: 'actions',
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space size="small">
          <Button onClick={() => openEditKeywordModal(record)} size="small" type="link">
            编辑
          </Button>
          <Popconfirm
            okText="确认"
            title="确认删除该关键词吗？"
            cancelText="取消"
            onConfirm={() => deleteKeywordMutation.mutate(record)}
          >
            <Button danger size="small" type="link">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const defaultReplyColumns: ColumnsType<DefaultReplyRecord> = [
    {
      dataIndex: 'id',
      key: 'id',
      title: 'ID',
      width: 90,
    },
    {
      dataIndex: 'content',
      key: 'content',
      title: '回复内容',
    },
    {
      dataIndex: 'enabled',
      key: 'enabled',
      title: '状态',
      width: 110,
      render: (value: boolean) => (value ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
    },
    {
      dataIndex: 'created_at',
      key: 'created_at',
      title: '创建时间',
      width: 200,
      render: (value?: string | null) => value || '-',
    },
    {
      key: 'actions',
      title: '操作',
      width: 160,
      render: (_, record) => (
        <Space size="small">
          <Button onClick={() => openEditDefaultReplyModal(record)} size="small" type="link">
            编辑
          </Button>
          <Popconfirm
            okText="确认"
            title="确认删除该默认回复吗？"
            cancelText="取消"
            onConfirm={() => deleteDefaultReplyMutation.mutate(record)}
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

      <Card title="自动回复">
        <Tabs
          activeKey={activeTab}
          defaultActiveKey="keywords"
          onChange={setActiveTab}
          items={[
            {
              key: 'keywords',
              label: '关键词',
              children: (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Typography.Text type="secondary">
                    管理关键词自动回复，商品关键词可先选择账号，再从该账号商品列表中辅助填写商品 ID。
                  </Typography.Text>
                  <Space wrap>
                    <Select
                      allowClear
                      loading={accountsQuery.isLoading}
                      onChange={(value) => setKeywordAccountId(value ?? '')}
                      options={accountOptions}
                      placeholder="选择账号以辅助商品关键词配置"
                      style={{ width: 280 }}
                      value={keywordAccountId || undefined}
                    />
                    <Button onClick={openCreateKeywordModal} type="primary">
                      新增关键词
                    </Button>
                    <Upload {...uploadProps}>
                      <Button loading={importKeywordsMutation.isPending}>导入关键词</Button>
                    </Upload>
                    <Button onClick={() => void handleExportKeywords()}>导出关键词</Button>
                  </Space>
                  <Table<KeywordRecord>
                    columns={keywordColumns}
                    dataSource={keywordsQuery.data ?? []}
                    loading={keywordsQuery.isLoading || keywordsQuery.isFetching}
                    locale={{ emptyText: '暂无关键词配置' }}
                    pagination={false}
                    rowKey="id"
                  />
                </Space>
              ),
            },
            {
              key: 'default-replies',
              label: '默认回复',
              children: (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Typography.Text type="secondary">维护未命中关键词时使用的默认自动回复。</Typography.Text>
                  <Space wrap>
                    <Button onClick={openCreateDefaultReplyModal} type="primary">
                      新增默认回复
                    </Button>
                  </Space>
                  <Table<DefaultReplyRecord>
                    columns={defaultReplyColumns}
                    dataSource={defaultRepliesQuery.data ?? []}
                    loading={defaultRepliesQuery.isLoading || defaultRepliesQuery.isFetching}
                    locale={{ emptyText: '暂无默认回复配置' }}
                    pagination={false}
                    rowKey="id"
                  />
                </Space>
              ),
            },
            {
              key: 'ai-settings',
              label: 'AI设置',
              children: (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Typography.Text type="secondary">
                    配置 AI 回复服务。若已保存密钥，会以掩码形式显示；留空或保持掩码将继续使用现有密钥。
                  </Typography.Text>
                  {aiTestResult ? (
                    <Alert
                      message={aiTestResult.message}
                      showIcon
                      type={aiTestResult.success ? 'success' : 'error'}
                    />
                  ) : null}
                  <Form form={aiSettingsForm} layout="vertical">
                    <Form.Item label="服务商类型" name="provider_type" rules={[{ required: true, message: '请输入服务商类型' }]}>
                      <Input />
                    </Form.Item>
                    <Form.Item label="API Key" name="api_key">
                      <Input.Password visibilityToggle={false} />
                    </Form.Item>
                    <Form.Item label="基础地址" name="base_url">
                      <Input />
                    </Form.Item>
                    <Form.Item label="模型名称" name="model_name">
                      <Input />
                    </Form.Item>
                    <Form.Item label="系统提示词" name="system_prompt">
                      <Input.TextArea autoSize={{ minRows: 4, maxRows: 8 }} />
                    </Form.Item>
                    <Form.Item label="最大 Tokens" name="max_tokens" rules={[{ required: true, message: '请输入最大 Tokens' }]}>
                      <InputNumber min={1} precision={0} style={{ width: '100%' }} />
                    </Form.Item>
                    <Form.Item label="启用 AI 回复" name="enabled" valuePropName="checked">
                      <Switch checkedChildren="启用" unCheckedChildren="停用" />
                    </Form.Item>
                    <Space wrap>
                      <Button
                        loading={saveAISettingsMutation.isPending}
                        onClick={() => {
                          void aiSettingsForm
                            .validateFields()
                            .then((values) => {
                              saveAISettingsMutation.mutate(values)
                            })
                            .catch(() => undefined)
                        }}
                        type="primary"
                      >
                        保存设置
                      </Button>
                      <Button
                        loading={testAISettingsMutation.isPending}
                        onClick={() => {
                          void aiSettingsForm
                            .validateFields()
                            .then((values) => {
                              testAISettingsMutation.mutate(values)
                            })
                            .catch(() => undefined)
                        }}
                      >
                        测试连接
                      </Button>
                    </Space>
                  </Form>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        destroyOnHidden
        forceRender
        okText={editingKeyword ? '保存' : '新增'}
        open={keywordModalOpen}
        title={editingKeyword ? '编辑关键词' : '新增关键词'}
        cancelText="取消"
        confirmLoading={createKeywordMutation.isPending || updateKeywordMutation.isPending}
        onCancel={closeKeywordModal}
        onOk={() => {
          void keywordForm
            .validateFields()
            .then((values) => {
              if (editingKeyword) {
                updateKeywordMutation.mutate({ id: editingKeyword.id, values })
                return
              }

              createKeywordMutation.mutate(values)
            })
            .catch(() => undefined)
        }}
      >
        <Form form={keywordForm} initialValues={{ enabled: true, is_regex: false, scope: 'general' }} layout="vertical">
          <Form.Item label="关键词" name="pattern" rules={[{ required: true, message: '请输入关键词' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="回复内容" name="reply_content" rules={[{ required: true, message: '请输入回复内容' }]}>
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} />
          </Form.Item>
          <Form.Item label="作用域" name="scope">
            <Select
              disabled={Boolean(editingKeyword)}
              onChange={(value) => setKeywordScope(value)}
              options={[
                { label: '通用关键词', value: 'general' },
                { label: '商品关键词', value: 'item' },
              ]}
            />
          </Form.Item>
          {keywordScope === 'item' ? (
            <>
              <Form.Item label="账号选择" name="account_id">
                <Select
                  allowClear
                  disabled={Boolean(editingKeyword)}
                  loading={accountsQuery.isLoading}
                  onChange={(value) => setKeywordAccountId(value ?? '')}
                  options={accountOptions}
                  placeholder="选择账号以辅助加载商品列表"
                />
              </Form.Item>
              <Form.Item
                extra={
                  editingKeyword
                    ? '当前后端兼容接口不支持直接修改商品 ID，如需调整建议删除后重建。'
                    : '可直接输入商品 ID，或先选择账号后从下拉建议中选取。'
                }
                label="商品ID"
                name="item_id"
                rules={keywordScope === 'item' ? [{ required: true, message: '请输入商品ID' }] : undefined}
              >
                <AutoComplete disabled={Boolean(editingKeyword)} options={itemOptions} placeholder="请输入或选择商品ID" />
              </Form.Item>
            </>
          ) : null}
          <Form.Item label="正则匹配" name="is_regex" valuePropName="checked">
            <Switch checkedChildren="正则" unCheckedChildren="普通" />
          </Form.Item>
          <Form.Item label="启用状态" name="enabled" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        destroyOnHidden
        forceRender
        okText={editingDefaultReply ? '保存' : '新增'}
        open={defaultReplyModalOpen}
        title={editingDefaultReply ? '编辑默认回复' : '新增默认回复'}
        cancelText="取消"
        confirmLoading={createDefaultReplyMutation.isPending || updateDefaultReplyMutation.isPending}
        onCancel={closeDefaultReplyModal}
        onOk={() => {
          void defaultReplyForm
            .validateFields()
            .then((values) => {
              if (editingDefaultReply) {
                updateDefaultReplyMutation.mutate({ id: editingDefaultReply.id, values })
                return
              }

              createDefaultReplyMutation.mutate(values)
            })
            .catch(() => undefined)
        }}
      >
        <Form form={defaultReplyForm} initialValues={{ enabled: true }} layout="vertical">
          <Form.Item label="回复内容" name="content" rules={[{ required: true, message: '请输入回复内容' }]}>
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} />
          </Form.Item>
          <Form.Item label="启用状态" name="enabled" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
