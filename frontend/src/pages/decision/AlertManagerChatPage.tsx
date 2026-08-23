/**
 * 预警处置对话式页面（alert-manager 工作流）
 *
 * 复用 WorkflowChatLayout 通用组件，仅提供 alert-manager 特有配置：
 * - 6 步骤 + G1-G7 门禁
 * - 草稿字段渲染：预警批次 / 过滤条件 / 元数据 / 根因 / 建议
 */
import {
  Lock, ClipboardList, FileText, Lightbulb,
  CheckCircle2, Bell, Filter, AlertTriangle, Target,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '鉴权与预警拉取',
    description: '加载租户/用户身份，拉取待处置预警列表',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '范围过滤',
    description: '采集过滤条件（类型/严重等级/时间范围）',
    gates: ['G3'],
    icon: <Filter className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '根因分析',
    description: '对每条预警做根因分析（关联覆盖/拜访/培训缺口）',
    gates: ['G4'],
    icon: <AlertTriangle className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '建议生成',
    description: '生成处置建议（派单/跟进/培训触发）',
    gates: ['G5'],
    icon: <Lightbulb className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: '用户确认',
    description: '用户审核建议并确认处置方案',
    gates: ['G6'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '派单落库',
    description: '生成协同待办任务并落库',
    gates: ['G7'],
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '预警批次已拉取' },
  { id: 'G3', label: '过滤条件已采集' },
  { id: 'G4', label: '根因分析完成' },
  { id: 'G5', label: '处置建议已生成' },
  { id: 'G6', label: '用户已确认处置方案' },
  { id: 'G7', label: '待办任务已派发落库' },
]

const QUICK_STARTERS = [
  '拉取本周预警并生成处置建议',
  '分析覆盖率下降的高优预警根因',
  '为所有高严重度预警派发跟进任务',
  '汇总本月预警处置情况并生成报告',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderAlertDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const config = safeGet<Record<string, unknown>>(draftState, 'config')
  if (config) {
    const alertsBatch = safeArr<Record<string, unknown>>(safeGet(config, 'alerts_batch'))
    if (alertsBatch.length)
      items.push({
        label: '预警批次',
        value: `${alertsBatch.length} 条`,
        icon: <Bell className="w-3.5 h-3.5" />,
      })
  }

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const parts: string[] = []
    const alertType = safeStr(safeGet(collection, 'alert_type'))
    const severity = safeStr(safeGet(collection, 'severity'))
    const dateRange = safeStr(safeGet(collection, 'date_range'))
    if (alertType) parts.push(`类型=${alertType}`)
    if (severity) parts.push(`等级=${severity}`)
    if (dateRange) parts.push(`时间=${dateRange}`)
    if (parts.length)
      items.push({
        label: '过滤条件',
        value: parts.join(' / '),
        icon: <Filter className="w-3.5 h-3.5" />,
      })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  if (titleBg) {
    const metadata = safeArr<Record<string, unknown>>(safeGet(titleBg, 'metadata'))
    if (metadata.length)
      items.push({
        label: '预警元数据',
        value: `${metadata.length} 条已合并`,
        icon: <FileText className="w-3.5 h-3.5" />,
      })
  }

  const knowledge = safeGet<Record<string, unknown>>(draftState, 'knowledge')
  if (knowledge) {
    const rootCauses = safeArr<Record<string, unknown>>(safeGet(knowledge, 'root_causes'))
    if (rootCauses.length)
      items.push({
        label: '根因分析',
        value: `${rootCauses.length} 条已分析`,
        icon: <AlertTriangle className="w-3.5 h-3.5" />,
      })

    const suggestions = safeArr<Record<string, unknown>>(safeGet(knowledge, 'suggestions'))
    if (suggestions.length)
      items.push({
        label: '处置建议',
        value: `${suggestions.length} 条建议`,
        icon: <Lightbulb className="w-3.5 h-3.5" />,
      })

    const confirmed = safeGet(knowledge, 'confirmed')
    if (confirmed)
      items.push({
        label: '确认状态',
        value: '用户已确认',
        icon: <CheckCircle2 className="w-3.5 h-3.5" />,
      })
  }

  const contextPayload = safeGet<Record<string, unknown>>(draftState, 'context_payload')
  if (contextPayload) {
    const taskIds = safeArr<unknown>(safeGet(contextPayload, 'task_ids'))
    if (taskIds.length)
      items.push({
        label: '已派发任务',
        value: `${taskIds.length} 个待办`,
        icon: <Target className="w-3.5 h-3.5" />,
      })
  }

  return items
}

export default function AlertManagerChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式预警处置工作流"
      pageDescription="AI 原生 · 门禁驱动工作流 · 预警根因分析与派单"
      breadcrumbs={[{ label: '决策支持' }, { label: '对话式预警处置' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过自然语言对话处置预警"
      emptyStateSubtitle="AI 将引导您完成 预警拉取 → 范围过滤 → 根因分析 → 建议生成 → 用户确认 → 派单落库"
      inputPlaceholder={(isDone) =>
        isDone
          ? '预警处置已完成，输入"再处置一批"开始新工作流...'
          : '描述预警处置需求，AI 将引导你逐步完成...'
      }
      doneMessage="预警处置工作流已完成"
      draftFieldRenderer={renderAlertDraft}
      finalGateId="G7"
    />
  )
}
