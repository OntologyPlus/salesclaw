import api from './api'

// 内容工具模块 API
export const toolsAPI = {
  // 工具总览
  getOverview: () => api.get('/tools/overview').then(r => r.data.data),
}

export default toolsAPI
