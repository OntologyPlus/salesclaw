/**
 * 会议组织对话式页面（meeting-organizer 工作流）
 *
 * 复用 WorkflowChatLayout 通用组件，仅提供 meeting-organizer 特有配置：
 * - 6 步骤 + G1-G7 门禁
 * - 草稿字段渲染：参会候选 / 议程 / 通知 / 材料 / 派发
 */
import {
  Lock, ClipboardList, Bell, Paperclip,
  CheckCircle2, Users, Calendar, Send,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '鉴权与参会候选',
    description: '加载租户/用户身份，拉取参会人员候选名单',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '议程采集',
    description: '采集议程主题 / 时间 / 地点 / 时长',
    gates: ['G3'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '通知生成',
    description: '生成会议通知（含议程+参会人+地点+时间）',
    gates: ['G4'],
    icon: <Bell className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '材料关联',
    description: '关联会议材料（文档/演示/参考资料）',
    gates: ['G5'],
    icon: <Paperclip className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: '用户确认',
    description: '用户审核通知并确认发送',
    gates: ['G6'],
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '落库+派发',
    description: '会议记录入库 + 通知派发',
    gates: ['G7'],
    icon: <Send className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '参会候选名单已拉取' },
  { id: 'G3', label: '议程已采集' },
  { id: 'G4', label: '会议通知已生成' },
  { id: 'G5', label: '会议材料已关联' },
  { id: 'G6', label: '用户已确认发送' },
  { id: 'G7', label: '会议已落库并派发' },
]

const QUICK_STARTERS = [
  '组织下周一产品培训会议',
  '为新产品上市组织区域学术研讨会',
  '安排本月销售周例会并通知全员',
  '组织季度 KOL 交流会议',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderMeetingDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const config = safeGet<Record<string, unknown>>(draftState, 'config')
  if (config) {
    const attendees = safeArr<Record<string, unknown>>(safeGet(config, 'attendees'))
    if (attendees.length)
      items.push({
        label: '参会候选',
        value: `${attendees.length} 人`,
        icon: <Users className="w-3.5 h-3.5" />,
      })
  }

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const parts: string[] = []
    const topic = safeStr(safeGet(collection, 'topic'))
    const date = safeStr(safeGet(collection, 'meeting_date'))
    const location = safeStr(safeGet(collection, 'location'))
    const duration = safeGet(collection, 'duration_minutes')
    if (topic) parts.push(`主题=${topic}`)
    if (date) parts.push(`时间=${date}`)
    if (location) parts.push(`地点=${location}`)
    if (duration != null) parts.push(`时长=${duration}分`)
    if (parts.length)
      items.push({
        label: '议程',
        value: parts.join(' / '),
        icon: <Calendar className="w-3.5 h-3.5" />,
      })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  if (titleBg) {
    const notice = safeStr(safeGet(titleBg, 'notice_text'))
    if (notice)
      items.push({
        label: '通知内容',
        value: notice.length > 60 ? notice.slice(0, 60) + '...' : notice,
        icon: <Bell className="w-3.5 h-3.5" />,
      })

    const materials = safeArr<Record<string, unknown>>(safeGet(titleBg, 'materials'))
    if (materials.length)
      items.push({
        label: '会议材料',
        value: `${materials.length} 份`,
        icon: <Paperclip className="w-3.5 h-3.5" />,
      })

    const confirmed = safeGet(titleBg, 'confirmed')
    if (confirmed)
      items.push({
        label: '确认状态',
        value: '用户已确认',
        icon: <CheckCircle2 className="w-3.5 h-3.5" />,
      })
  }

  const contextPayload = safeGet<Record<string, unknown>>(draftState, 'context_payload')
  if (contextPayload) {
    const meetingId = safeGet(contextPayload, 'meeting_id')
    const dispatched = safeGet(contextPayload, 'dispatched_count')
    if (meetingId != null || dispatched != null) {
      const parts: string[] = []
      if (meetingId != null) parts.push(`会议ID=${meetingId}`)
      if (dispatched != null) parts.push(`已派发=${dispatched}`)
      items.push({
        label: '派发结果',
        value: parts.join(' / '),
        icon: <Send className="w-3.5 h-3.5" />,
      })
    }
  }

  return items
}

export default function MeetingOrganizerChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式会议组织工作流"
      pageDescription="AI 原生 · 门禁驱动工作流 · 议程采集与通知派发"
      breadcrumbs={[{ label: '协同办公' }, { label: '对话式会议组织' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过自然语言对话组织会议"
      emptyStateSubtitle="AI 将引导您完成 参会候选 → 议程采集 → 通知生成 → 材料关联 → 用户确认 → 落库派发"
      inputPlaceholder={(isDone) =>
        isDone
          ? '会议组织已完成，输入"再组织一场"开始新工作流...'
          : '描述会议需求，AI 将引导你逐步完成...'
      }
      doneMessage="会议组织工作流已完成"
      draftFieldRenderer={renderMeetingDraft}
      finalGateId="G7"
    />
  )
}
