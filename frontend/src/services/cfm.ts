import api from './api'

// 会议论坛模块 API
export const cfmAPI = {
  // 会议论坛总览
  getOverview: () => api.get('/cfm/overview').then(r => r.data.data),

  // 会议列表
  getMeetings: (params?: { status?: string; meeting_type?: string; page?: number; page_size?: number }) =>
    api.get('/cfm/meetings', { params }).then(r => r.data.data),

  // 话题列表
  getTopics: (params?: { category?: string; page?: number; page_size?: number }) =>
    api.get('/cfm/topics', { params }).then(r => r.data.data),
}

export default cfmAPI
