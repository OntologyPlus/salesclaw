import api from './api'

// CRM 模块 API
export const crmAPI = {
  // 客户关系总览
  getOverview: () => api.get('/crm/overview').then(r => r.data.data),

  // 客户列表
  getCustomers: (params?: { page?: number; page_size?: number }) =>
    api.get('/crm/customers', { params }).then(r => r.data.data),

  // 互动记录列表
  getInteractions: (params?: { page?: number; page_size?: number }) =>
    api.get('/crm/interactions', { params }).then(r => r.data.data),
}

export default crmAPI
