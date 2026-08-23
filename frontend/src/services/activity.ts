import api from './api'

// 培训活动模块 API（活动编排 + 数据看板）
export const activityAPI = {
  // 活动 CRUD
  list: (params?: Record<string, any>) =>
    api.get('/training/activities', { params }).then(r => r.data.data),
  get: (id: number) =>
    api.get(`/training/activities/${id}`).then(r => r.data.data),
  create: (data: any) =>
    api.post('/training/activities', data).then(r => r.data.data),
  update: (id: number, data: any) =>
    api.put(`/training/activities/${id}`, data).then(r => r.data.data),

  // 状态流转
  publish: (id: number) =>
    api.post(`/training/activities/${id}/publish`).then(r => r.data.data),
  end: (id: number) =>
    api.post(`/training/activities/${id}/end`).then(r => r.data.data),
  offShelf: (id: number) =>
    api.post(`/training/activities/${id}/off-shelf`).then(r => r.data.data),

  // 场景关联
  listScenarios: (id: number) =>
    api.get(`/training/activities/${id}/scenarios`).then(r => r.data.data),
  addScenarios: (id: number, scenarioIds: number[]) =>
    api.post(`/training/activities/${id}/scenarios`, { scenario_ids: scenarioIds }).then(r => r.data.data),
  removeScenario: (id: number, scenarioId: number) =>
    api.delete(`/training/activities/${id}/scenarios/${scenarioId}`).then(r => r.data.data),

  // 数据看板
  analyticsSummary: (id: number) =>
    api.get(`/training/activities/${id}/analytics/summary`).then(r => r.data.data),
  analyticsTrend: (id: number, days?: number) =>
    api.get(`/training/activities/${id}/analytics/trend`, { params: { days } }).then(r => r.data.data),
  analyticsDepartment: (id: number, keyword?: string) =>
    api.get(`/training/activities/${id}/analytics/department`, { params: { keyword } }).then(r => r.data.data),
  analyticsScenario: (id: number, keyword?: string) =>
    api.get(`/training/activities/${id}/analytics/scenario`, { params: { keyword } }).then(r => r.data.data),
  analyticsLearner: (id: number, keyword?: string) =>
    api.get(`/training/activities/${id}/analytics/learner`, { params: { keyword } }).then(r => r.data.data),
  // CSV 导出 URL（相对路径，页面带 token 下载）
  analyticsExportUrl: (id: number, dimension: string) =>
    `/v1/training/activities/${id}/analytics/export?dimension=${dimension}`,
}

export default activityAPI
