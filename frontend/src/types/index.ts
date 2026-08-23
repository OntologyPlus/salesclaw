// 统一响应格式
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  trace_id: string
}

// 分页响应
export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// 用户
export interface User {
  id: number
  username: string
  display_name: string
  email: string
  phone?: string
  avatar?: string
  tenant_id: string
  roles: string[]
  permissions: string[]
  status: 'active' | 'inactive' | 'locked'
  created_at: string
  updated_at: string
}

// 租户
export interface Tenant {
  id: string
  name: string
  code: string
  status: 'active' | 'inactive'
  plan: 'free' | 'pro' | 'enterprise'
  expires_at?: string
  created_at: string
}

// 登录响应
export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

// AI Agent
export interface Agent {
  name: string
  display_name: string
  description: string
  domain: string
  capabilities: string[]
  icon?: string
  enabled: boolean
}

// AI Action
export interface Action {
  name: string
  display_name: string
  description: string
  agent: string
  parameters: Record<string, unknown>
  requires_review: boolean
  enabled: boolean
}

// 聊天消息
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  agent_used?: string
  actions_called?: string[]
  references?: Reference[]
  created_at: string
  pending?: boolean
  error?: string
}

// 引用
export interface Reference {
  title: string
  url?: string
  type?: string
}

// 聊天会话
export interface ChatSession {
  id: string
  agent: string
  title: string
  messages: ChatMessage[]
  created_at: string
  updated_at: string
}

// 聊天发送响应
export interface ChatSendResponse {
  session_id: string
  response: string
  agent_used: string
  actions_called: string[]
  references: Reference[]
}

// Toast 通知
export interface ToastItem {
  id: string
  message: string
  type: 'info' | 'success' | 'warning' | 'error'
}

// 命令面板项
export interface CommandItem {
  id: string
  label: string
  description?: string
  icon?: string
  group: string
  keywords?: string
  action: () => void
}

// 面包屑
export interface Breadcrumb {
  label: string
  path?: string
}

// ──────────────────────────────────────────────
// 本体论 + AI 原生改造：诊断/信号实体类型
// ──────────────────────────────────────────────
export type DiagnosisLevel = 'GREEN' | 'YELLOW' | 'RED' | 'BLACK'
export type DiagnosisStatus = 'draft' | 'confirmed' | 'executing' | 'verified' | 'closed'
export type SignalSeverity = 'high' | 'medium' | 'low'

export interface SignalEntity {
  id: number
  name: string
  category: string
  severity: SignalSeverity
  cleared: number
  clear_condition: string
}

export interface ProvenanceInfo {
  mode?: string
  intent?: string
  agent?: string
  model_version?: string
  run_id?: number | null
}

// OAG Layer 4 生成校验层：五维校验明细
export interface ValidationDetail {
  numeric_ok?: boolean | null
  relation_ok?: boolean | null
  temporal_ok?: boolean | null
  causal_ok?: boolean | null
  business_rule_ok?: boolean | null
  score?: number
  strategies?: Record<string, { score: number; flag: string | null }>
  extra?: Record<string, unknown>
}

// OAG Layer 5 动作闭环：可触发动作建议
export interface ActionSuggestion {
  action: string
  display_name: string
  risk_level: string
  description: string
}

export interface DiagnosisEntity {
  id: number
  rep_id: number
  domain: string
  target_type: string | null
  target_id: number | null
  summary: string
  level: DiagnosisLevel
  confidence: number
  status: DiagnosisStatus
  trace_id: string | null
  reasoning_chain_id: number | null
  provenance: ProvenanceInfo | null
  // OAG 借鉴点（置信度档位 🟢/🟡/🔴 + 校验明细 + 可触发动作）
  confidence_band?: 'GREEN' | 'YELLOW' | 'RED' | null
  validation_detail?: ValidationDetail | null
  action_suggestion?: ActionSuggestion[]
  // 误判排除闸（方案第五章 O14）：红/黄灯受结构性因素驱动时降级并标记
  excluded?: number | null
  excluded_reason?: {
    type: string
    label: string
    desc: string
    original_level: string
    evidence?: string
  } | null
  signals: SignalEntity[]
  created_at: string | null
}

export interface ParadigmEntity {
  id: number
  domain: string
  problem_type: string
  title: string
  effective_method: string
  evidence_execution_ids: number[]
  usage_count: number
  effectiveness_score: number
  reasoning_chain_id?: string | number | null
  created_at: string | null
}

export interface AttributionFactor {
  name: string
  contribution: number
  direction?: string
  evidence?: string
}

// ── L2 关系链推理（跨对象归因）类型 ──
export interface ChainLink {
  name: string
  display_name: string
  relation: string
}

export interface ChainPath {
  nodes: string[]
  links: ChainLink[]
  depth: number
  contribution: number       // 单跳传播权重 0-1
  arrived_prob: number       // 累计到达概率 0-1
  target_reached: boolean
  terminal: string
}

export interface ChainNode {
  name: string
  display_name: string
  domain: string
}

export interface ChainEdge {
  source: string
  target: string
  source_display: string
  target_display: string
  link: string
  display_name: string
  relation: string
  cardinality: string
}

export interface ChainSubgraph {
  nodes: ChainNode[]
  edges: ChainEdge[]
}

export interface ChainRootCause {
  object: string
  display_name: string
  domain: string
  contribution: number
  reason: string
}

export interface ChainResult {
  root_type: string
  root_id?: number | null
  target_type?: string | null
  domain?: string | null
  max_depth: number
  ai_generated: boolean
  paths?: ChainPath[]
  subgraph?: ChainSubgraph
  root_cause: ChainRootCause | null
  summary: string
}

export interface AttributionResult {
  source: string
  summary: string
  level: string
  confidence: number
  factors: AttributionFactor[]
  root_cause: string
  evidence: Array<Record<string, unknown>>
  reasoning_chain_id?: number | null
  provenance?: ProvenanceInfo | null
  trace_id?: string | null
  chain?: ChainResult | null
}
