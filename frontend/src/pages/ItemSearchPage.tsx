import { useEffect, useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Progress,
  Space,
  Tag,
  Typography,
  theme as antdTheme,
} from 'antd'
import { apiClient } from '../api/client'

type SearchFormValues = {
  keyword: string
  pageCount: number
}

type CaptchaStartResponse = {
  session_id: string
}

type CaptchaStatusResponse = {
  active?: boolean
}

type SearchItem = {
  id?: number | string
  item_id?: string
  title?: string
  price?: number | string
  account_id?: string
  status?: string
}

type SearchResponse =
  | SearchItem[]
  | {
      items?: SearchItem[]
      data?: SearchItem[]
      total?: number
      need_captcha?: boolean
    }

type SearchResultState = {
  captchaRequired: boolean
  items: SearchItem[]
  sessionId: string
  total: number
}

const SEARCH_PROGRESS_DURATION = 400

function normalizeSearchItems(payload: SearchResponse | undefined) {
  if (Array.isArray(payload)) {
    return payload
  }

  return payload?.items ?? payload?.data ?? []
}

function normalizeSearchTotal(payload: SearchResponse | undefined, items: SearchItem[]) {
  if (Array.isArray(payload)) {
    return payload.length
  }

  return payload?.total ?? items.length
}

function needsCaptcha(payload: SearchResponse | undefined) {
  if (Array.isArray(payload)) {
    return false
  }

  return Boolean(payload?.need_captcha)
}

