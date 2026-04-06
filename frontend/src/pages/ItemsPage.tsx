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
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { apiClient } from '../api/client'

type AccountOption = {
  account_id: string
  username?: string
}

type AccountsResponse = AccountOption[] | { accounts?: AccountOption[]; data?: AccountOption[] }

type ItemRecord = {
  id: number
  item_id: string
  title: string
  price: number | string
  status: string
  raw_data?: unknown
  account_id: string
  created_at?: string | null
  updated_at?: string | null
}

type ItemsResponse = {
  items: ItemRecord[]
  total: number
  page: number
  page_size: number
}

type EditItemFormValues = {
  title: string
  price: number
  status: string
}

const PAGE_SIZE = 20

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

export default function ItemsPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [searchText, setSearchText] = useState('')
  const [queryText, setQueryText] = useState('')
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [page, setPage] = useState(1)
  const [selectedItems, setSelectedItems] = useState<ItemRecord[]>([])
  const [editingItem, setEditingItem] = useState<ItemRecord | null>(null)
  const [editForm] = Form.useForm<EditItemFormValues>()

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const response = await apiClient.get<AccountsResponse>('/accounts')
      return normalizeAccounts(response.data)
    },
    retry: false,
  })

  const itemsQuery = useQuery({
    queryKey: ['items', selectedAccountId, queryText, page],
    queryFn: async () => {
      const response = await apiClient.get<ItemsResponse>('/items', {
        params: {
          account_id: selectedAccountId,
          q: queryText,
          page,
          page_size: PAGE_SIZE,
        },
      })

      return response.data
    },
    placeholderData: (previousData) => previousData,
    retry: false,
  })

  const refreshItems = async () => {
    await queryClient.invalidateQueries({ queryKey: ['items'] })
  }

  const closeEditModal = () => {
    setEditingItem(null)
    editForm.resetFields()
  }

  const syncMutation = useMutation({
    mutationFn: async (accountId: string) => {
      const response = await apiClient.post<{ message?: string }>('/items/sync', {
        account_id: accountId,
      })

      return response.data
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '商品同步失败'))
    },
    onSuccess: async (payload) => {
      messageApi.success(payload.message ?? '商品同步已开始')
      await refreshItems()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (payload: { account_id: string; item_ids: string[] }) => {
      await apiClient.delete('/items', {
        data: payload,
      })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '删除商品失败'))
    },
    onSuccess: async (_, variables) => {
      messageApi.success(variables.item_ids.length > 1 ? '批量删除成功' : '商品已删除')
      setSelectedItems((current) => current.filter((item) => !variables.item_ids.includes(item.item_id)))
      await refreshItems()
    },
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { account_id: string; item_id: string; values: EditItemFormValues }) => {
      await apiClient.put(`/items/${payload.account_id}/${payload.item_id}`, payload.values)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '更新商品失败'))
    },
    onSuccess: async () => {
      messageApi.success('商品已更新')
      closeEditModal()
      await refreshItems()
    },
  })

  const accountOptions = useMemo(
    () =>
      (accountsQuery.data ?? []).map((account) => ({
        label: account.username ? `${account.username} (${account.account_id})` : account.account_id,
        value: account.account_id,
      })),
    [accountsQuery.data],
  )

  const selectedRowKeys = useMemo(() => selectedItems.map((item) => item.item_id), [selectedItems])

  const batchDeleteAccountId = useMemo(() => {
    if (selectedAccountId) {
      return selectedAccountId
    }

    const uniqueAccountIds = Array.from(new Set(selectedItems.map((item) => item.account_id).filter(Boolean)))
    return uniqueAccountIds.length === 1 ? uniqueAccountIds[0] : ''
  }, [selectedAccountId, selectedItems])

  const handleSearch = () => {
    setPage(1)
    setQueryText(searchText.trim())
  }

  const handleAccountChange = (value: string) => {
    setSelectedAccountId(value)
    setSelectedItems([])
    setPage(1)
  }

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  const openEditModal = (item: ItemRecord) => {
    setEditingItem(item)
    editForm.setFieldsValue({
      title: item.title,
      price: Number(item.price),
      status: item.status,
    })
  }

  const handleDeleteItems = (items: ItemRecord[]) => {
    const accountIds = Array.from(new Set(items.map((item) => item.account_id).filter(Boolean)))

    if (accountIds.length !== 1) {
      messageApi.error('请选择同一账号下的商品后再删除')
      return
    }

    deleteMutation.mutate({
      account_id: accountIds[0],
      item_ids: items.map((item) => item.item_id),
    })
  }

  const columns: ColumnsType<ItemRecord> = [
    {
      dataIndex: 'item_id',
      key: 'item_id',
      title: '商品ID',
      width: 180,
    },
    {
      dataIndex: 'title',
      key: 'title',
      title: '标题',
    },
    {
      dataIndex: 'price',
      key: 'price',
      title: '价格',
      width: 120,
      render: (value: ItemRecord['price']) => String(value),
    },
    {
      dataIndex: 'status',
      key: 'status',
      title: '状态',
      width: 120,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    {
      dataIndex: 'account_id',
      key: 'account_id',
      title: '账号ID',
      width: 160,
    },
    {
      dataIndex: 'updated_at',
      key: 'updated_at',
      title: '更新时间',
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
            okText="确认"
            title="确认删除该商品吗？"
            cancelText="取消"
            onConfirm={() => handleDeleteItems([record])}
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
      <Card
        title="商品管理"
        extra={
          <Space wrap>
            <Select
              allowClear
              loading={accountsQuery.isLoading}
              onChange={(value) => handleAccountChange(value ?? '')}
              options={accountOptions}
              placeholder="选择账号"
              style={{ width: 240 }}
              value={selectedAccountId || undefined}
            />
            <Input
              allowClear
              onChange={(event) => setSearchText(event.target.value)}
              onPressEnter={handleSearch}
              placeholder="搜索商品标题或商品ID"
              style={{ width: 240 }}
              value={searchText}
            />
            <Button onClick={handleSearch} type="primary">
              搜索
            </Button>
            <Button
              disabled={!selectedAccountId}
              loading={syncMutation.isPending}
              onClick={() => syncMutation.mutate(selectedAccountId)}
            >
              同步商品
            </Button>
            <Popconfirm
              okText="确认"
              title="确认批量删除选中的商品吗？"
              cancelText="取消"
              disabled={selectedItems.length === 0}
              onConfirm={() => {
                if (!batchDeleteAccountId) {
                  messageApi.error('请先选择账号或勾选同一账号下的商品')
                  return
                }

                deleteMutation.mutate({
                  account_id: batchDeleteAccountId,
                  item_ids: selectedItems.map((item) => item.item_id),
                })
              }}
            >
              <Button disabled={selectedItems.length === 0} loading={deleteMutation.isPending}>
                批量删除
              </Button>
            </Popconfirm>
          </Space>
        }
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text type="secondary">
            共 {itemsQuery.data?.total ?? 0} 条商品，支持按账号与关键字筛选。
          </Typography.Text>
          <Table<ItemRecord>
            columns={columns}
            dataSource={itemsQuery.data?.items ?? []}
            loading={itemsQuery.isLoading || itemsQuery.isFetching}
            onChange={handleTableChange}
            pagination={{
              current: itemsQuery.data?.page ?? page,
              pageSize: itemsQuery.data?.page_size ?? PAGE_SIZE,
              total: itemsQuery.data?.total ?? 0,
            }}
            rowKey="item_id"
            rowSelection={{
              onChange: (_, selectedRows) => setSelectedItems(selectedRows),
              selectedRowKeys,
            }}
            scroll={{ x: 980 }}
          />
        </Space>
      </Card>

      <Modal
        destroyOnHidden
        okText="保存"
        open={Boolean(editingItem)}
        title={editingItem ? `编辑商品：${editingItem.item_id}` : '编辑商品'}
        cancelText="取消"
        confirmLoading={updateMutation.isPending}
        onCancel={closeEditModal}
        onOk={() => {
          void editForm.validateFields().then((values) => {
            if (!editingItem) {
              return
            }

            updateMutation.mutate({
              account_id: editingItem.account_id,
              item_id: editingItem.item_id,
              values,
            })
          })
        }}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入商品标题' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="价格" name="price" rules={[{ required: true, message: '请输入商品价格' }]}>
            <InputNumber min={0} precision={2} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="状态" name="status" rules={[{ required: true, message: '请选择商品状态' }]}>
            <Select
              options={[
                { label: 'online', value: 'online' },
                { label: 'offline', value: 'offline' },
                { label: 'sold', value: 'sold' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
