import { useCallback, useMemo, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
  message,
} from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { apiClient } from '../api/client'
import { useSSE } from '../hooks/useSSE'

type AccountOption = {
  account_id: string
  username?: string
}

type AccountsResponse = AccountOption[] | { accounts?: AccountOption[]; data?: AccountOption[] }

type OrderRecord = {
  id: number
  order_id: string
  item_id: string
  buyer_id: string
  status: string
  amount: string | number
  account_id: string
  created_at?: string | null
  updated_at?: string | null
}

type OrdersResponse = {
  orders: OrderRecord[]
  total: number
  page: number
  page_size: number
}

const PAGE_SIZE = 20

const STATUS_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: 'pending', value: 'pending' },
  { label: 'paid', value: 'paid' },
  { label: 'completed', value: 'completed' },
  { label: 'cancelled', value: 'cancelled' },
]

function normalizeAccounts(payload: AccountsResponse | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  return payload?.accounts ?? payload?.data ?? []
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

function getBadgeStatus(status: string) {
  switch (status) {
    case 'completed':
      return 'success'
    case 'paid':
      return 'processing'
    case 'pending':
      return 'warning'
    case 'cancelled':
      return 'default'
    default:
      return 'processing'
  }
}

export default function OrdersPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('')
  const [page, setPage] = useState(1)
  const [selectedOrders, setSelectedOrders] = useState<OrderRecord[]>([])

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const response = await apiClient.get<AccountsResponse>('/accounts')
      return normalizeAccounts(response.data)
    },
    retry: false,
  })

  const ordersQuery = useQuery({
    queryKey: ['orders', selectedAccountId, selectedStatus, page],
    queryFn: async () => {
      const response = await apiClient.get<OrdersResponse>('/orders', {
        params: {
          account_id: selectedAccountId,
          status: selectedStatus,
          page,
          page_size: PAGE_SIZE,
        },
      })

      return response.data
    },
    placeholderData: (previousData) => previousData,
    retry: false,
  })

  const refreshOrders = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['orders'] })
  }, [queryClient])

  useSSE(
    '/api/orders/stream',
    useCallback(() => {
      void refreshOrders()
    }, [refreshOrders]),
  )

  const refreshOrderMutation = useMutation({
    mutationFn: async (orderId: string) => {
      await apiClient.post(`/orders/${orderId}/refresh`)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '刷新订单失败'))
    },
    onSuccess: async () => {
      messageApi.success('订单刷新已触发')
      await refreshOrders()
    },
  })

  const deleteOrdersMutation = useMutation({
    mutationFn: async (payload: { account_id: string; order_ids: string[] }) => {
      await apiClient.delete('/orders', {
        data: payload,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '删除订单失败'))
    },
    onSuccess: async (_, variables) => {
      messageApi.success(variables.order_ids.length > 1 ? '批量删除成功' : '订单已删除')
      setSelectedOrders([])
      await refreshOrders()
    },
  })

  const accountOptions = useMemo(
    () => [
      { label: '全部账号', value: '' },
      ...((accountsQuery.data ?? []).map((account) => ({
        label: account.username ? `${account.username} (${account.account_id})` : account.account_id,
        value: account.account_id,
      })) ?? []),
    ],
    [accountsQuery.data],
  )

  const selectedRowKeys = useMemo(() => selectedOrders.map((order) => order.order_id), [selectedOrders])

  const batchDeleteAccountId = useMemo(() => {
    if (selectedAccountId) {
      return selectedAccountId
    }

    const uniqueAccountIds = Array.from(new Set(selectedOrders.map((order) => order.account_id).filter(Boolean)))
    return uniqueAccountIds.length === 1 ? uniqueAccountIds[0] : ''
  }, [selectedAccountId, selectedOrders])

  const handleAccountChange = (value: string) => {
    setSelectedAccountId(value)
    setSelectedOrders([])
    setPage(1)
  }

  const handleStatusChange = (value: string) => {
    setSelectedStatus(value)
    setSelectedOrders([])
    setPage(1)
  }

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  const handleBatchDelete = () => {
    if (!batchDeleteAccountId) {
      messageApi.error('请先选择同一账号下的订单后再删除')
      return
    }

    deleteOrdersMutation.mutate({
      account_id: batchDeleteAccountId,
      order_ids: selectedOrders.map((order) => order.order_id),
    })
  }

  const columns: ColumnsType<OrderRecord> = [
    {
      dataIndex: 'order_id',
      key: 'order_id',
      title: '订单ID',
      width: 180,
    },
    {
      dataIndex: 'item_id',
      key: 'item_id',
      title: '商品ID',
      width: 180,
    },
    {
      dataIndex: 'buyer_id',
      key: 'buyer_id',
      title: '买家ID',
      width: 180,
    },
    {
      dataIndex: 'status',
      key: 'status',
      title: '状态',
      width: 140,
      render: (value: string) => <Badge status={getBadgeStatus(value)} text={value} />,
    },
    {
      dataIndex: 'amount',
      key: 'amount',
      title: '金额',
      width: 120,
      render: (value: OrderRecord['amount']) => String(value),
    },
    {
      dataIndex: 'account_id',
      key: 'account_id',
      title: '账号ID',
      width: 160,
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
      width: 120,
      render: (_, record) => (
        <Button
          loading={refreshOrderMutation.isPending && refreshOrderMutation.variables === record.order_id}
          onClick={() => refreshOrderMutation.mutate(record.order_id)}
          size="small"
          type="link"
        >
          刷新
        </Button>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      {contextHolder}

      <div>
        <Typography.Title level={3} style={{ marginBottom: 8, marginTop: 0 }}>
          订单管理
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          实时查看订单状态，支持按账号和状态筛选、单条刷新与批量删除。
        </Typography.Paragraph>
      </div>

      {accountsQuery.isError ? (
        <Alert message="账号列表加载失败" showIcon type="error" description={getErrorMessage(accountsQuery.error, '请稍后重试')} />
      ) : null}

      {ordersQuery.isError ? (
        <Alert message="订单数据加载失败" showIcon type="error" description={getErrorMessage(ordersQuery.error, '请稍后重试')} />
      ) : null}

      <Card
        extra={
          <Space wrap>
            <Select
              aria-label="账号筛选"
              loading={accountsQuery.isLoading}
              onChange={(value) => handleAccountChange(value ?? '')}
              options={accountOptions}
              style={{ width: 240 }}
              value={selectedAccountId}
            />
            <Select
              aria-label="订单状态"
              onChange={(value) => handleStatusChange(value ?? '')}
              options={STATUS_OPTIONS}
              style={{ width: 180 }}
              value={selectedStatus}
            />
            <Popconfirm
              cancelText="取消"
              disabled={selectedOrders.length === 0}
              okText="确认"
              onConfirm={handleBatchDelete}
              title="确认批量删除选中的订单吗？"
            >
              <Button disabled={selectedOrders.length === 0} loading={deleteOrdersMutation.isPending}>
                批量删除
              </Button>
            </Popconfirm>
          </Space>
        }
        title="订单列表"
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text type="secondary">共 {ordersQuery.data?.total ?? 0} 条订单，已启用实时更新。</Typography.Text>
          <Table<OrderRecord>
            columns={columns}
            dataSource={ordersQuery.data?.orders ?? []}
            loading={ordersQuery.isLoading || ordersQuery.isFetching}
            locale={{
              emptyText: <Empty description="暂无订单" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
            }}
            onChange={handleTableChange}
            pagination={{
              current: ordersQuery.data?.page ?? page,
              pageSize: ordersQuery.data?.page_size ?? PAGE_SIZE,
              total: ordersQuery.data?.total ?? 0,
            }}
            rowKey="order_id"
            rowSelection={{
              onChange: (_, selectedRows) => setSelectedOrders(selectedRows),
              selectedRowKeys,
            }}
            scroll={{ x: 1180 }}
          />
        </Space>
      </Card>
    </Space>
  )
}
