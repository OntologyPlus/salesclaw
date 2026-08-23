import api from './api'

// AI 模型配置
export interface AIConfig {
  provider: string
  model: string
  base_url: string
  enable_thinking: boolean
  reasoning_budget: number
  temperature: number
  top_p: number
  max_tokens: number
}

// LLM 调用日志
export interface LlmLog {
  id: number
  provider: string
  model: string
  prompt_tokens: number
  completion_tokens: number
  duration_ms: number
  status: string
  ts: string
}

// 设置模块 API
export const settingsAPI = {
  // 设置总览（个人资料 + 通知订阅）
  getOverview: () => api.get('/settings/overview').then(r => r.data.data),
  // AI 模型配置
  getAIConfig: () => api.get('/settings/ai-config').then(r => r.data.data),
  // LLM 调用日志
  getLLMLogs: (limit: number = 10) =>
    api.get('/settings/llm-logs', { params: { limit } }).then(r => r.data.data),
}

export default settingsAPI
