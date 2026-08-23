import api from './api'

// 平台管理模块 API
export const platformAPI = {
  // 平台总览
  getOverview: () => api.get('/platform/overview').then(r => r.data.data),

  // 用户列表
  getUsers: (params?: { page?: number; page_size?: number }) =>
    api.get('/platform/users', { params }).then(r => r.data.data),

  // 角色列表
  getRoles: () => api.get('/platform/roles').then(r => r.data.data),
}

export default platformAPI
