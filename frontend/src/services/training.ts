import api from './api'

// 智能培训模块 API
export const trainingAPI = {
  // 概览
  getOverview: () => api.get('/training/overview').then(r => r.data.data),

  // 课程
  listCourses: (params?: { category?: string; difficulty?: string; keyword?: string; page?: number; page_size?: number }) =>
    api.get('/training/courses', { params }).then(r => r.data.data),
  getCourse: (id: number) => api.get(`/training/courses/${id}`).then(r => r.data.data),
  createCourse: (data: any) => api.post('/training/courses', data).then(r => r.data.data),
  updateCourse: (id: number, data: any) => api.put(`/training/courses/${id}`, data).then(r => r.data.data),
  deleteCourse: (id: number) => api.delete(`/training/courses/${id}`).then(r => r.data.data),
  enrollCourse: (id: number) => api.post(`/training/courses/${id}/enroll`).then(r => r.data.data),
  getCourseProgress: (id: number) => api.get(`/training/courses/${id}/progress`).then(r => r.data.data),
  updateCourseProgress: (id: number, data: { progress: number; last_position?: number }) =>
    api.post(`/training/courses/${id}/progress`, data).then(r => r.data.data),

  // 题库
  listQuestions: (params?: { category?: string; question_type?: string; difficulty?: string; page?: number }) =>
    api.get('/training/questions', { params }).then(r => r.data.data),
  createQuestion: (data: any) => api.post('/training/questions', data).then(r => r.data.data),

  // 考试
  listExams: (params?: { status?: string; page?: number }) =>
    api.get('/training/exams', { params }).then(r => r.data.data),
  getExam: (id: number) => api.get(`/training/exams/${id}`).then(r => r.data.data),
  createExam: (data: any) => api.post('/training/exams', data).then(r => r.data.data),
  submitExam: (id: number, answers: any[]) =>
    api.post(`/training/exams/${id}/submit`, { answers }).then(r => r.data.data),
  getExamResult: (id: number) => api.get(`/training/exams/${id}/result`).then(r => r.data.data),

  // 学习路径
  listPaths: (params?: { page?: number }) =>
    api.get('/training/paths', { params }).then(r => r.data.data),
  getPath: (id: number) => api.get(`/training/paths/${id}`).then(r => r.data.data),
  createPath: (data: any) => api.post('/training/paths', data).then(r => r.data.data),
  enrollPath: (id: number) => api.post(`/training/paths/${id}/enroll`).then(r => r.data.data),

  // 我的学习
  getMyLearning: () => api.get('/training/my-learning').then(r => r.data.data),

  // 证书
  listCertificates: (params?: { page?: number }) =>
    api.get('/training/certificates', { params }).then(r => r.data.data),

  // 演练
  listScenarios: (params?: { page?: number }) =>
    api.get('/training/scenarios', { params }).then(r => r.data.data),
  generateScenarioFromDoctor: (doctorId: number) =>
    api.post(`/training/scenarios/from-doctor/${doctorId}`).then(r => r.data.data),
  startPractice: (scenarioId: number) =>
    api.post('/training/practice/start', { scenario_id: scenarioId }).then(r => r.data.data),
  practiceMessage: (sessionId: number, message: string) =>
    api.post('/training/practice/message', { session_id: sessionId, message }).then(r => r.data.data),
  endPractice: (sessionId: number) =>
    api.post('/training/practice/end', { session_id: sessionId }).then(r => r.data.data),
}

export default trainingAPI
