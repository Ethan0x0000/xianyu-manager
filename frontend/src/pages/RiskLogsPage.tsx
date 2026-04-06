import { useMemo, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Input, Popconfirm, Space, Table, Typography, message } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { apiClient } from '../api/client'

type RiskLogRecord = {
  id: number
  account_id: string
  event_type: string
  details: string
  created_at?: string | null
}

type RiskLogsResponse = {
  logs: RiskLogRecord[]
  total: number
  page: number
  page_size: number
}

const PAGE_SIZE = 20

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

export default function RiskLogsPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [accountId, setAccountId] = useState('')
  const [page, setPage] = useState(1)

  const riskLogsQuery = useQuery({
    queryKey: ['risk-logs', accountId, page],
    queryFn: async () => {
      const response = await apiClient.get<RiskLogsResponse>('/risk-logs', {
        params: {
          account_id: accountId,
          page,
          page_size: PAGE_SIZE,
        },
      })

      return response.data
    },
    placeholderData: (previousData) => previousData,
    retry: false,
  })

  const clearMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete('/risk-logs')
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '清空风控日志失败'))
    },
    onSuccess: async () => {
      messageApi.success('风控日志已清空')
      setPage(1)
      await queryClient.invalidateQueries({ queryKey: ['risk-logs'] })
    },
  })

  const columns = useMemo<ColumnsType<RiskLogRecord>>(
    () => [
      {
        dataIndex: 'id',
        key: 'id',
        title: 'ID',
        width: 100,
      },
      {
        dataIndex: 'account_id',
        key: 'account_id',
        title: '账号ID',
        width: 180,
      },
      {
        dataIndex: 'event_type',
        key: 'event_type',
        title: '事件类型',
        width: 180,
      },
      {
        dataIndex: 'details',
        key: 'details',
        title: '详情',
      },
      {
        dataIndex: 'created_at',
        key: 'created_at',
        title: '创建时间',
        width: 200,
        render: (value?: string | null) => value || '-',
      },
    ],
    [],
  )

  const handleTableChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      {contextHolder}

      <div>
        <Typography.Title level={3} style={{ marginBottom: 8, marginTop: 0 }}>
          风控日志
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          按账号筛选并查看风控事件明细，支持危险确认后的全量清空。
        </Typography.Paragraph>
      </div>

      {riskLogsQuery.isError ? (
        <Alert description={getErrorMessage(riskLogsQuery.error, '请稍后重试')} message="风控日志加载失败" showIcon type="error" />
      ) : null}

      <Card
        extra={
          <Space wrap>
            <Input
              allowClear
              onChange={(event) => {
                setAccountId(event.target.value)
                setPage(1)
              }}
              placeholder="按账号ID筛选"
              style={{ width: 240 }}
              value={accountId}
            />
            <Popconfirm
              cancelText="取消"
              description="此操作不可撤销"
              okButtonProps={{ danger: true }}
              okText="确认清空"
              onConfirm={() => clearMutation.mutate()}
              title="确认清空全部风控日志？"
            >
              <Button danger loading={clearMutation.isPending}>
                清空全部
              </Button>
            </Popconfirm>
          </Space>
        }
        title="风控日志列表"
      >
        <Table<RiskLogRecord>
          columns={columns}
          dataSource={riskLogsQuery.data?.logs ?? []}
          loading={riskLogsQuery.isLoading || riskLogsQuery.isFetching}
          onChange={handleTableChange}
          pagination={{
            current: riskLogsQuery.data?.page ?? page,
            pageSize: riskLogsQuery.data?.page_size ?? PAGE_SIZE,
            total: riskLogsQuery.data?.total ?? 0,
          }}
          rowKey="id"
          scroll={{ x: 880 }}
        />
      </Card>
    </Space>
  )
}
