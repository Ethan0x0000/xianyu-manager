import { Button, Result } from 'antd'
import { Component, type ErrorInfo, type ReactNode } from 'react'

type AppErrorBoundaryProps = {
  children: ReactNode
}

type AppErrorBoundaryState = {
  hasError: boolean
}

export default class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = {
    hasError: false,
  }

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Unhandled application error', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
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
          <Result
            extra={
              <Button
                type="primary"
                onClick={() => {
                  if (typeof window !== 'undefined') {
                    window.location.reload()
                  }
                }}
              >
                刷新页面
              </Button>
            }
            status="error"
            subTitle="请刷新页面后重试；如果问题持续出现，请检查浏览器控制台与后端日志。"
            title="页面发生错误"
          />
        </div>
      )
    }

    return this.props.children
  }
}
