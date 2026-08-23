import api from './api'
import type { ApiResponse, LoginResponse, User } from '@/types'

// 登录
export async function login(
  username: string,
  password: string,
  tenant_code: string
): Promise<LoginResponse> {
  const res = await api.post<ApiResponse<LoginResponse>>('/auth/login', {
    username,
    password,
    tenant_code,
  })
  return res.data.data
}

// 刷新 token
export async function refresh(refresh_token: string): Promise<LoginResponse> {
  const res = await api.post<ApiResponse<LoginResponse>>('/auth/refresh', {
    refresh_token,
  })
  return res.data.data
}

// 登出
export async function logout(): Promise<void> {
  await api.post<ApiResponse<null>>('/auth/logout')
}

// 获取当前用户
export async function getMe(): Promise<User> {
  const res = await api.get<ApiResponse<User>>('/auth/me')
  return res.data.data
}

// 修改密码
export async function changePassword(old_password: string, new_password: string): Promise<void> {
  await api.post<ApiResponse<null>>('/auth/change-password', {
    old_password,
    new_password,
  })
}
