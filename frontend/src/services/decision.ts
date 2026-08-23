import api from './api'

// 决策支持模块 API
export const decisionAPI = {
  getOverview: () => api.get('/decision/overview').then(r => r.data.data),
  getKpi: () => api.get('/decision/kpi').then(r => r.data.data),
  getAttribution: () => api.get('/decision/attribution').then(r => r.data.data),
  simulate: (visitChange: number, trainingChange: number) =>
    api.post('/decision/simulate', { visit_change: visitChange, training_change: trainingChange }).then(r => r.data.data),
  getAlerts: () => api.get('/decision/alerts').then(r => r.data.data),
  getDiagnosis: () => api.get('/decision/diagnosis').then(r => r.data.data),
  getReason: (targetType: string, targetId: number, explanationType = 'causal') =>
    api.get(`/decision/reason/${targetType}/${targetId}`, { params: { explanation_type: explanationType } }).then(r => r.data.data),
  getConfidence: (chainId: number) =>
    api.get(`/decision/confidence/${chainId}`).then(r => r.data.data),

  // 诊断闭环
  getLoop: (scope = 'all') =>
    api.get('/decision/loop', { params: { scope } }).then(r => r.data.data),
  getLoopRep: (repId: number) =>
    api.get(`/decision/loop/rep/${repId}`).then(r => r.data.data),
  getLoopTeam: (region: string) =>
    api.get(`/decision/loop/team/${region}`).then(r => r.data.data),

  // 随访闭环（v2 — 全链路）
  confirmLoop: (repId: number, domain: string, suggestion: Record<string, unknown>) =>
    api.post('/decision/loop/confirm', { rep_id: repId, domain, suggestion }).then(r => r.data.data),
  getFollowup: (executionId: number) =>
    api.get(`/decision/loop/followup/${executionId}`).then(r => r.data.data),
  completeLoop: (executionId: number, actualMetrics: Record<string, unknown>, forceClosureState?: string) =>
    api.post(`/decision/loop/complete/${executionId}`, { actual_metrics: actualMetrics, force_closure_state: forceClosureState }).then(r => r.data.data),
  getParadigms: (executionId?: number, domain?: string) =>
    api.get('/decision/loop/paradigms', { params: { execution_id: executionId, domain } }).then(r => r.data.data),
  getRepHistory: (repId: number) =>
    api.get(`/decision/loop/history/${repId}`).then(r => r.data.data),
  getTeamClosure: (region?: string, month?: string) =>
    api.get('/decision/loop/team-closure', { params: { region, month } }).then(r => r.data.data),

  // AI 原生诊断（本体论实体驱动）
  aiDiagnose: (domain = 'coverage', targetType?: string, targetId?: number) =>
    api.post('/decision/ai-diagnose', { domain, target_type: targetType, target_id: targetId }).then(r => r.data.data),
  aiAttribute: (domain = 'coverage', targetType?: string, targetId?: number) =>
    api.post('/decision/ai-attribute', { domain, target_type: targetType, target_id: targetId }).then(r => r.data.data),
  confirmDiagnosis: (diagnosisId: number) =>
    api.post('/decision/diagnosis/confirm', { diagnosis_id: diagnosisId }).then(r => r.data.data),
  advanceDiagnosis: (diagnosisId: number, toStatus: string) =>
    api.post('/decision/diagnosis/advance', { diagnosis_id: diagnosisId, to_status: toStatus }).then(r => r.data.data),
  listDiagnoses: (status?: string, domain?: string, repId?: number) =>
    api.get('/decision/diagnoses', { params: { status, domain, rep_id: repId } }).then(r => r.data.data),

  // 信号独立交互
  clearSignal: (signalId: number) =>
    api.post('/decision/signal/clear', { signal_id: signalId }).then(r => r.data.data),

  // 范式库（本体范式实体，新表）
  getLibraryParadigms: (domain?: string) =>
    api.get('/decision/paradigms', { params: { domain } }).then(r => r.data.data),
  deriveParadigm: (executionId: number, domain: string) =>
    api.post('/decision/paradigm/derive', { execution_id: executionId, domain }).then(r => r.data.data),

  // AI 归因（经编排器七步）
  getAttributionAI: (domain = 'attribution', targetType?: string, targetId?: number) =>
    api.post('/decision/ai-attribute', { domain, target_type: targetType, target_id: targetId }).then(r => r.data.data),

  // 推理链详情（可观测 AI 原生）
  getReasoningChain: (chainId: number) =>
    api.get(`/decision/reasoning-chain/${chainId}`).then(r => r.data.data),

  // L2 关系链推理：跨对象归因（ontology/chain）
  getChain: (params: {
    root_type: string
    root_id?: number
    target_type?: string
    domain?: string
    max_depth?: number
  }) =>
    api.get('/ontology/chain', { params }).then(r => r.data.data),

  // N 跳邻居查询（ontology/graph/neighbors/{object}）
  getNeighbors: (objectName: string, depth = 2, domain?: string) =>
    api.get(`/ontology/graph/neighbors/${encodeURIComponent(objectName)}`, {
      params: { depth, domain },
    }).then(r => r.data.data),
}

export default decisionAPI
