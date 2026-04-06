import { useMemo, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Empty, Popconfirm, Select, Space, Table, Typography, message } from 'antd'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { apiClient } from '../api/client'

type TablesResponse = {
  tables: string[]
}

type TableRow = Record<string, unknown>

type TableRowsResponse = {
  rows: TableRow[]
  total: number
  page: number
  page_size: number
  columns: string[]
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

function formatCellValue(value: unknown) {
  if (value == null) {
    return '-'
  }

  if (typeof value === 'object') {
    return JSON.stringify(value)
  }

  return String(value)
}

export default function DataManagementPage() {
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [selectedTable, setSelectedTable] = useState('')
  const [page, setPage] = useState(1)

  const tablesQuery = useQuery({
    queryKey: ['data-tables'],
    queryFn: async () => {
      const response = await apiClient.get<TablesResponse>('/data/tables')
      return response.data.tables ?? []
    },
    retry: false,
  })

  const tableRowsQuery = useQuery({
    queryKey: ['data-table', selectedTable, page],
    queryFn: async () => {
      const response = await apiClient.get<TableRowsResponse>(`/data/table/${encodeURIComponent(selectedTable)}`, {
        params: {
          page,
          page_size: PAGE_SIZE,
        },
      })

      return response.data
    },
    enabled: Boolean(selectedTable),
    placeholderData: (previousData) => previousData,
    retry: false,
  })

  const clearTableMutation = useMutation({
    mutationFn: async (tableName: string) => {
      await apiClient.delete(`/data/table/${encodeURIComponent(tableName)}`)
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error, '清空数据表失败'))
    },
    onSuccess: async () => {
      messageApi.success('数据表已清空')
      setPage(1)
      await queryClient.invalidateQueries({ queryKey: ['data-table', selectedTable] })
    },
  })

  const columns = useMemo<ColumnsType<TableRow>>(
    () =>
      (tableRowsQuery.data?.columns ?? []).map((columnName) => ({
        dataIndex: columnName,
        key: columnName,
        title: columnName,
        render: (value: unknown) => formatCellValue(value),
      })),
    [tableRowsQuery.data?.columns],
  )

  const primaryRowKey = tableRowsQuery.data?.columns?.[0] ?? 'id'

  const tableOptions = useMemo(
    () => (tablesQuery.data ?? []).map((tableName) => ({ label: tableName, value: tableName })),
    [tablesQuery.data],
  )

  const handleTableChange = (value: string) => {
    setSelectedTable(value)
    setPage(1)
  }

  const handlePaginationChange = (pagination: TablePaginationConfig) => {
    setPage(pagination.current ?? 1)
  }

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      {contextHolder}

      <div>
        <Typography.Title level={3} style={{ marginBottom: 8, marginTop: 0 }}>
          数据管理
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          浏览数据库表结构与分页记录，支持切换数据表并执行危险清空操作。
        </Typography.Paragraph>
      </div>

      {tablesQuery.isError ? (
        <Alert description={getErrorMessage(tablesQuery.error, '请稍后重试')} message="数据表列表加载失败" showIcon type="error" />
      ) : null}

      {tableRowsQuery.isError ? (
        <Alert description={getErrorMessage(tableRowsQuery.error, '请稍后重试')} message="数据表内容加载失败" showIcon type="error" />
      ) : null}

      <Card
        extra={
          <Space wrap>
            <Select
              aria-label="数据表选择"
              loading={tablesQuery.isLoading}
              onChange={(value) => handleTableChange(value ?? '')}
              options={tableOptions}
              placeholder="请选择数据表"
              style={{ width: 260 }}
              value={selectedTable || undefined}
            />
            <Popconfirm
              cancelText="取消"
              description="此操作不可撤销"
              disabled={!selectedTable}
              okButtonProps={{ danger: true }}
              okText="确认清空"
              onConfirm={() => clearTableMutation.mutate(selectedTable)}
              title={`确认清空数据表 ${selectedTable || ''} 吗？`}
            >
              <Button danger disabled={!selectedTable} loading={clearTableMutation.isPending}>
                清空数据表
              </Button>
            </Popconfirm>
          </Space>
        }
        title="数据库表浏览器"
      >
        {selectedTable ? (
          <Table<TableRow>
            columns={columns}
            dataSource={tableRowsQuery.data?.rows ?? []}
            loading={tableRowsQuery.isLoading || tableRowsQuery.isFetching}
            locale={{
              emptyText: <Empty description="当前数据表暂无记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
            }}
            onChange={handlePaginationChange}
            pagination={{
              current: tableRowsQuery.data?.page ?? page,
              pageSize: tableRowsQuery.data?.page_size ?? PAGE_SIZE,
              total: tableRowsQuery.data?.total ?? 0,
            }}
            rowKey={(record) => String(record.id ?? record[primaryRowKey] ?? JSON.stringify(record))}
            scroll={{ x: 'max-content' }}
          />
        ) : (
          <Empty description="请选择需要查看的数据表" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>
    </Space>
  )
}
