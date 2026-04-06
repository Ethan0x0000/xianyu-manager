import { useEffect, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { apiClient } from '../api/client'

type ItemReplyRecord = {
  id: number
  item_id: string
  reply_content: string
  enabled: boolean
  created_at?: string | null
}

type ReplyFormValues = {
  item_id: string
  reply_content: string
  enabled: boolean
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

export default function ItemRepliesPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [itemIdInput, setItemIdInput] = useState('')
  const [activeItemId, setActiveItemId] = useState('')
  const [editingReply, setEditingReply] = useState<ItemReplyRecord | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [form] = Form.useForm<ReplyFormValues>()

  const repliesQuery = useQuery({
    queryKey: ['item-replies', activeItemId],
    queryFn: async () => {
      const response = await apiClient.get<ItemReplyRecord[]>('/replies/item-replies', {
        params: {
          item_id: activeItemId,
        },
      })

      return response.data
    },
    enabled: Boolean(activeItemId),
    retry: false,
  })

  const invalidateReplies = async (itemId = activeItemId) => {
    if (!itemId) {
      return
    }

    await queryClient.invalidateQueries({ queryKey: ['item-replies', itemId] })
  }

  const createMutation = useMutation({
    mutationFn: async (values: ReplyFormValues) => {
      await apiClient.post('/replies/item-replies', values)
      return values.item_id
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '新增商品回复失败'))
    },
    onSuccess: async (itemId) => {
      messageApi.success('商品回复已新增')
      setActiveItemId(itemId)
      setItemIdInput(itemId)
      setIsModalOpen(false)
      form.resetFields()
      await invalidateReplies(itemId)
    },
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { id: number; values: ReplyFormValues }) => {
      await apiClient.put(`/replies/item-replies/${payload.id}`, payload.values)
      return payload.values.item_id
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '更新商品回复失败'))
    },
    onSuccess: async (itemId) => {
      messageApi.success('商品回复已更新')
      setActiveItemId(itemId)
      setItemIdInput(itemId)
      setEditingReply(null)
      setIsModalOpen(false)
      form.resetFields()
      await invalidateReplies(itemId)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (reply: ItemReplyRecord) => {
      await apiClient.delete(`/replies/item-replies/${reply.id}`)
      return reply.item_id
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '删除商品回复失败'))
    },
    onSuccess: async (itemId) => {
      messageApi.success('商品回复已删除')
      await invalidateReplies(itemId)
    },
  })

  useEffect(() => {
    if (!isModalOpen) {
      setEditingReply(null)
    }
  }, [isModalOpen])

  const openCreateModal = () => {
    setEditingReply(null)
    setIsModalOpen(true)
    form.setFieldsValue({
      enabled: true,
      item_id: activeItemId || itemIdInput,
      reply_content: '',
    })
  }

  const openEditModal = (reply: ItemReplyRecord) => {
    setEditingReply(reply)
    setIsModalOpen(true)
    form.setFieldsValue({
      item_id: reply.item_id,
      reply_content: reply.reply_content,
      enabled: reply.enabled,
    })
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingReply(null)
    form.resetFields()
  }

  const columns: ColumnsType<ItemReplyRecord> = [
    {
      dataIndex: 'item_id',
      key: 'item_id',
      title: '商品ID',
      width: 180,
    },
    {
      dataIndex: 'reply_content',
      key: 'reply_content',
      title: '回复内容',
    },
    {
      dataIndex: 'enabled',
      key: 'enabled',
      title: '状态',
      width: 120,
      render: (enabled: boolean) => (enabled ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
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
            title="确认删除该条商品回复吗？"
            cancelText="取消"
            onConfirm={() => deleteMutation.mutate(record)}
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
        title="商品回复"
        extra={
          <Space wrap>
            <Input
              allowClear
              onChange={(event) => setItemIdInput(event.target.value)}
              onPressEnter={() => setActiveItemId(itemIdInput.trim())}
              placeholder="请输入商品ID"
              style={{ width: 240 }}
              value={itemIdInput}
            />
            <Button onClick={() => setActiveItemId(itemIdInput.trim())} type="primary">
              查询回复
            </Button>
            <Button onClick={openCreateModal}>新增回复</Button>
          </Space>
        }
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text type="secondary">
            先输入商品 ID，再维护该商品的专属自动回复。
          </Typography.Text>
          {activeItemId ? (
            <Table<ItemReplyRecord>
              columns={columns}
              dataSource={repliesQuery.data ?? []}
              loading={repliesQuery.isLoading || repliesQuery.isFetching}
              locale={{ emptyText: <Empty description="当前商品暂无专属回复" /> }}
              pagination={false}
              rowKey="id"
            />
          ) : (
            <Empty description="请输入商品 ID 后查询商品回复" />
          )}
        </Space>
      </Card>

      <Modal
        destroyOnHidden
        okText={editingReply ? '保存' : '新增'}
        open={isModalOpen}
        title={editingReply ? '编辑商品回复' : '新增商品回复'}
        cancelText="取消"
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        onCancel={closeModal}
        onOk={() => {
          void form.validateFields().then((values) => {
            const payload = {
              ...values,
              item_id: values.item_id.trim(),
              reply_content: values.reply_content.trim(),
            }

            if (editingReply) {
              updateMutation.mutate({ id: editingReply.id, values: payload })
              return
            }

            createMutation.mutate(payload)
          })
        }}
      >
        <Form form={form} initialValues={{ enabled: true }} layout="vertical">
          <Form.Item label="商品ID" name="item_id" rules={[{ required: true, message: '请输入商品ID' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="回复内容" name="reply_content" rules={[{ required: true, message: '请输入回复内容' }]}>
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
