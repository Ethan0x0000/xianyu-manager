import { useEffect, useMemo, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  Empty,
  InputNumber,
  Select,
  Space,
  Switch,
  Typography,
  message,
} from 'antd'
import { apiClient } from '../api/client'

type LogsResponse = {
  logs: string[]
}

const LEVEL_OPTIONS = [
  { label: 'ALL', value: '' },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'ERROR', value: 'ERROR' },
]

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

function getDownloadFilename(contentDisposition?: string | null) {
  if (!contentDisposition) {
    return 'xianyu-manager.log'
  }

  const match = /filename="?([^";]+)"?/i.exec(contentDisposition)
  return match?.[1] ?? 'xianyu-manager.log'
}

export default function LogsPage() {
  const [messageApi, contextHolder] = message.useMessage()
  const [level, setLevel] = useState('')
  const [limit, setLimit] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  const logsQuery = useQuery({
    queryKey: ['logs', level, limit],
    queryFn: async () => {
      const response = await apiClient.get<LogsResponse>('/logs', {
        params: {
          level,
          limit,
        },
      })

      return response.data
    },
    retry: false,
  })

  useEffect(() => {
    if (!autoRefresh) {
      return
    }

    const timer = window.setInterval(() => {
      void logsQuery.refetch()
    }, 30_000)

    return () => {
      window.clearInterval(timer)
    }
  }, [autoRefresh, logsQuery])

  const lines = useMemo(() => logsQuery.data?.logs ?? [], [logsQuery.data])

  const handleExport = async () => {
    try {
      setIsExporting(true)
      const response = await apiClient.get<Blob>('/logs/export', {
        params: {
          level,
          limit,
        },
        responseType: 'blob',
      })

      const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: 'text/plain;charset=utf-8' })
      const url = window.URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = getDownloadFilename(response.headers['content-disposition'])
      anchor.click()
      window.URL.revokeObjectURL(url)
      messageApi.success('日志导出成功')
    } catch (error) {
      messageApi.error(getErrorMessage(error, '日志导出失败'))
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      {contextHolder}

      <div>
        <Typography.Title level={3} style={{ marginBottom: 8, marginTop: 0 }}>
          日志管理
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          查看运行日志，支持按级别过滤、手动刷新、自动轮询与文本导出。
        </Typography.Paragraph>
      </div>

      {logsQuery.isError ? (
        <Alert description={getErrorMessage(logsQuery.error, '请稍后重试')} message="日志加载失败" showIcon type="error" />
      ) : null}

      <Card
        extra={
          <Space align="center" size="middle" wrap>
            <Select
              aria-label="日志级别"
              onChange={(value) => setLevel(value ?? '')}
              options={LEVEL_OPTIONS}
              style={{ width: 140 }}
              value={level}
            />
            <InputNumber
              aria-label="日志条数"
              min={1}
              onChange={(value) => setLimit(typeof value === 'number' ? value : 100)}
              style={{ width: 140 }}
              value={limit}
            />
            <Space size="small">
              <Typography.Text>自动刷新</Typography.Text>
              <Switch checked={autoRefresh} onChange={setAutoRefresh} />
            </Space>
            <Button loading={logsQuery.isFetching} onClick={() => void logsQuery.refetch()}>
              刷新
            </Button>
            <Button loading={isExporting} onClick={() => void handleExport()}>
              导出日志
            </Button>
          </Space>
        }
        title="日志查看器"
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text type="secondary">当前展示 {lines.length} 条日志。</Typography.Text>

          <div
            style={{
              background: 'rgba(0, 0, 0, 0.02)',
              border: '1px solid rgba(5, 5, 5, 0.06)',
              borderRadius: 8,
              maxHeight: 520,
              overflow: 'auto',
              padding: 16,
            }}
          >
            {lines.length > 0 ? (
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                {lines.map((line, index) => (
                  <Typography.Text code key={`${index}-${line}`} style={{ display: 'block', whiteSpace: 'pre-wrap' }}>
                    {line}
                  </Typography.Text>
                ))}
              </Space>
            ) : (
              <Empty description="暂无日志" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </div>
        </Space>
      </Card>
    </Space>
  )
}
