import api from './api'

export const personaAPI = {
  list: (params?: Record<string, any>) =>
    api.get('/personas', { params }).then(r => r.data.data),
  get: (id: number) =>
    api.get(`/personas/${id}`).then(r => r.data.data),
  create: (data: any) =>
    api.post('/personas', data).then(r => r.data.data),
  update: (id: number, data: any) =>
    api.put(`/personas/${id}`, data).then(r => r.data.data),
  delete: (id: number) =>
    api.delete(`/personas/${id}`).then(r => r.data.data),
  match: (rawText: string) =>
    api.get('/personas/match', { params: { raw_text: rawText } }).then(r => r.data.data),
}

export default personaAPI
