/**
 * 医药代表上岗备案对话式页面（pharma-rep-onboarding 工作流）
 */
import {
  Lock, ClipboardList, FileSignature, BadgeCheck, ShieldCheck,
  CheckCircle2, Sparkles, User, GraduationCap, MapPin,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '上岗清单',
    description: '拉取培训/考核/承诺三件套状态',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '资质采集',
    description: '学历/专业/身份证/合同/授权区域',
    gates: ['G3'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '承诺书签署',
    description: '合规承诺书预览与签署确认',
    gates: ['G4'],
    icon: <FileSignature className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '备案提交',
    description: '生成唯一备案号（第 16 条）',
    gates: ['G5'],
    icon: <BadgeCheck className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: '准入校验',
    description: '上岗三件套二次校验',
    gates: ['G6'],
    icon: <ShieldCheck className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '落库完成',
    description: '上岗记录落库',
    gates: ['G7'],
    icon: <Sparkles className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '上岗清单已拉取' },
  { id: 'G3', label: '资质草稿已确认' },
  { id: 'G4', label: '承诺书已签署' },
  { id: 'G5', label: '备案已提交' },
  { id: 'G6', label: '上岗准入通过' },
  { id: 'G7', label: '上岗记录已落库' },
]

const QUICK_STARTERS = [
  '开始上岗备案',
  '查看我的上岗三件套状态',
  '我已完成培训和考试，准备签署承诺书',
  '提交备案并完成上岗准入',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderOnboardingDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const config = safeGet<Record<string, unknown>>(draftState, 'config')
  if (config) {
    const status = safeGet<Record<string, unknown>>(config, 'onboarding_status')
    if (status) {
      const training = status.training_done ?? status.course_completed
      const exam = status.exam_done ?? status.exam_passed
      const commit = status.commitment_signed
      items.push({
        label: '三件套',
        value: `培训${training ? '✓' : '○'} / 考试${exam ? '✓' : '○'} / 承诺${commit ? '✓' : '○'}`,
        icon: <GraduationCap className="w-3.5 h-3.5" />,
      })
    }
  }

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const education = safeStr(safeGet(collection, 'education'))
    if (education)
      items.push({ label: '学历', value: education, icon: <User className="w-3.5 h-3.5" /> })
    const region = safeStr(safeGet(collection, 'authorized_region') ?? safeGet(collection, 'region'))
    if (region)
      items.push({ label: '授权区域', value: region, icon: <MapPin className="w-3.5 h-3.5" /> })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  const regNo = safeStr(
    safeGet(titleBg || {}, 'registration_no')
      ?? safeGet(draftState, 'registration_no'),
  )
  if (regNo)
    items.push({ label: '备案号', value: regNo, icon: <BadgeCheck className="w-3.5 h-3.5" /> })

  if (draftState.scenario_id) {
    items.push({
      label: '上岗记录',
      value: `#${draftState.scenario_id}`,
      icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    })
  }

  const gates = safeArr<string>(draftState.gates_passed)
  if (gates.length)
    items.push({
      label: '已过门禁',
      value: gates.join(', '),
      icon: <ShieldCheck className="w-3.5 h-3.5" />,
    })

  return items
}

export default function OnboardingChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式上岗备案"
      pageDescription="AI 原生 · 门禁驱动 · 培训-考核-承诺闭环（第 9/10/14-18 条）"
      breadcrumbs={[{ label: '智能培训' }, { label: '对话式上岗备案' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过对话完成医药代表上岗备案"
      emptyStateSubtitle="AI 将引导：清单核对 → 资质采集 → 承诺签署 → 备案号 → 准入 → 落库"
      inputPlaceholder={(isDone) =>
        isDone
          ? '上岗已完成，输入「重新开始备案」开启新流程...'
          : '描述上岗进度，或点击快捷语开始...'
      }
      doneMessage="上岗备案已完成"
      draftFieldRenderer={renderOnboardingDraft}
      finalGateId="G7"
      pageKey="pharma-rep-onboarding"
      intentOverride="pharma_rep_onboarding"
    />
  )
}
