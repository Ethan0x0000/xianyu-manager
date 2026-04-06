import { Alert, Button, Card, Form, Input, Spin, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import { loginApi } from '../api/auth'
import { useAuthStore } from '../stores/authStore'
import type { ApiError, LoginRequest } from '../api/types'

type LoginInfoStatus = {
  enabled: boolean
}

function getErrorMessage(error: unknown) {
  if (typeof error === 'object' && error !== null) {
    const apiError = error as { response?: { data?: ApiError } }
    return apiError.response?.data?.detail ?? apiError.response?.data?.message ?? '登录失败，请重试'
  }

  return '登录失败，请重试'
}

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const login = useAuthStore((state) => state.login)
  const verifyToken = useAuthStore((state) => state.verifyToken)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [showDefaultCredentials, setShowDefaultCredentials] = useState(false)
  const [infoLoading, setInfoLoading] = useState(true)

  const redirectPath = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? '/dashboard'

  useEffect(() => {
    if (isAuthenticated) {
      navigate(redirectPath, { replace: true })
    }
  }, [isAuthenticated, navigate, redirectPath])

  useEffect(() => {
    async function fetchLoginInfo() {
      try {
        const response = await apiClient.get<LoginInfoStatus>('/auth/login-info-status')
        setShowDefaultCredentials(response.data.enabled)
      } catch {
        // Silently fail - if endpoint is unavailable, just don't show hint
        setShowDefaultCredentials(false)
      } finally {
        setInfoLoading(false)
      }
    }

    fetchLoginInfo()
  }, [])

  async function handleFinish(values: LoginRequest) {
    setLoading(true)
    setErrorMessage(null)

    try {
      const response = await loginApi(values)
      login(response.token)

      const verified = await verifyToken()
      if (!verified) {
        setErrorMessage('登录状态校验失败，请重新登录')
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }

  if (infoLoading) {
    return (
      <div
        style={{
          alignItems: 'center',
          display: 'flex',
          justifyContent: 'center',
          minHeight: '100vh',
        }}
      >
        <Spin />
      </div>
    )
  }

  return (
    <div
      style={{
        alignItems: 'center',
        display: 'flex',
        justifyContent: 'center',
        minHeight: '100vh',
        padding: 24,
      }}
    >
      <Card style={{ maxWidth: 420, width: '100%' }}>
        <Typography.Title level={2}>管理员登录</Typography.Title>
        <Typography.Paragraph type="secondary">请输入管理员账号与密码</Typography.Paragraph>

        {errorMessage ? (
          <Alert
            closable
            message={errorMessage}
            onClose={() => setErrorMessage(null)}
            showIcon
            style={{ marginBottom: 16 }}
            type="error"
          />
        ) : null}

        {showDefaultCredentials ? (
          <Alert
            message="默认凭证已启用"
            description="默认用户名: admin  默认密码: admin123"
            showIcon
            style={{ marginBottom: 16 }}
            type="info"
          />
        ) : null}

        <Form<LoginRequest> layout="vertical" onFinish={handleFinish}>
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input autoComplete="username" placeholder="admin" disabled={loading} />
          </Form.Item>

          <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password autoComplete="current-password" placeholder="请输入密码" disabled={loading} />
          </Form.Item>

          <Button block htmlType="submit" loading={loading} type="primary">
            登录
          </Button>
        </Form>
      </Card>
    </div>
  )
}
