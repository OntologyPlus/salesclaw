import api from './api'

// 综合能力画像模块 API
export const profileAPI = {
  // 综合能力评分
  getScore: () => api.get('/profile/score').then(r => r.data.data),
  // 学习需求分析
  getLearningNeeds: () => api.get('/profile/learning-needs').then(r => r.data.data),
  // 雷达图数据
  getRadar: () => api.get('/profile/radar').then(r => r.data.data),
  // 全息画像
  getFullProfile: () => api.get('/profile/full').then(r => r.data.data),
}

export default profileAPI
