import api from './api'

// 通知中心模块 API（规则管理 + 发送记录 + 失败导出）
export const notificationAPI = {
  // 规则管理
  createRule: (data: any) =>
    api.post('/notifications/rules', data).then(r => r.data.data),
  listRules: (params?: Record<string, any>) =>
    api.get('/notifications/rules', { params }).then(r => r.data.data),
  updateRuleStatus: (id: number, enabled: number) =>
    api.patch(`/notifications/rules/${id}/status`, { enabled }).then(r => r.data.data),

  // 发送记录
  listBatches: (params?: Record<string, any>) =>
    api.get('/notifications/batches', { params }).then(r => r.data.data),
  getBatch: (id: number) =>
    api.get(`/notifications/batches/${id}`).then(r => r.data.data),

  // 导出失败名单 URL（相对路径，页面带 token 下载）
  exportFailedUrl: (id: number) =>
    `/v1/notifications/batches/${id}/export-failed`,
}

export default notificationAPI
