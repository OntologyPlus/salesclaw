import api from './api'

export const contextAPI = {
  get: () =>
    api.get('/context').then(r => r.data.data),
  set: (data: any) =>
    api.put('/context', data).then(r => r.data.data),
  overview: (params?: Record<string, any>) =>
    api.get('/context/overview', { params }).then(r => r.data.data),
  perspective: (params?: Record<string, any>) =>
    api.get('/context/perspective', { params }).then(r => r.data.data),
  insight: (params?: Record<string, any>) =>
    api.get('/context/insight', { params }).then(r => r.data.data),
}

export default contextAPI
