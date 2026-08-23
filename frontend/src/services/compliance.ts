import api from './api'

// Phase 3 合规专项 API（公示 / 监管报送 / 年度审计）
// 对应后端 api/compliance/routes.py 的 /compliance/* 端点

export interface PublicDisclosure {
  id: number
  category: string
  title: string
  ref_type: string | null
  ref_id: number | null
  content: Record<string, unknown>
  disclosed_level: string
  status: string
  published_at: string | null
  expired_at: string | null
  created_at: string | null
}

export interface RegulatorySubmission {
  id: number
  period_type: string
  period_value: string
  submission_type: string
  format: string
  status: string
  submitted_at: string | null
  external_ref: string | null
  created_at: string | null
}

export interface AnnualComplianceAudit {
  id: number
  year: number
  scope: string | null
  metrics: Record<string, unknown>
  chain_integrity: Record<string, unknown>
  conclusion: string
  audited_at: string | null
}

export interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

export const complianceAPI = {
  // ── 公示 ──
  createDisclosure: (data: {
    category: string
    title: string
    content?: Record<string, unknown>
    ref_type?: string | null
    ref_id?: number | null
    disclosed_level?: string
    expired_at?: string | null
  }) => api.post('/compliance/public-disclosures', data).then(r => r.data.data),

  publishDisclosure: (id: number) =>
    api.post(`/compliance/public-disclosures/${id}/publish`).then(r => r.data.data),

  listDisclosures: (params?: {
    category?: string
    status?: string
    disclosed_level?: string
    page?: number
    page_size?: number
  }) => api.get('/compliance/public-disclosures', { params }).then(r => r.data.data),

  // ── 监管报送 ──
  createSubmission: (data: {
    period_type: string
    period_value: string
    submission_type: string
    format?: string
  }) => api.post('/compliance/regulatory-submissions', data).then(r => r.data.data),

  listSubmissions: (params?: {
    period_type?: string
    status?: string
    page?: number
    page_size?: number
  }) => api.get('/compliance/regulatory-submissions', { params }).then(r => r.data.data),

  submitSubmission: (id: number, external_ref?: string) =>
    api.post(`/compliance/regulatory-submissions/${id}/submit`, null, {
      params: external_ref ? { external_ref } : {},
    }).then(r => r.data.data),

  previewSubmission: (params: {
    period_type: string
    period_value: string
    submission_type?: string
  }) => api.get('/compliance/regulatory-submissions/preview', { params }).then(r => r.data.data),

  exportSubmission: (id: number, fmt = 'json') =>
    api.get(`/compliance/regulatory-submissions/${id}/export`, {
      params: { fmt },
      responseType: 'blob',
    }).then(r => r.data),

  pushSubmissionExternal: (id: number) =>
    api.post(`/compliance/regulatory-submissions/${id}/push-external`).then(r => r.data.data),

  // ── 年度审计 ──
  generateAnnualAudit: (year: number, scope?: string) =>
    api.post(`/compliance/annual-audit/${year}`, null, {
      params: scope ? { scope } : {},
    }).then(r => r.data.data),

  listAnnualAudits: (params?: { page?: number; page_size?: number }) =>
    api.get('/compliance/annual-audits', { params }).then(r => r.data.data),

  // ── 医药代表备案（第 14-18 条）──
  getProfile: (userId: number) =>
    api.get(`/compliance/profile/${userId}`).then(r => r.data.data),

  updateProfile: (userId: number, data: Record<string, unknown>) =>
    api.put(`/compliance/profile/${userId}`, data).then(r => r.data.data),

  submitRegistration: (userId: number) =>
    api.post(`/compliance/profile/${userId}/submit-registration`).then(r => r.data.data),

  revokeRegistration: (userId: number, reason: string) =>
    api.post(`/compliance/profile/${userId}/revoke`, { reason }).then(r => r.data.data),

  listPendingRevokes: () =>
    api.get('/compliance/pending-revokes').then(r => r.data.data),

  // ── 合规承诺 / 准入（第 9、10、15 条）──
  signCommitment: (data: {
    commitment_type: string
    commitment_text: string
    version: string
    course_id?: number | null
    exam_record_id?: number | null
  }) => api.post('/compliance/commitment/sign', data).then(r => r.data.data),

  checkOnboarding: (userId: number) =>
    api.get(`/compliance/onboarding-check/${userId}`).then(r => r.data.data),

  checkOnboardingGate: (userId: number) =>
    api.get(`/compliance/onboarding-gate/${userId}`).then(r => r.data.data),

  // ── 违规管理 / 合规预警（第 11、12、24、25 条）──
  listViolationEvents: (params?: {
    status?: string
    severity?: string
    page?: number
    page_size?: number
  }) => api.get('/compliance/violation-events', { params }).then(r => r.data.data),

  handleViolationEvent: (eventId: number, result: string, status = 'resolved') =>
    api.post(`/compliance/violation-events/${eventId}/handle`, { result, status }).then(r => r.data.data),

  listAlerts: (params?: {
    status?: string
    severity?: string
    alert_type?: string
    page?: number
    page_size?: number
  }) => api.get('/compliance/alerts', { params }).then(r => r.data.data),

  handleAlert: (alertId: number, result: string, status = 'resolved') =>
    api.post(`/compliance/alerts/${alertId}/handle`, { result, status }).then(r => r.data.data),

  scanDeadlines: () =>
    api.post('/compliance/deadlines/scan').then(r => r.data.data),

  // ── 禁止行为清单（第 11、12、24、25 条）──
  listForbiddenBehaviors: (subject?: string) =>
    api.get('/compliance/forbidden-behaviors', {
      params: subject ? { subject } : {},
    }).then(r => r.data.data),

  listForbiddenTools: () =>
    api.get('/compliance/forbidden-tools').then(r => r.data.data),
}

export default complianceAPI
