import api from './api'

// 事件统计
export interface EventStat {
  type: string
  desc: string
  total: number
  completed: number
  failed: number
  pending: number
  dead_letter_count: number
}

// AI 事件流条目
export interface AIEventItem {
  event_id: number
  event_type: string
  event_type_desc: string
  status: string
  consistency?: string
  retry_count?: number
  error_message?: string | null
  published_at?: string | null
  affected_domains?: string[]
}

// 死信队列条目
export interface DeadLetterItem {
  dead_letter_id: number
  event_id: number
  event_type: string
  event_type_desc: string
  error_message?: string | null
  failed_at?: string | null
  resolved?: boolean
}

// 可观测模块 API
export const observabilityAPI = {
  // 系统指标
  getMetrics: () => api.get('/observability/metrics').then(r => r.data.data),
  // AI 事件列表
  getEvents: (params?: { event_type?: string; status?: string; limit?: number }) =>
    api.get('/observability/events', { params }).then(r => r.data.data.items ?? []),
  // 死信队列
  getDeadLetters: (limit: number = 20) =>
    api.get('/observability/dead-letters', { params: { limit } }).then(r => r.data.data),
  // 12 种事件统计
  getEventStats: () => api.get('/observability/event-stats').then(r => r.data.data),
}

export default observabilityAPI
