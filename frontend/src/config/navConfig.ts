// F-重构：角色/工作流导向的导航配置（单一事实来源）
// 侧边栏分组以「医药代表日常工作流」组织，技术模块收敛到「更多工具」折叠区。
// 新增/调整菜单只需改这里，无需动 Sidebar 组件逻辑。
import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  path: string
  labelKey: string // i18n key，位于 zh-CN.json / en.json 的 nav.* 下
  label: string // i18n 缺失时的中文兜底
  end?: boolean // react-router NavLink 的 end 匹配（列表型路由需精确匹配根路径）
  icon?: LucideIcon // 可选，缺省由 navIconMap 按 path 兜底
}

export interface NavGroup {
  id: string
  titleKey: string // 分组的 i18n key（nav.group.*）
  items: NavItem[]
}

// 列表型根路由：其下还有子路由，NavLink 需精确匹配根路径以避免全部高亮
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

export const navGroups: NavGroup[] = [
  {
    id: 'today',
    titleKey: 'nav.group.today',
    items: [
      { path: '/portal', labelKey: 'nav.portal', label: '门户', end: end('/portal') },
      { path: '/profile', labelKey: 'nav.profile', label: '我的画像', end: end('/profile') },
      { path: '/notification-center', labelKey: 'nav.notificationCenter', label: '通知中心' },
      { path: '/ai', labelKey: 'nav.ai', label: 'AI 助手' },
    ],
  },
  {
    id: 'visit',
    titleKey: 'nav.group.visit',
    items: [
      { path: '/sales', labelKey: 'nav.sales', label: '销售总览', end: end('/sales') },
      { path: '/sales/plans', labelKey: 'nav.visitPlans', label: '拜访计划' },
      { path: '/sales/records', labelKey: 'nav.visitRecords', label: '拜访记录' },
      { path: '/sales/feedback', labelKey: 'nav.visitFeedback', label: '拜访反馈' },
      { path: '/sales/coverage', labelKey: 'nav.coverage', label: '覆盖分管' },
      { path: '/collection', labelKey: 'nav.collection', label: '数据采集', end: end('/collection') },
      { path: '/collection/todos', labelKey: 'nav.collectionTodos', label: '待办任务' },
      { path: '/sales/scoring', labelKey: 'nav.scoring', label: '积分管理' },
      { path: '/sales/matrix', labelKey: 'nav.matrix', label: '矩阵看板' },
      { path: '/sales/roi', labelKey: 'nav.roi', label: 'ROI 分析' },
    ],
  },
  {
    id: 'learn',
    titleKey: 'nav.group.learn',
    items: [
      { path: '/training', labelKey: 'nav.training', label: '培训总览', end: end('/training') },
      { path: '/training/my-learning', labelKey: 'nav.myLearning', label: '我的学习' },
      { path: '/training/paths', labelKey: 'nav.paths', label: '学习路径' },
      { path: '/training/courses', labelKey: 'nav.courses', label: '课程中心' },
      { path: '/training/exams', labelKey: 'nav.exams', label: '考试中心' },
      { path: '/training/practice', labelKey: 'nav.practice', label: '场景演练' },
      { path: '/training/certificates', labelKey: 'nav.certificates', label: '我的证书' },
      { path: '/training/experience', labelKey: 'nav.experience', label: '经验值排行' },
      { path: '/training/personas', labelKey: 'nav.personas', label: '角色画像库' },
      { path: '/training/scenario-parse', labelKey: 'nav.scenarioParse', label: '剧本解析' },
      { path: '/training/ppt-speech', labelKey: 'nav.pptSpeech', label: 'PPT 演讲' },
      { path: '/training/activities', labelKey: 'nav.activities', label: '培训活动' },
      { path: '/training/effect', labelKey: 'nav.trainingEffect', label: '培训效果归因' },
    ],
  },
  {
    id: 'decision',
    titleKey: 'nav.group.decision',
    items: [
      { path: '/decision', labelKey: 'nav.decision', label: '决策总览', end: end('/decision') },
      { path: '/decision/diagnosis', labelKey: 'nav.decisionDiagnosis', label: '统一诊断' },
      { path: '/decision/loop', labelKey: 'nav.decisionLoop', label: '诊断闭环' },
      { path: '/decision/followup', labelKey: 'nav.decisionFollowup', label: '随访闭环' },
      { path: '/decision/paradigms', labelKey: 'nav.decisionParadigms', label: '范式库' },
      { path: '/decision/executions', labelKey: 'nav.decisionExecutions', label: '效果追踪' },
      { path: '/decision/kpi', labelKey: 'nav.decisionKpi', label: 'KPI 监控' },
      { path: '/decision/attribution', labelKey: 'nav.decisionAttribution', label: '归因分析' },
      { path: '/decision/simulation', labelKey: 'nav.decisionSimulation', label: '模拟推演' },
      { path: '/decision/alerts', labelKey: 'nav.decisionAlerts', label: '预警中心' },
    ],
  },
  {
    id: 'collab',
    titleKey: 'nav.group.collab',
    items: [
      { path: '/collab', labelKey: 'nav.collab', label: '协同总览', end: end('/collab') },
      { path: '/collab/tasks', labelKey: 'nav.collabTasks', label: '任务管理' },
      { path: '/collab/approvals', labelKey: 'nav.collabApprovals', label: '审批中心' },
      { path: '/collab/announcements', labelKey: 'nav.collabAnnouncements', label: '公告栏' },
      { path: '/knowledge', labelKey: 'nav.knowledge', label: '知识总览', end: end('/knowledge') },
      { path: '/knowledge/documents', labelKey: 'nav.knowledgeDocuments', label: '知识文档' },
      { path: '/knowledge/faqs', labelKey: 'nav.knowledgeFaqs', label: '常见问题' },
    ],
  },
  {
    id: 'relationship',
    titleKey: 'nav.group.relationship',
    items: [
      { path: '/crm', labelKey: 'nav.crm', label: '客户关系' },
      { path: '/cfm', labelKey: 'nav.cfm', label: '会议论坛' },
      { path: '/tools', labelKey: 'nav.tools', label: '内容工具' },
    ],
  },
  {
    id: 'compliance',
    titleKey: 'nav.group.compliance',
    items: [
      { path: '/compliance', labelKey: 'nav.complianceOverview', label: '合规总览', end: end('/compliance') },
      { path: '/compliance/profile', labelKey: 'nav.complianceProfile', label: '代表备案' },
      { path: '/compliance/commitment', labelKey: 'nav.complianceCommitment', label: '合规承诺' },
      { path: '/compliance/violation', labelKey: 'nav.complianceViolation', label: '违规管理' },
      { path: '/compliance/forbidden', labelKey: 'nav.complianceForbidden', label: '禁止行为' },
      { path: '/compliance/disclosure', labelKey: 'nav.complianceDisclosure', label: '合规公示' },
      { path: '/compliance/submission', labelKey: 'nav.complianceSubmission', label: '监管报送' },
      { path: '/compliance/audit', labelKey: 'nav.complianceAudit', label: '年度审计' },
    ],
  },
  {
    id: 'moreTools',
    titleKey: 'nav.group.moreTools',
    items: [
      { path: '/platform', labelKey: 'nav.platform', label: '平台管理' },
      { path: '/mdm', labelKey: 'nav.mdm', label: '主数据' },
      { path: '/ontology', labelKey: 'nav.ontology', label: '本体图谱' },
      { path: '/settings', labelKey: 'nav.settings', label: '设置' },
      { path: '/audit', labelKey: 'nav.audit', label: '审计' },
      { path: '/observability', labelKey: 'nav.observability', label: '可观测' },
    ],
  },
]

export default navGroups
