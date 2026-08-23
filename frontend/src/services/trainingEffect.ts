import api from './api'

/**
 * 培训效果因果归因 API（B 路径）
 *
 * 对应后端 /v1/training/effect/* 5 个端点 + cohort-compare
 * 设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §10
 */
export const trainingEffectAPI = {
  /** 总览（CEO 看板入口） */
  getOverview: (params?: { period_days?: number }) =>
    api.get('/training/effect/overview', { params }).then(r => r.data.data),

  /** 列表查询 */
  listExecutions: (params?: { user_id?: number; status?: string; period_days?: number; limit?: number }) =>
    api.get('/training/effect/executions', { params }).then(r => r.data.data),

  /** 详情 */
  getExecution: (executionId: number) =>
    api.get(`/training/effect/executions/${executionId}`).then(r => r.data.data),

  /** 触发 AI 归因 */
  evaluate: (executionId: number, force = false) =>
    api.post('/training/effect/evaluate', { execution_id: executionId, force }).then(r => r.data.data),

  /** 滞后期曲线（4 个时间点的指标快照 + delta） */
  lagCurve: (executionId: number) =>
    api.get('/training/effect/lag-curve', { params: { execution_id: executionId } }).then(r => r.data.data),

  /** 同期类比组对比 */
  cohortCompare: (data: { cohort_key: string; period_days?: number }) =>
    api.post('/training/effect/cohort-compare', data,
             { params: data }).then(r => r.data.data),
}

export default trainingEffectAPI
