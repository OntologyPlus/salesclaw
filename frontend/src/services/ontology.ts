import api from './api'

// Ontology 模块 API
export const ontologyApi = {
  // 整体统计
  getStats: () => api.get('/ontology/stats').then(r => r.data.data),

  // 域列表
  getDomains: () => api.get('/ontology/domains').then(r => r.data.data),

  // 实体列表
  getObjects: (domain?: string) =>
    api.get('/ontology/objects', { params: { domain } }).then(r => r.data.data),

  // 单个实体详情
  getObject: (name: string) =>
    api.get(`/ontology/objects/${name}`).then(r => r.data.data),

  // 关系列表
  getLinks: () => api.get('/ontology/links').then(r => r.data.data),

  // Action 列表
  getActions: (domain?: string, riskLevel?: string) =>
    api.get('/ontology/actions', { params: { domain, risk_level: riskLevel } }).then(r => r.data.data),

  // 图谱概览
  getGraph: () => api.get('/ontology/graph').then(r => r.data.data),

  // 搜索
  search: (q: string, domain?: string) =>
    api.get('/ontology/search', { params: { q, domain } }).then(r => r.data.data),

  // 实体关系（出向 + 入向）
  getRelations: (objectName: string) =>
    api.get(`/ontology/relations/${objectName}`).then(r => r.data.data),

  // L2 关系链推理：N 跳邻居子图（后端 ontology/chain 引擎，确定性规则）
  getNeighbors: (objectName: string, depth = 2, domain?: string) =>
    api.get(`/ontology/graph/neighbors/${encodeURIComponent(objectName)}`, {
      params: { depth, domain },
    }).then(r => r.data.data),

  // 本体成熟度评估（参考3 附录C 5 级成熟度模型）
  getMaturity: () => api.get('/ontology/maturity').then(r => r.data.data),
}

export default ontologyApi
