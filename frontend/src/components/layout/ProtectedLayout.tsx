import { Navigate, Outlet, useLocation } from 'react-router-dom'
import useAuthStore from '@/stores/auth'
import Layout from './Layout'

// 鉴权布局：未登录跳转 /login
export default function ProtectedLayout() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return (
    <Layout>
      <Outlet />
    </Layout>
  )
}
