import api from './api'

export const experienceAPI = {
  myPoints: () =>
    api.get('/experience/me').then(r => r.data.data),
  myHistory: (params?: Record<string, any>) =>
    api.get('/experience/me/history', { params }).then(r => r.data.data),
  leaderboard: (params?: Record<string, any>) =>
    api.get('/experience/leaderboard', { params }).then(r => r.data.data),
}

export default experienceAPI
