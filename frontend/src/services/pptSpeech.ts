import api from './api'

export const pptSpeechAPI = {
  // PPT 场景
  listScenarios: (params?: Record<string, any>) =>
    api.get('/training/ppt/scenarios', { params }).then(r => r.data.data),
  getScenario: (id: number) =>
    api.get(`/training/ppt/scenarios/${id}`).then(r => r.data.data),
  createScenario: (data: any) =>
    api.post('/training/ppt/scenarios', data).then(r => r.data.data),
  updateScenario: (id: number, data: any) =>
    api.put(`/training/ppt/scenarios/${id}`, data).then(r => r.data.data),
  publishScenario: (id: number) =>
    api.post(`/training/ppt/scenarios/${id}/publish`).then(r => r.data.data),
  parsePPT: (id: number) =>
    api.post(`/training/ppt/scenarios/${id}/parse`).then(r => r.data.data),

  // PPT 演讲会话
  startSession: (data: { scenario_id: number; mode?: string; activity_id?: number }) =>
    api.post('/training/ppt/sessions/start', data).then(r => r.data.data),
  submitPage: (sessionId: number, data: { page_no: number; recording: any }) =>
    api.post(`/training/ppt/sessions/${sessionId}/page-submit`, data).then(r => r.data.data),
  submitQA: (sessionId: number, data: { question_id: number; answer: any }) =>
    api.post(`/training/ppt/sessions/${sessionId}/qa`, data).then(r => r.data.data),
  completeSession: (sessionId: number) =>
    api.post(`/training/ppt/sessions/${sessionId}/complete`).then(r => r.data.data),
  getSession: (id: number) =>
    api.get(`/training/ppt/sessions/${id}`).then(r => r.data.data),
  listSessions: (params?: Record<string, any>) =>
    api.get('/training/ppt/sessions', { params }).then(r => r.data.data),
}

export default pptSpeechAPI
