import api from './api'

// 审计模块 API
export const auditAPI = {
  // 审计总览
  getOverview: () => api.get('/audit/overview').then(r => r.data.data),

  // 审计日志列表
  getLogs: (params?: { action?: string; actor_id?: string | number; page?: number; page_size?: number }) =>
    api.get('/audit/logs', { params }).then(r => r.data.data),

  // 导出审计日志（format=csv/json）
  exportLogs: (params?: { format?: 'csv' | 'json'; action?: string; actor_id?: string | number }) =>
    api.get('/audit/export', { params }).then(r => r.data.data),
}

export default auditAPI