export default function ItemSearchPage() {
  const { token } = antdTheme.useToken()
  const [form] = Form.useForm<SearchFormValues>()
  const [searching, setSearching] = useState(false)
  const [currentPage, setCurrentPage] = useState(0)
  const [targetPageCount, setTargetPageCount] = useState(0)
  const [captchaRequired, setCaptchaRequired] = useState(false)
  const [captchaSessionId, setCaptchaSessionId] = useState('')
  const [results, setResults] = useState<SearchItem[]>([])
  const [resultTotal, setResultTotal] = useState(0)
  const [errorMessage, setErrorMessage] = useState('')
  const [pendingResult, setPendingResult] = useState<SearchResultState | null>(null)

  const progressPercent = useMemo(() => {
    if (!targetPageCount) {
      return 0
    }

    return Math.round((Math.min(currentPage, targetPageCount) / targetPageCount) * 100)
  }, [currentPage, targetPageCount])

  const searchMutation = useMutation({
    mutationFn: async (values: SearchFormValues) => {
      const captchaResponse = await apiClient.post<CaptchaStartResponse>('/captcha/start')
      const searchResponse = await apiClient.post<SearchResponse>('/item-search/start', {
        keyword: values.keyword.trim(),
        page_count: values.pageCount,
      })

      const items = normalizeSearchItems(searchResponse.data)
      const total = normalizeSearchTotal(searchResponse.data, items)
      const responseNeedsCaptcha = needsCaptcha(searchResponse.data)

      let captchaActive = false
      if (responseNeedsCaptcha) {
        try {
          const captchaStatus = await apiClient.get<CaptchaStatusResponse>('/captcha/status', {
            params: {
              session_id: captchaResponse.data.session_id,
            },
          })
          captchaActive = Boolean(captchaStatus.data.active)
        } catch {
          captchaActive = true
        }
      }

      return {
        captchaRequired: responseNeedsCaptcha || captchaActive,
        items,
        sessionId: captchaResponse.data.session_id,
        total,
      }
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : '商品搜索失败，请稍后重试'
      setSearching(false)
      setPendingResult(null)
      setErrorMessage(message)
    },
    onMutate: (values) => {
      setCaptchaRequired(false)
      setCaptchaSessionId('')
      setCurrentPage(1)
      setErrorMessage('')
      setPendingResult(null)
      setResultTotal(0)
      setResults([])
      setSearching(true)
      setTargetPageCount(values.pageCount)
    },
    onSuccess: (data) => {
      setCaptchaRequired(data.captchaRequired)
      setCaptchaSessionId(data.sessionId)
      setPendingResult(data)
    },
  })

  useEffect(() => {
    if (!searching || !pendingResult) {
      return
    }

    if (currentPage >= targetPageCount) {
      setCaptchaRequired(pendingResult.captchaRequired)
      setCaptchaSessionId(pendingResult.sessionId)
      setResults(pendingResult.items)
      setResultTotal(pendingResult.total)
      setSearching(false)
      return
    }

    const timer = window.setTimeout(() => {
      setCurrentPage((page) => Math.min(page + 1, targetPageCount))
    }, SEARCH_PROGRESS_DURATION)

    return () => window.clearTimeout(timer)
  }, [currentPage, pendingResult, searching, targetPageCount])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      searchMutation.mutate(values)
    } catch {
      return
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ display: 'flex' }}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: token.marginXS, marginTop: 0 }}>
          商品搜索
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }} type="secondary">
          输入关键词后发起多页搜索，前端会展示进度、验证码提醒与最终结果概览。
        </Typography.Paragraph>
      </div>

      {errorMessage ? <Alert description={errorMessage} message="搜索请求失败" showIcon type="error" /> : null}

      {captchaRequired ? (
        <Alert
          description={captchaSessionId ? `验证码会话：${captchaSessionId}` : '验证码会话已创建，请在闲鱼侧完成验证。'}
          message="需要验证码，请手动处理"
          showIcon
          type="warning"
        />
      ) : null}

      <Card title="搜索条件">
        <Form
          form={form}
          initialValues={{
            keyword: '',
            pageCount: 3,
          }}
          layout="vertical"
        >
          <Space align="start" size="middle" style={{ display: 'flex' }} wrap>
            <Form.Item
              label="搜索关键词"
              name="keyword"
              rules={[{ required: true, message: '请输入搜索关键词' }]}
              style={{ flex: 1, marginBottom: 0, minWidth: 260 }}
            >
              <Input allowClear placeholder="请输入要搜索的商品关键词" />
            </Form.Item>

            <Form.Item
              label="搜索页数"
              name="pageCount"
              rules={[
                { required: true, message: '请输入搜索页数' },
                {
                  validator: async (_, value: number | null | undefined) => {
                    if (typeof value !== 'number' || value < 1 || value > 10) {
                      throw new Error('搜索页数必须在 1-10 之间')
                    }
                  },
                },
              ]}
              style={{ marginBottom: 0, minWidth: 160 }}
            >
              <InputNumber aria-label="搜索页数" style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item label=" " style={{ marginBottom: 0 }}>
              <Button loading={searchMutation.isPending} onClick={() => void handleSubmit()} type="primary">
                开始搜索
              </Button>
            </Form.Item>
          </Space>
        </Form>
      </Card>

      <Card title="搜索进度">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text strong>{searching ? '搜索中...' : '等待搜索'}</Typography.Text>
          <Typography.Text type="secondary">
            {targetPageCount ? `当前进度：第 ${Math.min(currentPage || 0, targetPageCount)} / ${targetPageCount} 页` : '尚未开始搜索'}
          </Typography.Text>
          <Progress percent={progressPercent} status={searching ? 'active' : results.length > 0 ? 'success' : 'normal'} />
        </Space>
      </Card>

      <Card title="搜索结果">
        {results.length > 0 ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Typography.Text type="secondary">共返回 {resultTotal} 条结果</Typography.Text>
            <List
              dataSource={results}
              renderItem={(item) => (
                <List.Item key={String(item.id ?? item.item_id ?? item.title ?? 'search-item')}>
                  <Space direction="vertical" size={token.marginXXS} style={{ width: '100%' }}>
                    <Typography.Text strong>{item.title || '未命名商品'}</Typography.Text>
                    <Space size={token.marginXS} wrap>
                      <Tag>{item.item_id || '无商品ID'}</Tag>
                      {item.account_id ? <Tag color="blue">{item.account_id}</Tag> : null}
                      {item.status ? <Tag color="processing">{item.status}</Tag> : null}
                      {item.price !== undefined ? <Tag color="green">¥{item.price}</Tag> : null}
                    </Space>
                  </Space>
                </List.Item>
              )}
            />
          </Space>
        ) : (
          <Empty
            description={searching ? '正在整理搜索结果，请稍候。' : '暂无搜索结果，输入关键词后开始搜索。'}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}
      </Card>
    </Space>
  )
}
