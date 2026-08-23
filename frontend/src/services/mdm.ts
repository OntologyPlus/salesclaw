import api from './api'

// 主数据模块 API
export const mdmAPI = {
  // 医院列表
  getHospitals: (params?: { keyword?: string; page?: number; page_size?: number }) =>
    api.get('/mdm/hospitals', { params }).then(r => r.data.data),

  // 医生列表
  getDoctors: (params?: { keyword?: string; page?: number; page_size?: number }) =>
    api.get('/mdm/doctors', { params }).then(r => r.data.data),

  // 产品列表
  getProducts: (params?: { keyword?: string; page?: number; page_size?: number }) =>
    api.get('/mdm/products', { params }).then(r => r.data.data),

  // 区域列表
  getZones: (params?: { page?: number; page_size?: number }) =>
    api.get('/mdm/zones', { params }).then(r => r.data.data),
}

export default mdmAPI
