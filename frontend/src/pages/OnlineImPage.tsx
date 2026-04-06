import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, Button, Card, Empty, Space, Typography, theme as antdTheme } from 'antd'
import { LinkOutlined } from '@ant-design/icons'
import { apiClient } from '../api/client'

type AccountRecord = {
  id?: number
  account_id: string
  username?: string
  enabled?: boolean
}

type AccountsResponse = AccountRecord[] | { accounts?: AccountRecord[]; data?: AccountRecord[] }

const IM_URL = 'https://www.goofish.com/im'
function normalizeAccounts(payload: AccountsResponse | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  return payload?.accounts ?? payload?.data ?? []
}

function getAccountLabel(account: AccountRecord) {
  return account.username ? `${account.username} (${account.account_id})` : account.account_id
}

export default function OnlineImPage() {
  const { token } = antdTheme.useToken()
  const [selectedAccountId, setSelectedAccountId] = useState('')

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => {
      const response = await apiClient.get<AccountsResponse>('/accounts')
      return normalizeAccounts(response.data)
    },
    retry: false,
  })

  useEffect(() => {
    if (!accountsQuery.data?.length || selectedAccountId) {
      return
    }

    const defaultAccount = accountsQuery.data.find((account) => account.enabled !== false) ?? accountsQuery.data[0]
    setSelectedAccountId(defaultAccount.account_id)
  }, [accountsQuery.data, selectedAccountId])

  const selectedAccount = useMemo(
    () => (accountsQuery.data ?? []).find((account) => account.account_id === selectedAccountId) ?? null,
    [accountsQuery.data, selectedAccountId],
  )

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: token.marginXS, marginTop: 0 }}>
          在线客服
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          选择当前接待账号后，直接打开或内嵌查看闲鱼 IM，减少切换账号时的上下文丢失。
        </Typography.Paragraph>
      </div>

      {accountsQuery.isError ? (
        <Alert description="请稍后刷新后重试。" message="账号列表加载失败" showIcon type="error" />
      ) : null}

      <Card title="客服账号">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Typography.Text strong>选择客服账号</Typography.Text>
            <select
              aria-label="选择客服账号"
              disabled={accountsQuery.isLoading || !accountsQuery.data?.length}
              onChange={(event) => setSelectedAccountId(event.target.value)}
              style={{
                background: token.colorBgContainer,
                border: `${token.lineWidth}px solid ${token.colorBorder}`,
                borderRadius: token.borderRadius,
                color: token.colorText,
                display: 'block',
                marginTop: token.marginXS,
                minHeight: token.controlHeight,
                paddingInline: token.paddingSM,
                width: '100%',
              }}
              value={selectedAccountId}
            >
              {(accountsQuery.data ?? []).map((account) => (
                <option disabled={account.enabled === false} key={account.account_id} value={account.account_id}>
                  {getAccountLabel(account)}
                </option>
              ))}
            </select>
          </div>

          {selectedAccount ? (
            <Card size="small" type="inner" title="账号上下文">
              <Space direction="vertical" size={token.marginXS} style={{ width: '100%' }}>
                <Typography.Text strong>{`当前账号：${selectedAccount.username || '未命名账号'}（${selectedAccount.account_id}）`}</Typography.Text>
                <Typography.Text>{`账号ID：${selectedAccount.account_id}`}</Typography.Text>
                <Typography.Text>{`用户名：${selectedAccount.username || '未设置'}`}</Typography.Text>
              </Space>
            </Card>
          ) : (
            <Empty description="暂无可用账号，请先在账号管理中添加账号。" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Space>
      </Card>

      <Card title="闲鱼 IM">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text strong>
            {selectedAccount
              ? `当前账号：${selectedAccount.username || '未命名账号'}（${selectedAccount.account_id}）`
              : '当前账号：未选择'}
          </Typography.Text>

          <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
            如果内嵌页面被浏览器或闲鱼策略拦截，请直接点击“打开闲鱼IM”在新标签页继续处理消息。
          </Typography.Paragraph>

          <Space wrap>
            <Button
              icon={<LinkOutlined aria-hidden="true" />}
              onClick={() => window.open(IM_URL, '_blank', 'noopener,noreferrer')}
              type="primary"
            >
              打开闲鱼IM
            </Button>
          </Space>

          <Card size="small" type="inner" title="访问说明">
            <Typography.Text type="secondary">
              当前页面保留账号上下文与快捷入口；若闲鱼策略限制内嵌页面，请直接在新标签页完成消息处理。
            </Typography.Text>
          </Card>
        </Space>
      </Card>
    </Space>
  )
}
