import { Spin } from 'antd'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function ProtectedRoute() {
  const location = useLocation()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const isInitializing = useAuthStore((state) => state.isInitializing)

  if (isInitializing) {
    return (
      <div
        style={{
          alignItems: 'center',
          display: 'flex',
          gap: 12,
          justifyContent: 'center',
          minHeight: '100vh',
        }}
      >
        <Spin />
        <span>正在验证登录状态…</span>
      </div>
    )
  }

  if (isAuthenticated) {
    return <Outlet />
  }

  return <Navigate replace state={{ from: location }} to="/login" />
}
