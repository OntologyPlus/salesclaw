import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import type { ApiResponse } from '@/types'
import useAuthStore from '@/stores/auth'

// 创建 axios 实例
const api: AxiosInstance = axios.create({
  baseURL: '/v1',
  // N+5：AI 类请求（chat_send）实际可能 25-30s，统一拉到 90s 避免误 timeout
  timeout: 90000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：注入 Authorization
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：处理统一响应格式与错误
let redirectingToLogin = false

function handleUnauthorized() {
  // 防止并发 401 重复跳转；整页 reload 会随页面卸载中止所有进行中请求
  if (redirectingToLogin) return
  redirectingToLogin = true
  useAuthStore.getState().logout()
  if (window.location.pathname !== '/login') {
    window.location.replace('/login')
  }
}

api.interceptors.response.use(
  (response) => {
    const data = response.data as ApiResponse
    // 非 JSON / 无 code 字段直接返回
    if (data && typeof data.code === 'number') {
      if (data.code !== 0) {
        // 业务错误
        const error = new Error(data.message || '请求失败') as Error & { code?: number; trace_id?: string }
        error.code = data.code
        error.trace_id = data.trace_id
        return Promise.reject(error)
      }
      return response
    }
    return response
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const data = error.response.data
      // 401 未登录或 token 过期
      if (status === 401) {
        handleUnauthorized()
      }
      const message = data?.message || error.message || '网络错误'
      const wrapped = new Error(message) as Error & { code?: number; status?: number; trace_id?: string }
      wrapped.code = data?.code
      wrapped.status = status
      wrapped.trace_id = data?.trace_id
      return Promise.reject(wrapped)
    }
    return Promise.reject(error)
  }
)

export default api
