import { useMemo, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { apiClient } from '../api/client'

type AccountOption = {
  account_id: string
  username?: string
}

type AccountsResponse = AccountOption[] | { accounts?: AccountOption[]; data?: AccountOption[] }

type CardRecord = {
  account_id: string
  content_type: string
  id: number
  name: string
}

type CardsResponse = CardRecord[] | { cards?: CardRecord[]; data?: CardRecord[] }

type DeliveryRuleRecord = {
  account_id: string
  card_id: number
  card_name?: string | null
  content_type?: string | null
  enabled: boolean | number
  id: number
  item_id: string
  priority: number
}

type DeliveryRulesResponse = DeliveryRuleRecord[] | { rules?: DeliveryRuleRecord[]; data?: DeliveryRuleRecord[] }

type DeliveryLogRecord = {
  card_id: number
  created_at?: string | null
  id?: number
  order_id: string
  status: string
}

type DeliveryLogsResponse = DeliveryLogRecord[] | { logs?: DeliveryLogRecord[]; data?: DeliveryLogRecord[] }

type RuleFormValues = {
  card_id: number
  enabled: boolean
  item_id: string
  priority: number
}

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

function normalizeRules(payload: DeliveryRulesResponse | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  return payload?.rules ?? payload?.data ?? []
}

function normalizeLogs(payload: DeliveryLogsResponse | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  return payload?.logs ?? payload?.data ?? []
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

export default function DeliveryPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [editingRule, setEditingRule] = useState<DeliveryRuleRecord | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form] = Form.useForm<RuleFormValues>()

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const response = await apiClient.get<AccountsResponse>('/accounts')
      return normalizeAccounts(response.data)
    },
    retry: false,
  })

  const cardsQuery = useQuery({
    queryKey: ['delivery-cards', (accountsQuery.data ?? []).map((account) => account.account_id).join(',')],
    queryFn: async () => {
      const accountIds = (accountsQuery.data ?? []).map((account) => account.account_id)
      const responses = await Promise.all(
        accountIds.map((accountId) =>
          apiClient.get<CardsResponse>('/cards', {
            params: { account_id: accountId },
          }),
        ),
      )

      const flattened = responses.flatMap((response) => normalizeCards(response.data))
      const uniqueCards = new Map<number, CardRecord>()
      flattened.forEach((card) => {
        uniqueCards.set(card.id, card)
      })
      return Array.from(uniqueCards.values())
    },
    enabled: Boolean(accountsQuery.data?.length),
    retry: false,
  })

  const rulesQuery = useQuery({
    queryKey: ['delivery-rules'],
    queryFn: async () => {
      const response = await apiClient.get<DeliveryRulesResponse>('/delivery/rules')
      return normalizeRules(response.data)
    },
    retry: false,
  })

  const logsQuery = useQuery({
    queryKey: ['delivery-logs', 'recent'],
    queryFn: async () => {
      const response = await apiClient.get<DeliveryLogsResponse>('/delivery/logs/recent')
      return normalizeLogs(response.data)
    },
    retry: false,
  })

  const cardsById = useMemo(() => new Map((cardsQuery.data ?? []).map((card) => [card.id, card])), [cardsQuery.data])

  const cardOptions = useMemo(
    () =>
      (cardsQuery.data ?? []).map((card) => ({
        label: `${card.name} (${card.account_id})`,
        value: card.id,
      })),
    [cardsQuery.data],
  )

  const enabledRulesCount = useMemo(
    () => (rulesQuery.data ?? []).filter((rule) => Boolean(rule.enabled)).length,
    [rulesQuery.data],
  )

  const refreshRules = async () => {
    await queryClient.invalidateQueries({ queryKey: ['delivery-rules'] })
  }

  const closeModal = () => {
    setEditingRule(null)
    setIsModalOpen(false)
    form.resetFields()
  }

  const createRuleMutation = useMutation({
    mutationFn: async (values: RuleFormValues) => {
      const selectedCard = cardsById.get(values.card_id)
      if (!selectedCard) {
        throw new Error('请选择有效的卡券')
      }

      await apiClient.post('/delivery/rules', {
        account_id: selectedCard.account_id,
        card_id: values.card_id,
        enabled: values.enabled,
        item_id: values.item_id.trim(),
        priority: values.priority,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '新增发货规则失败'))
    },
    onSuccess: async () => {
      messageApi.success('发货规则已新增')
      closeModal()
      await refreshRules()
    },
  })

  const updateRuleMutation = useMutation({
    mutationFn: async (payload: { ruleId: number; values: RuleFormValues }) => {
      await apiClient.put(`/delivery/rules/${payload.ruleId}`, {
        card_id: payload.values.card_id,
        enabled: payload.values.enabled,
        priority: payload.values.priority,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '更新发货规则失败'))
    },
    onSuccess: async () => {
      messageApi.success('发货规则已更新')
      closeModal()
      await refreshRules()
    },
  })

  const deleteRuleMutation = useMutation({
    mutationFn: async (ruleId: number) => {
      await apiClient.delete(`/delivery/rules/${ruleId}`)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '删除发货规则失败'))
    },
    onSuccess: async () => {
      messageApi.success('发货规则已删除')
      await refreshRules()
    },
  })

  const toggleEnabledMutation = useMutation({
    mutationFn: async (rule: DeliveryRuleRecord) => {
      await apiClient.put(`/delivery/rules/${rule.id}`, {
        enabled: !Boolean(rule.enabled),
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '切换规则状态失败'))
    },
    onSuccess: async () => {
      await refreshRules()
    },
  })

  const openAddModal = () => {
    setEditingRule(null)
    form.setFieldsValue({
      enabled: true,
      item_id: '',
      priority: 0,
    })
    setIsModalOpen(true)
  }

  const openEditModal = (rule: DeliveryRuleRecord) => {
    setEditingRule(rule)
    form.setFieldsValue({
      card_id: rule.card_id,
      enabled: Boolean(rule.enabled),
      item_id: rule.item_id,
      priority: rule.priority,
    })
    setIsModalOpen(true)
  }

  const submitForm = async () => {
    const values = await form.validateFields()

    if (editingRule) {
      updateRuleMutation.mutate({
        ruleId: editingRule.id,
        values,
      })
      return
    }

    createRuleMutation.mutate(values)
  }

  const ruleColumns: ColumnsType<DeliveryRuleRecord> = [
    {
      dataIndex: 'item_id',
      key: 'item_id',
      title: '商品ID',
      width: 180,
    },
    {
      dataIndex: 'card_name',
      key: 'card_name',
      title: '卡券名称',
      render: (value?: string | null) => value || '-',
    },
    {
      dataIndex: 'priority',
      key: 'priority',
      title: '优先级',
      width: 120,
    },
    {
      dataIndex: 'enabled',
      key: 'enabled',
      title: '启用',
      width: 120,
      render: (_, record) => (
        <Switch checked={Boolean(record.enabled)} loading={toggleEnabledMutation.isPending} onChange={() => toggleEnabledMutation.mutate(record)} />
      ),
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
            title="确认删除该规则吗？"
            onConfirm={() => deleteRuleMutation.mutate(record.id)}
          >
            <Button danger size="small" type="link">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const logColumns: ColumnsType<DeliveryLogRecord> = [
    {
      dataIndex: 'order_id',
      key: 'order_id',
      title: '订单ID',
      width: 180,
    },
    {
      dataIndex: 'card_id',
      key: 'card_id',
      title: '卡券ID',
      width: 120,
    },
    {
      dataIndex: 'status',
      key: 'status',
      title: '状态',
      width: 120,
      render: (value: string) => <Tag color={value === 'success' ? 'green' : 'blue'}>{value}</Tag>,
    },
    {
      dataIndex: 'created_at',
      key: 'created_at',
      title: '创建时间',
      render: (value?: string | null) => value || '-',
    },
  ]

  return (
    <>
      {contextHolder}
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space wrap style={{ width: '100%' }}>
          <Card style={{ minWidth: 180 }}>
            <Statistic title="规则总数" value={rulesQuery.data?.length ?? 0} />
          </Card>
          <Card style={{ minWidth: 180 }}>
            <Statistic title="已启用规则" value={enabledRulesCount} />
          </Card>
          <Card style={{ minWidth: 180 }}>
            <Statistic title="最近日志数" value={logsQuery.data?.length ?? 0} />
          </Card>
        </Space>

        <Card
          title="自动发货规则"
          extra={
            <Button onClick={openAddModal} type="primary">
              新增规则
            </Button>
          }
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Typography.Text type="secondary">支持绑定商品与卡券，并按优先级控制发货命中顺序。</Typography.Text>
            <Table<DeliveryRuleRecord>
              columns={ruleColumns}
              dataSource={rulesQuery.data ?? []}
              loading={rulesQuery.isLoading || rulesQuery.isFetching}
              pagination={false}
              rowKey="id"
              scroll={{ x: 860 }}
            />
          </Space>
        </Card>

        <Card title="最近发货日志">
          <Table<DeliveryLogRecord>
            columns={logColumns}
            dataSource={logsQuery.data ?? []}
            loading={logsQuery.isLoading || logsQuery.isFetching}
            pagination={false}
            rowKey={(record) => String(record.id ?? `${record.order_id}-${record.card_id}-${record.created_at ?? ''}`)}
            scroll={{ x: 760 }}
          />
        </Card>
      </Space>

      <Modal
        destroyOnHidden
        cancelText="取消"
        confirmLoading={createRuleMutation.isPending || updateRuleMutation.isPending}
        okText={editingRule ? '保存' : '新增'}
        open={isModalOpen}
        title={editingRule ? '编辑规则' : '新增规则'}
        onCancel={closeModal}
        onOk={() => {
          void submitForm()
        }}
      >
        <Form form={form} initialValues={{ enabled: true, priority: 0 }} layout="vertical">
          <Form.Item label="商品ID" name="item_id" rules={[{ message: '请输入商品ID', required: true }]}>
            <Input disabled={Boolean(editingRule)} />
          </Form.Item>
          <Form.Item label="卡券" name="card_id" rules={[{ message: '请选择卡券', required: true }]}>
            <Select loading={accountsQuery.isLoading || cardsQuery.isLoading} options={cardOptions} placeholder="选择卡券" />
          </Form.Item>
          <Form.Item label="优先级" name="priority" rules={[{ message: '请输入优先级', required: true }]}>
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="启用状态" name="enabled" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
