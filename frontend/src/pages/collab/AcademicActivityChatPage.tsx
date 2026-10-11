/**
 * 学术推广活动对话式页面（academic-activity-lifecycle 工作流）
 */
import {
  Lock, ClipboardList, FileCheck, Stamp, UserCheck,
  Receipt, Archive, Sparkles, MapPin, Calendar, Users,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '模板拉取',
    description: '活动模板与必填项',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '活动草稿',
    description: '标题/类型/时间/地点/参与方',
    gates: ['G3'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '活动立项',
    description: '创建活动 + 22 项规则校验',
    gates: ['G4'],
    icon: <FileCheck className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '审批通过',
    description: '推进至 approved',
    gates: ['G5'],
    icon: <Stamp className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: '签到证据',
    description: '三流合一 · 签到流',
    gates: ['G6'],
    icon: <UserCheck className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '费用核销',
    description: '三流合一 · 费用流',
    gates: ['G7'],
    icon: <Receipt className="w-4 h-4" />,
  },
  {
    name: 'Step7',
    label: '反馈归档',
    description: '不良反应收集 + 归档',
    gates: ['G8'],
    icon: <Archive className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '活动模板已拉取' },
  { id: 'G3', label: '活动草稿已确认' },
  { id: 'G4', label: '活动已立项' },
  { id: 'G5', label: '审批已通过' },
  { id: 'G6', label: '签到证据已提交' },
  { id: 'G7', label: '费用核销已提交' },
  { id: 'G8', label: '反馈已归档' },
]

const QUICK_STARTERS = [
  '发起一场学术讲座',
  '为心内科组织科室会，下周三下午',
  '提交本次活动签到证据',
  '录入费用并完成反馈归档',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderAcademicDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const title = safeStr(safeGet(collection, 'title'))
    if (title)
      items.push({ label: '活动标题', value: title, icon: <Sparkles className="w-3.5 h-3.5" /> })
    const when = safeStr(safeGet(collection, 'planned_at') ?? safeGet(collection, 'time'))
    if (when)
      items.push({ label: '计划时间', value: when, icon: <Calendar className="w-3.5 h-3.5" /> })
    const loc = safeStr(safeGet(collection, 'location'))
    if (loc)
      items.push({ label: '地点', value: loc, icon: <MapPin className="w-3.5 h-3.5" /> })
  }

  if (draftState.scenario_id) {
    items.push({
      label: '活动 ID',
      value: `#${draftState.scenario_id}`,
      icon: <FileCheck className="w-3.5 h-3.5" />,
    })
  }

  const knowledge = safeGet<Record<string, unknown>>(draftState, 'knowledge')
  if (knowledge) {
    const checkin = Number(safeGet(knowledge, 'checkin_count') ?? 0)
    const expense = Number(safeGet(knowledge, 'expense_count') ?? 0)
    items.push({
      label: '三流进度',
      value: `签到 ${checkin} · 费用 ${expense}`,
      icon: <Users className="w-3.5 h-3.5" />,
    })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  if (titleBg?.approved) {
    items.push({
      label: '审批',
      value: '已通过',
      icon: <Stamp className="w-3.5 h-3.5" />,
    })
  }

  const gates = safeArr<string>(draftState.gates_passed)
  if (gates.length)
    items.push({
      label: '已过门禁',
      value: gates.join(', '),
      icon: <Lock className="w-3.5 h-3.5" />,
    })

  return items
}

export default function AcademicActivityChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式学术活动"
      pageDescription="AI 原生 · 门禁驱动 · 协议/签到/费用三流合一（第 19-22 条）"
      breadcrumbs={[{ label: '协同办公' }, { label: '对话式学术活动' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过对话完成学术推广活动全生命周期"
      emptyStateSubtitle="AI 将引导：模板 → 立项 → 审批 → 签到 → 费用 → 反馈归档"
      inputPlaceholder={(isDone) =>
        isDone
          ? '活动已归档，输入「再办一场」开始新流程...'
          : '描述活动需求，或点击快捷语开始...'
      }
      doneMessage="学术活动已完成归档"
      draftFieldRenderer={renderAcademicDraft}
      finalGateId="G8"
      pageKey="academic-activity-lifecycle"
      intentOverride="academic_activity"
    />
  )
}
