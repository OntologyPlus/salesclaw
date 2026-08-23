import api from './api'

// 决策效果追踪 API
export const effectTrackingApi = {
  // 执行记录列表
  list: (status?: string, limit?: number) =>
    api.get('/decision/executions', { params: { status, limit } }).then(r => r.data.data),

  // 单条详情
  get: (id: number) =>
    api.get(`/decision/executions/${id}`).then(r => r.data.data),

  // 创建执行记录
  create: (data: {
    decision_type: string
    title: string
    description?: string
    baseline?: Record<string, number>
    target?: Record<string, number>
  }) => api.post('/decision/executions', data).then(r => r.data.data),

  // 开始执行
  start: (id: number) =>
    api.post(`/decision/executions/${id}/start`).then(r => r.data.data),

  // 更新进度
  updateProgress: (id: number, actual_metrics: Record<string, number>) =>
    api.post(`/decision/executions/${id}/progress`, { actual_metrics }).then(r => r.data.data),

  // 完成执行
  complete: (id: number, actual_metrics?: Record<string, number>) =>
    api.post(`/decision/executions/${id}/complete`, { actual_metrics: actual_metrics || {} }).then(r => r.data.data),

  // 计算效果
  getEffectiveness: (id: number) =>
    api.get(`/decision/executions/${id}/effectiveness`).then(r => r.data.data),

  // N+AI原生闭环：经编排器 evaluate 意图做 AI 效果归因评估
  aiEvaluate: (id: number, domain = 'general') =>
    api.post(`/decision/effect/evaluate`, { execution_id: id, domain }).then(r => r.data.data),
}

export default effectTrackingApi
