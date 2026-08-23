import api from './api'

// 协同办公模块 API
export const collabAPI = {
  getOverview: () => api.get('/collab/overview').then(r => r.data.data),

  getTasks: (params?: { status?: string; task_type?: string; page?: number; page_size?: number }) =>
    api.get('/collab/tasks', { params }).then(r => r.data.data),
  getTask: (id: number) => api.get(`/collab/tasks/${id}`).then(r => r.data.data),
  createTask: (data: Record<string, unknown>) => api.post('/collab/tasks', data).then(r => r.data.data),
  updateTaskStatus: (id: number, status: string) =>
    api.patch(`/collab/tasks/${id}/status`, { status }).then(r => r.data.data),

  getApprovals: (params?: { status?: string; approval_type?: string; page?: number; page_size?: number }) =>
    api.get('/collab/approvals', { params }).then(r => r.data.data),
  getApproval: (id: number) => api.get(`/collab/approvals/${id}`).then(r => r.data.data),
  createApproval: (data: Record<string, unknown>) => api.post('/collab/approvals', data).then(r => r.data.data),
  reviewApproval: (id: number, decision: string, comment?: string) =>
    api.post(`/collab/approvals/${id}/review`, { decision, comment }).then(r => r.data.data),

  getAnnouncements: (params?: { ann_type?: string; page?: number; page_size?: number }) =>
    api.get('/collab/announcements', { params }).then(r => r.data.data),
  getAnnouncement: (id: number) => api.get(`/collab/announcements/${id}`).then(r => r.data.data),
}

export default collabAPI
