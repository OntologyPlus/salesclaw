/**
 * 拜访计划创建对话式页面（visit-planner 工作流）
 *
 * 复用 WorkflowChatLayout 通用组件，仅提供 visit-planner 特有配置：
 * - 7 步骤 + G1-G8 门禁
 * - 草稿字段渲染：目标医生 / 拜访目的 / 计划标题 / 优先级 / Payload
 */
import {
  Lock, ClipboardList, FileText, Target, Users, Tag,
  Lightbulb, Database, CheckCircle2, Sparkles, Calendar,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '鉴权与配置',
    description: '拉取周期/辖区/覆盖摘要',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '采集目标医生',
    description: '采集目标医生列表 + 拜访目的',
    gates: ['G3'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '计划标题与概述',
    description: '生成计划标题 + 计划概述，用户确认',
    gates: ['G4'],
    icon: <FileText className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '优先级优化',
    description: '基于覆盖+历史拜访计算优先级排序',
    gates: ['G5'],
    icon: <Target className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: 'Payload 生成',
    description: '生成计划 Payload（planned_date + visit_type）',
    gates: ['G6'],
    icon: <Database className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '提交确认',
    description: '用户确认提交，落库 VisitPlan',
    gates: ['G7'],
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
  {
    name: 'Step7',
    label: '完成',
    description: '计划已创建，返回 plan_id',
    gates: ['G8'],
    icon: <Sparkles className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '周期/辖区/覆盖摘要已加载' },
  { id: 'G3', label: '目标医生与拜访目的已采集' },
  { id: 'G4', label: '计划标题与概述已确认' },
  { id: 'G5', label: '优先级排序完成' },
  { id: 'G6', label: '计划 Payload 就绪' },
  { id: 'G7', label: '用户已确认提交' },
  { id: 'G8', label: '计划已落库' },
]

const QUICK_STARTERS = [
  '生成本周拜访计划',
  '为三甲医院重点医生安排拜访',
  '优化下周覆盖缺口',
  '为心内科主任安排学术拜访',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderVisitDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const config = safeGet<Record<string, unknown>>(draftState, 'config')
  if (config) {
    const period = safeStr(safeGet(config, 'period'))
    if (period)
      items.push({ label: '计划周期', value: period, icon: <Calendar className="w-3.5 h-3.5" /> })
    const coverageSummary = safeStr(safeGet(config, 'coverage_summary'))
    if (coverageSummary)
      items.push({
        label: '覆盖摘要',
        value: coverageSummary.length > 80 ? coverageSummary.slice(0, 80) + '...' : coverageSummary,
        icon: <Database className="w-3.5 h-3.5" />,
      })
  }

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const targetDoctors = safeArr<Record<string, unknown>>(safeGet(collection, 'target_doctors'))
    if (targetDoctors.length)
      items.push({
        label: '目标医生',
        value: `${targetDoctors.length} 位医生`,
        icon: <Users className="w-3.5 h-3.5" />,
      })
    const visitPurposes = safeArr<string>(safeGet(collection, 'visit_purposes'))
    if (visitPurposes.length)
      items.push({
        label: '拜访目的',
        value: visitPurposes.join(' / '),
        icon: <Lightbulb className="w-3.5 h-3.5" />,
      })
    const priorityComputed = safeGet<boolean>(collection, 'priority_computed')
    if (priorityComputed)
      items.push({
        label: '优先级',
        value: '已计算完成',
        icon: <Target className="w-3.5 h-3.5" />,
      })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  if (titleBg) {
    const planTitle = safeStr(safeGet(titleBg, 'plan_title'))
    if (planTitle)
      items.push({ label: '计划标题', value: planTitle, icon: <FileText className="w-3.5 h-3.5" /> })
    const planSummary = safeStr(safeGet(titleBg, 'plan_summary'))
    if (planSummary)
      items.push({
        label: '计划概述',
        value: planSummary.length > 80 ? planSummary.slice(0, 80) + '...' : planSummary,
        icon: <FileText className="w-3.5 h-3.5" />,
      })
  }

  const contextPayload = safeGet<Record<string, unknown>>(draftState, 'context_payload')
  if (contextPayload) {
    const ready = safeGet<boolean>(contextPayload, 'ready')
    if (ready)
      items.push({
        label: '计划 Payload',
        value: '已就绪',
        icon: <Database className="w-3.5 h-3.5" />,
      })
  }

  if (draftState.scenario_id) {
    items.push({
      label: '计划 ID',
      value: `#${draftState.scenario_id}`,
      icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    })
  }

  return items
}

export default function VisitPlanChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式拜访计划创建"
      pageDescription="AI 原生 · 门禁驱动工作流 · 自然语言引导采集与落库"
      breadcrumbs={[{ label: '销售执行' }, { label: '对话式拜访计划创建' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过自然语言对话创建拜访计划"
      emptyStateSubtitle="AI 将引导您完成 采集目标医生 → 计划标题 → 优先级优化 → Payload 生成 → 落库"
      inputPlaceholder={(isDone) =>
        isDone
          ? '计划已创建，输入"再创建一个"开始新工作流...'
          : '描述拜访需求，AI 将引导你逐步完成...'
      }
      doneMessage="拜访计划已成功创建"
      draftFieldRenderer={renderVisitDraft}
      finalGateId="G8"
    />
  )
}
