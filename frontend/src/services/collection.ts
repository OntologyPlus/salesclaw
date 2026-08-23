import api from './api'

// 数据采集模块 API
export const collectionAPI = {
  // 项目管理
  listProjects: (params?: Record<string, any>) =>
    api.get('/collection/projects', { params }).then(r => r.data.data),
  getProject: (id: number) =>
    api.get(`/collection/projects/${id}`).then(r => r.data.data),
  createProject: (data: any) =>
    api.post('/collection/projects', data).then(r => r.data.data),
  updateProject: (id: number, data: any) =>
    api.put(`/collection/projects/${id}`, data).then(r => r.data.data),
  generateItems: (id: number) =>
    api.post(`/collection/projects/${id}/generate-items`).then(r => r.data.data),
  regenerateTodos: (id: number) =>
    api.post(`/collection/projects/${id}/regenerate-todos`).then(r => r.data.data),

  // 数据项管理（状态机）
  listItems: (params?: Record<string, any>) =>
    api.get('/collection/items', { params }).then(r => r.data.data),
  getItem: (id: number) =>
    api.get(`/collection/items/${id}`).then(r => r.data.data),
  submitItem: (id: number, values: any) =>
    api.post(`/collection/items/${id}/submit`, { values }).then(r => r.data.data),
  withdrawItem: (id: number) =>
    api.post(`/collection/items/${id}/withdraw`).then(r => r.data.data),
  approveItem: (id: number) =>
    api.post(`/collection/items/${id}/approve`).then(r => r.data.data),
  rejectItem: (id: number, reason: string) =>
    api.post(`/collection/items/${id}/reject`, { reason }).then(r => r.data.data),
  lockItem: (id: number) =>
    api.post(`/collection/items/${id}/lock`).then(r => r.data.data),
  publishItem: (id: number) =>
    api.post(`/collection/items/${id}/publish`).then(r => r.data.data),
  unpublishItem: (id: number, reason: string) =>
    api.post(`/collection/items/${id}/unpublish`, { reason }).then(r => r.data.data),

  // 模板管理
  listTemplates: (params?: Record<string, any>) =>
    api.get('/collection/templates', { params }).then(r => r.data.data),
  createTemplate: (data: any) =>
    api.post('/collection/templates', data).then(r => r.data.data),

  // 待办任务管理
  listTodos: (params?: Record<string, any>) =>
    api.get('/collection/todos', { params }).then(r => r.data.data),
  getTodo: (id: number) =>
    api.get(`/collection/todos/${id}`).then(r => r.data.data),
  getTodoDialog: (id: number) =>
    api.get(`/collection/todos/${id}/dialog`).then(r => r.data.data),
  getTodoSubmissions: (id: number) =>
    api.get(`/collection/todos/${id}/submissions`).then(r => r.data.data),
  batchDeleteTodos: (ids: number[]) =>
    api.post('/collection/todos/batch-delete', { todo_ids: ids }).then(r => r.data.data),
}

export default collectionAPI
