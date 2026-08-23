/**
 * 报告生成对话式页面（report-builder 工作流）
 *
 * 复用 WorkflowChatLayout 通用组件，仅提供 report-builder 特有配置：
 * - 7 步骤 + G1-G8 门禁
 * - 草稿字段渲染：数据源 / 范围 / 大纲 / 数据 / 正文 / 审阅
 */
import {
  Lock, ClipboardList, FileText, Database, Activity,
  BarChart3, ListChecks, Send,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '鉴权与数据源',
    description: '加载租户/用户身份，拉取报告数据源（周报/KPI/培训）',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '范围采集',
    description: '采集报告类型（周报/月报/季度）+ 时间范围',
    gates: ['G3'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '大纲生成',
    description: '生成报告大纲（章节结构）',
    gates: ['G4'],
    icon: <ListChecks className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '数据聚合',
    description: '聚合 KPI / 拜访 / 培训 / 积分数据',
    gates: ['G5'],
    icon: <Database className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: '正文生成',
    description: '基于大纲和数据生成报告正文',
    gates: ['G6'],
    icon: <FileText className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '审阅',
    description: 'AI 自检报告质量（完整性/准确性/可读性）',
    gates: ['G7'],
    icon: <Activity className="w-4 h-4" />,
  },
  {
    name: 'Step7',
    label: '落库外发',
    description: '报告入库（importance=12）+ 外发链接',
    gates: ['G8'],
    icon: <Send className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '数据源已加载' },
  { id: 'G3', label: '报告范围已采集' },
  { id: 'G4', label: '报告大纲已生成' },
  { id: 'G5', label: '数据已聚合' },
  { id: 'G6', label: '报告正文已生成' },
  { id: 'G7', label: '报告质量已审阅通过' },
  { id: 'G8', label: '报告已落库并外发' },
]

const QUICK_STARTERS = [
  '生成本周工作周报',
  '为我生成本月销售业绩月报',
  '生成本季度培训效果季度报告',
  '汇总本月覆盖与拜访情况生成报告',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderReportDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const config = safeGet<Record<string, unknown>>(draftState, 'config')
  if (config) {
    const sources = safeArr<Record<string, unknown>>(safeGet(config, 'data_sources'))
    if (sources.length)
      items.push({
        label: '数据源',
        value: `${sources.length} 个`,
        icon: <Database className="w-3.5 h-3.5" />,
      })
  }

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const parts: string[] = []
    const reportType = safeStr(safeGet(collection, 'report_type'))
    const period = safeStr(safeGet(collection, 'period'))
    const startDate = safeStr(safeGet(collection, 'start_date'))
    const endDate = safeStr(safeGet(collection, 'end_date'))
    if (reportType) parts.push(`类型=${reportType}`)
    if (period) parts.push(`周期=${period}`)
    if (startDate) parts.push(`起=${startDate}`)
    if (endDate) parts.push(`止=${endDate}`)
    if (parts.length)
      items.push({
        label: '报告范围',
        value: parts.join(' / '),
        icon: <ClipboardList className="w-3.5 h-3.5" />,
      })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  if (titleBg) {
    const outline = safeArr<Record<string, unknown>>(safeGet(titleBg, 'outline'))
    if (outline.length)
      items.push({
        label: '大纲章节',
        value: `${outline.length} 章`,
        icon: <ListChecks className="w-3.5 h-3.5" />,
      })

    const aggregatedData = safeGet<Record<string, unknown>>(titleBg, 'aggregated_data')
    if (aggregatedData) {
      const kpi = safeGet(aggregatedData, 'kpi_summary')
      const visits = safeGet(aggregatedData, 'visit_summary')
      const parts: string[] = []
      if (kpi != null) parts.push('KPI')
      if (visits != null) parts.push('拜访')
      if (parts.length)
        items.push({
          label: '已聚合数据',
          value: parts.join(' / '),
          icon: <BarChart3 className="w-3.5 h-3.5" />,
        })
    }
  }

  const knowledge = safeGet<Record<string, unknown>>(draftState, 'knowledge')
  if (knowledge) {
    const content = safeStr(safeGet(knowledge, 'content'))
    if (content)
      items.push({
        label: '报告正文',
        value: content.length > 60 ? `${content.length} 字` : content,
        icon: <FileText className="w-3.5 h-3.5" />,
      })

    const quality = safeGet<Record<string, unknown>>(knowledge, 'quality')
    if (quality) {
      const completeness = safeGet(quality, 'completeness')
      const accuracy = safeGet(quality, 'accuracy')
      const parts: string[] = []
      if (completeness != null) parts.push(`完整度=${completeness}`)
      if (accuracy != null) parts.push(`准确度=${accuracy}`)
      if (parts.length)
        items.push({
          label: '质量评分',
          value: parts.join(' / '),
          icon: <Activity className="w-3.5 h-3.5" />,
        })
    }
  }

  const contextPayload = safeGet<Record<string, unknown>>(draftState, 'context_payload')
  if (contextPayload) {
    const reportId = safeGet(contextPayload, 'report_id')
    const outsendLink = safeStr(safeGet(contextPayload, 'outsend_link'))
    const parts: string[] = []
    if (reportId != null) parts.push(`报告ID=${reportId}`)
    if (outsendLink) parts.push('已外发')
    if (parts.length)
      items.push({
        label: '落库外发',
        value: parts.join(' / '),
        icon: <Send className="w-3.5 h-3.5" />,
      })
  }

  return items
}

export default function ReportBuilderChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式报告生成工作流"
      pageDescription="AI 原生 · 门禁驱动工作流 · 数据聚合与正文生成"
      breadcrumbs={[{ label: '协同办公' }, { label: '对话式报告生成' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过自然语言对话生成报告"
      emptyStateSubtitle="AI 将引导您完成 数据源 → 范围采集 → 大纲生成 → 数据聚合 → 正文生成 → 审阅 → 落库外发"
      inputPlaceholder={(isDone) =>
        isDone
          ? '报告已生成，输入"再生成一份"开始新工作流...'
          : '描述报告需求，AI 将引导你逐步完成...'
      }
      doneMessage="报告生成工作流已完成"
      draftFieldRenderer={renderReportDraft}
      finalGateId="G8"
    />
  )
}
