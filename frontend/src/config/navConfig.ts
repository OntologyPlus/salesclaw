// 角色/工作流导向导航（单一事实来源）
// tier=primary 进侧栏；secondary 经域总览 / ⌘K 到达，路由保留。
import type { LucideIcon } from 'lucide-react'

export type NavTier = 'primary' | 'secondary'

export interface NavItem {
  path: string
  labelKey: string
  label: string
  end?: boolean
  icon?: LucideIcon
  /** primary = 侧栏可见；secondary = 总览/⌘K */
  tier?: NavTier
}

export interface NavGroup {
  id: string
  titleKey: string
  items: NavItem[]
}

const LIST_ROOTS = [
  '/portal',
  '/profile',
  '/sales',
  '/training',
  '/decision',
  '/collab',
  '/knowledge',
  '/collection',
  '/compliance',
]

const end = (path: string) => LIST_ROOTS.includes(path)

const p = (item: Omit<NavItem, 'tier'>): NavItem => ({ ...item, tier: 'primary' })
const s = (item: Omit<NavItem, 'tier'>): NavItem => ({ ...item, tier: 'secondary' })

/** 完整导航（含 secondary） */
export const navGroups: NavGroup[] = [
  {
    id: 'today',
    titleKey: 'nav.group.today',
    items: [
      p({ path: '/portal', labelKey: 'nav.portal', label: '门户', end: end('/portal') }),
      s({ path: '/profile', labelKey: 'nav.profile', label: '我的画像', end: end('/profile') }),
      p({ path: '/notification-center', labelKey: 'nav.notificationCenter', label: '通知中心' }),
      p({ path: '/ai', labelKey: 'nav.ai', label: 'AI 助手' }),
    ],
  },
  {
    id: 'visit',
    titleKey: 'nav.group.visit',
    items: [
      p({ path: '/sales', labelKey: 'nav.sales', label: '销售总览', end: end('/sales') }),
      p({ path: '/sales/plans', labelKey: 'nav.visitPlans', label: '拜访计划' }),
      p({ path: '/sales/records', labelKey: 'nav.visitRecords', label: '拜访记录' }),
      s({ path: '/sales/feedback', labelKey: 'nav.visitFeedback', label: '拜访反馈' }),
      s({ path: '/sales/coverage', labelKey: 'nav.coverage', label: '覆盖分管' }),
      s({ path: '/collection', labelKey: 'nav.collection', label: '数据采集', end: end('/collection') }),
      p({ path: '/collection/todos', labelKey: 'nav.collectionTodos', label: '待办任务' }),
      s({ path: '/sales/scoring', labelKey: 'nav.scoring', label: '积分管理' }),
      s({ path: '/sales/matrix', labelKey: 'nav.matrix', label: '矩阵看板' }),
      s({ path: '/sales/roi', labelKey: 'nav.roi', label: 'ROI 分析' }),
    ],
  },
  {
    id: 'learn',
    titleKey: 'nav.group.learn',
    items: [
      p({ path: '/training', labelKey: 'nav.training', label: '培训总览', end: end('/training') }),
      p({ path: '/training/onboarding', labelKey: 'nav.onboardingChat', label: '对话式上岗备案' }),
      p({ path: '/training/my-learning', labelKey: 'nav.myLearning', label: '我的学习' }),
      s({ path: '/training/paths', labelKey: 'nav.paths', label: '学习路径' }),
      s({ path: '/training/courses', labelKey: 'nav.courses', label: '课程中心' }),
      s({ path: '/training/exams', labelKey: 'nav.exams', label: '考试中心' }),
      p({ path: '/training/practice', labelKey: 'nav.practice', label: '场景演练' }),
      s({ path: '/training/certificates', labelKey: 'nav.certificates', label: '我的证书' }),
      s({ path: '/training/experience', labelKey: 'nav.experience', label: '经验值排行' }),
      s({ path: '/training/personas', labelKey: 'nav.personas', label: '角色画像库' }),
      s({ path: '/training/scenario-parse', labelKey: 'nav.scenarioParse', label: '剧本解析' }),
      s({ path: '/training/ppt-speech', labelKey: 'nav.pptSpeech', label: 'PPT 演讲' }),
      s({ path: '/training/activities', labelKey: 'nav.activities', label: '培训活动' }),
      s({ path: '/training/effect', labelKey: 'nav.trainingEffect', label: '培训效果归因' }),
    ],
  },
  {
    id: 'decision',
    titleKey: 'nav.group.decision',
    items: [
      p({ path: '/decision', labelKey: 'nav.decision', label: '决策总览', end: end('/decision') }),
      p({ path: '/decision/diagnosis', labelKey: 'nav.decisionDiagnosis', label: '统一诊断' }),
      s({ path: '/decision/loop', labelKey: 'nav.decisionLoop', label: '诊断闭环' }),
      s({ path: '/decision/followup', labelKey: 'nav.decisionFollowup', label: '随访闭环' }),
      s({ path: '/decision/paradigms', labelKey: 'nav.decisionParadigms', label: '范式库' }),
      s({ path: '/decision/executions', labelKey: 'nav.decisionExecutions', label: '效果追踪' }),
      s({ path: '/decision/kpi', labelKey: 'nav.decisionKpi', label: 'KPI 监控' }),
      s({ path: '/decision/attribution', labelKey: 'nav.decisionAttribution', label: '归因分析' }),
      s({ path: '/decision/simulation', labelKey: 'nav.decisionSimulation', label: '模拟推演' }),
      p({ path: '/decision/alerts', labelKey: 'nav.decisionAlerts', label: '预警中心' }),
    ],
  },
  {
    id: 'collab',
    titleKey: 'nav.group.collab',
    items: [
      p({ path: '/collab', labelKey: 'nav.collab', label: '协同总览', end: end('/collab') }),
      p({ path: '/collab/academic-chat', labelKey: 'nav.academicChat', label: '对话式学术活动' }),
      p({ path: '/collab/academic-board', labelKey: 'nav.academicBoard', label: '学术三流看板' }),
      s({ path: '/collab/tasks', labelKey: 'nav.collabTasks', label: '任务管理' }),
      p({ path: '/collab/approvals', labelKey: 'nav.collabApprovals', label: '审批中心' }),
      s({ path: '/collab/announcements', labelKey: 'nav.collabAnnouncements', label: '公告栏' }),
      p({ path: '/knowledge', labelKey: 'nav.knowledge', label: '知识总览', end: end('/knowledge') }),
      s({ path: '/knowledge/documents', labelKey: 'nav.knowledgeDocuments', label: '知识文档' }),
      s({ path: '/knowledge/faqs', labelKey: 'nav.knowledgeFaqs', label: '常见问题' }),
    ],
  },
  {
    id: 'relationship',
    titleKey: 'nav.group.relationship',
    items: [
      p({ path: '/crm', labelKey: 'nav.crm', label: '客户关系' }),
      p({ path: '/cfm', labelKey: 'nav.cfm', label: '会议论坛' }),
      p({ path: '/tools', labelKey: 'nav.tools', label: '内容工具' }),
    ],
  },
  {
    id: 'compliance',
    titleKey: 'nav.group.compliance',
    items: [
      p({ path: '/compliance', labelKey: 'nav.complianceOverview', label: '合规总览', end: end('/compliance') }),
      p({ path: '/compliance/profile', labelKey: 'nav.complianceProfile', label: '代表备案' }),
      s({ path: '/compliance/commitment', labelKey: 'nav.complianceCommitment', label: '合规承诺' }),
      p({ path: '/compliance/violation', labelKey: 'nav.complianceViolation', label: '违规管理' }),
      p({ path: '/compliance/audit-pack', labelKey: 'nav.complianceAuditPack', label: '稽查包导出' }),
      s({ path: '/compliance/forbidden', labelKey: 'nav.complianceForbidden', label: '禁止行为' }),
      s({ path: '/compliance/disclosure', labelKey: 'nav.complianceDisclosure', label: '合规公示' }),
      s({ path: '/compliance/submission', labelKey: 'nav.complianceSubmission', label: '监管报送' }),
      s({ path: '/compliance/audit', labelKey: 'nav.complianceAudit', label: '年度审计' }),
    ],
  },
  {
    id: 'moreTools',
    titleKey: 'nav.group.moreTools',
    items: [
      p({ path: '/platform', labelKey: 'nav.platform', label: '平台管理' }),
      s({ path: '/mdm', labelKey: 'nav.mdm', label: '主数据' }),
      s({ path: '/ontology', labelKey: 'nav.ontology', label: '本体图谱' }),
      p({ path: '/settings', labelKey: 'nav.settings', label: '设置' }),
      s({ path: '/audit', labelKey: 'nav.audit', label: '审计' }),
      s({ path: '/observability', labelKey: 'nav.observability', label: '可观测' }),
    ],
  },
]

/** 侧栏：全量平铺；分组默认展开策略由 Sidebar 控制 */
export const sidebarNavGroups: NavGroup[] = navGroups.filter((g) => g.items.length > 0)

/** 扁平全量（⌘K / 域总览） */
export const allNavItems: NavItem[] = navGroups.flatMap((g) =>
  g.items.map((item) => ({ ...item, tier: item.tier ?? 'primary' })),
)

/** 按 path 前缀取某域全部入口（含总览自身时可选 excludeExact） */
export function getNavItemsByPrefixes(
  prefixes: string[],
  options?: { excludeExact?: string[] },
): NavItem[] {
  const exclude = new Set(options?.excludeExact ?? [])
  return allNavItems.filter((item) => {
    if (exclude.has(item.path)) return false
    return prefixes.some(
      (prefix) => item.path === prefix || item.path.startsWith(`${prefix}/`),
    )
  })
}

export default navGroups
