import api from './api'

// 销售执行模块 API
export const salesAPI = {
  // 销售总览
  getOverview: () => api.get('/sales/overview').then(r => r.data.data),

  // 拜访计划
  listPlans: (params?: { status?: string; page?: number; page_size?: number }) =>
    api.get('/sales/visit-plans', { params }).then(r => r.data.data),
  getPlan: (id: number) => api.get(`/sales/visit-plans/${id}`).then(r => r.data.data),
  createPlan: (data: { period: string; target_count: number; items?: any[] }) =>
    api.post('/sales/visit-plans', data).then(r => r.data.data),
  updatePlan: (id: number, data: any) => api.put(`/sales/visit-plans/${id}`, data).then(r => r.data.data),
  deletePlan: (id: number) => api.delete(`/sales/visit-plans/${id}`).then(r => r.data.data),
  submitPlan: (id: number) => api.post(`/sales/visit-plans/${id}/submit`).then(r => r.data.data),
  approvePlan: (id: number) => api.post(`/sales/visit-plans/${id}/approve`).then(r => r.data.data),
  rejectPlan: (id: number, reason: string) => api.post(`/sales/visit-plans/${id}/reject`, { reason }).then(r => r.data.data),
  aiRecommend: () => api.post('/sales/visit-plans/ai-recommend').then(r => r.data.data),

  // 拜访记录
  listRecords: (params?: { hospital_id?: number; page?: number; page_size?: number }) =>
    api.get('/sales/visit-records', { params }).then(r => r.data.data),
  getRecord: (id: number) => api.get(`/sales/visit-records/${id}`).then(r => r.data.data),
  createRecord: (data: any) => api.post('/sales/visit-records', data).then(r => r.data.data),
  updateRecord: (id: number, data: any) => api.put(`/sales/visit-records/${id}`, data).then(r => r.data.data),
  deleteRecord: (id: number) => api.delete(`/sales/visit-records/${id}`).then(r => r.data.data),

  // 拜访反馈
  listFeedbacks: (params?: { record_id?: number; page?: number; page_size?: number }) =>
    api.get('/sales/visit-feedbacks', { params }).then(r => r.data.data),
  createFeedback: (data: any) => api.post('/sales/visit-feedbacks', data).then(r => r.data.data),

  // 覆盖分管
  listCoverage: (params?: { user_id?: number; page?: number }) =>
    api.get('/sales/coverage', { params }).then(r => r.data.data),
  assignCoverage: (data: any) => api.post('/sales/coverage', data).then(r => r.data.data),

  // 矩阵看板
  getMatrix: (params?: { product_id?: number }) => api.get('/sales/matrix', { params }).then(r => r.data.data),

  // 积分管理（后端路径为 /sales/points/*，rules 返回 {items: [...]} 需提取）
  getScoringRules: () => api.get('/sales/points/rules').then(r => r.data.data?.items ?? []),
  getScoringRecords: (params?: { page?: number; page_size?: number }) =>
    api.get('/sales/points/records', { params }).then(r => r.data.data),
  getScoringSummary: () => api.get('/sales/points/summary').then(r => r.data.data),

  // 周报
  listWeeklyReports: (params?: { page?: number }) => api.get('/sales/weekly-reports', { params }).then(r => r.data.data),
  generateWeeklyReport: (weekStart: string) => api.post('/sales/weekly-reports/generate', { week_start: weekStart }).then(r => r.data.data),

  // 主数据（后端返回分页对象，这里提取 items 数组便于下拉选择使用）
  listHospitals: () => api.get('/sales/hospitals').then(r => r.data.data?.items ?? []),
  listDoctors: (params?: { hospital_id?: number }) => api.get('/sales/doctors', { params }).then(r => r.data.data?.items ?? []),
  listProducts: () => api.get('/sales/products').then(r => r.data.data?.items ?? []),
}

// 门户模块 API
export const portalAPI = {
  getOverview: () => api.get('/portal/overview').then(r => r.data.data),
  getShortcuts: () => api.get('/portal/shortcuts').then(r => r.data.data),
  getActivities: () => api.get('/portal/activities').then(r => r.data.data),
}

export default salesAPI
