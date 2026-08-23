import api from './api'

// 知识库模块 API
export const knowledgeAPI = {
  getOverview: () => api.get('/knowledge/overview').then(r => r.data.data),

  getDocuments: (params?: { category?: string; keyword?: string; page?: number; page_size?: number }) =>
    api.get('/knowledge/documents', { params }).then(r => r.data.data),
  getDocument: (id: number) => api.get(`/knowledge/documents/${id}`).then(r => r.data.data),
  createDocument: (data: Record<string, unknown>) => api.post('/knowledge/documents', data).then(r => r.data.data),

  getFaqs: (params?: { category?: string; keyword?: string; page?: number; page_size?: number }) =>
    api.get('/knowledge/faqs', { params }).then(r => r.data.data),
  getFaq: (id: number) => api.get(`/knowledge/faqs/${id}`).then(r => r.data.data),

  search: (keyword: string) => api.get('/knowledge/search', { params: { keyword } }).then(r => r.data.data),
}

export default knowledgeAPI
