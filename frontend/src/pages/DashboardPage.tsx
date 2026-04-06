import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, Col, Empty, Row, Skeleton, Space, Statistic, Table, Tag, Typography, theme as antdTheme } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { apiClient } from '../api/client'

type SalesSummary = {
  today_amount: string
  today_orders: number
  total_amount: string
  total_orders: number
}

type SalesTrendPoint = {
  date: string
  amount: string
  count: number
}

type DeliveryLog = {
  id: number
  order_id: string
  card_id: string
  status: string
  created_at: string
}

type DeliveryLogsResponse = {
  logs: DeliveryLog[]
}

const STAT_ITEMS = [
  { key: 'today_orders', title: '今日订单' },
  { key: 'total_orders', title: '总订单' },
  { key: 'today_amount', title: '今日成交额' },
  { key: 'total_amount', title: '累计成交额' },
] as const

function TrendChart({ data }: { data: SalesTrendPoint[] }) {
  const { token } = antdTheme.useToken()

  const { maxAmount, points } = useMemo(() => {
    const chartHeight = 180
    const chartWidth = 640
    const amounts = data.map((item) => Number(item.amount) || 0)
    const max = Math.max(...amounts, 0)

    const polylinePoints = data
      .map((item, index) => {
        const amount = Number(item.amount) || 0
        const x = data.length === 1 ? chartWidth / 2 : (index / (data.length - 1)) * chartWidth
        const y = max <= 0 ? chartHeight : chartHeight - (amount / max) * (chartHeight - 16)
        return `${x},${y}`
      })
      .join(' ')

    return {
      maxAmount: max,
      points: polylinePoints,
    }
  }, [data])

  return (
    <Space direction="vertical" size="middle" style={{ display: 'flex' }}>
      <div
        aria-label="最近 7 天销售趋势图"
        role="img"
        style={{
          background: token.colorBgLayout,
          border: `${token.lineWidth}px solid ${token.colorBorderSecondary}`,
          borderRadius: token.borderRadiusLG,
          overflow: 'hidden',
          padding: token.padding,
        }}
      >
        <svg preserveAspectRatio="none" viewBox="0 0 640 200" width="100%">
          <title>最近 7 天销售趋势图</title>
          <line stroke={token.colorBorderSecondary} strokeDasharray="4 4" x1="0" x2="640" y1="180" y2="180" />
          <line stroke={token.colorBorderSecondary} strokeDasharray="4 4" x1="0" x2="640" y1="100" y2="100" />
          <line stroke={token.colorBorderSecondary} strokeDasharray="4 4" x1="0" x2="640" y1="20" y2="20" />
          <polyline
            fill="none"
            points={points}
            stroke={token.colorPrimary}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="4"
          />
          {data.map((item, index) => {
            const amount = Number(item.amount) || 0
            const x = data.length === 1 ? 320 : (index / (data.length - 1)) * 640
            const y = maxAmount <= 0 ? 180 : 180 - (amount / maxAmount) * 164

            return (
              <g key={item.date}>
                <circle cx={x} cy={y} fill={token.colorPrimary} r="5" />
                <text
                  fill={token.colorTextSecondary}
                  fontSize="12"
                  textAnchor={index === 0 ? 'start' : index === data.length - 1 ? 'end' : 'middle'}
                  x={x}
                  y="196"
                >
                  {item.date.slice(5)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      <Row gutter={[12, 12]}>
        {data.map((item) => (
          <Col key={item.date} span={24} sm={12} xl={8}>
            <Card size="small">
              <Space direction="vertical" size={4}>
                <Typography.Text strong>{item.date}</Typography.Text>
                <Typography.Text type="secondary">成交额 {item.amount}</Typography.Text>
                <Typography.Text type="secondary">订单数 {item.count}</Typography.Text>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </Space>
  )
}

function renderStatisticValue(value: string | number) {
  return <span>{String(value)}</span>
}

export default function DashboardPage() {
  const { token } = antdTheme.useToken()

  const summaryQuery = useQuery({
    queryKey: ['sales-summary'],
    queryFn: () => apiClient.get<SalesSummary>('/sales/summary').then((response) => response.data),
  })

  const trendQuery = useQuery({
    queryKey: ['sales-trend', 7],
    queryFn: () => apiClient.get<SalesTrendPoint[]>('/sales/trend?days=7').then((response) => response.data),
  })

  const recentLogsQuery = useQuery({
    queryKey: ['delivery-recent-logs'],
    queryFn: () => apiClient.get<DeliveryLogsResponse>('/delivery/logs/recent').then((response) => response.data),
  })

  const deliveryColumns: ColumnsType<DeliveryLog> = [
    {
      dataIndex: 'order_id',
      key: 'order_id',
      title: '订单号',
    },
    {
      dataIndex: 'card_id',
      key: 'card_id',
      title: '卡密 / 卡券',
    },
    {
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => <Tag color="processing">{value}</Tag>,
      title: '状态',
    },
    {
      dataIndex: 'created_at',
      key: 'created_at',
      title: '创建时间',
    },
  ]

  const statValues = [
    summaryQuery.data?.today_orders ?? 0,
    summaryQuery.data?.total_orders ?? 0,
    summaryQuery.data?.today_amount ?? '0.00',
    summaryQuery.data?.total_amount ?? '0.00',
  ]

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: token.marginXS, marginTop: 0 }}>
          运营概览
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          聚合最近订单、销售走势与发货记录，帮助你快速掌握系统运行状态。
        </Typography.Paragraph>
      </div>

      <Row gutter={[16, 16]}>
        {STAT_ITEMS.map((item, index) => (
          <Col key={item.key} span={24} md={12} xl={6}>
            <Card>
              {summaryQuery.isLoading ? (
                <Skeleton active paragraph={{ rows: 1 }} title={false} />
              ) : (
                <Statistic formatter={renderStatisticValue} title={item.title} value={statValues[index]} />
              )}
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={24} xl={14}>
          <Card title="最近 7 天销售趋势">
            {trendQuery.isLoading ? <Skeleton active paragraph={{ rows: 6 }} /> : null}
            {!trendQuery.isLoading && (!trendQuery.data || trendQuery.data.length === 0) ? (
              <Empty description="暂无销售趋势数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : null}
            {!trendQuery.isLoading && trendQuery.data && trendQuery.data.length > 0 ? (
              <TrendChart data={trendQuery.data} />
            ) : null}
          </Card>
        </Col>

        <Col span={24} xl={10}>
          <Card title="最近发货日志">
            {recentLogsQuery.isLoading ? <Skeleton active paragraph={{ rows: 6 }} /> : null}
            {!recentLogsQuery.isLoading ? (
              <Table
                columns={deliveryColumns}
                dataSource={recentLogsQuery.data?.logs ?? []}
                locale={{
                  emptyText: <Empty description="暂无发货记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
                }}
                pagination={false}
                rowKey="id"
                size="small"
              />
            ) : null}
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
