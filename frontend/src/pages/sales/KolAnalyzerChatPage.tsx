/**
 * KOL 画像工作流对话式页面（kol-analyzer 工作流）
 *
 * 复用 WorkflowChatLayout 通用组件，仅提供 kol-analyzer 特有配置：
 * - 6 步骤 + G1-G7 门禁
 * - 草稿字段渲染：候选名单 / 维度 / 多源数据 / 画像 / 分级 / 策略
 */
import {
  Lock, ClipboardList, Database, FileText, Target,
  CheckCircle2, Users, Layers, Award,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '鉴权与候选拉取',
    description: '加载租户/用户身份，拉取 KOL 候选医生名单',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '维度采集',
    description: '采集画像维度（学术 / 处方 / 影响力 / 合作意愿）',
    gates: ['G3'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '多源数据',
    description: '聚合拜访记录 / 学术活动 / 反馈 / 培训参与',
    gates: ['G4'],
    icon: <Database className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '画像 + 分级',
    description: '生成 KOL 画像 + 多维评分 + 分级（A/B/C/D）',
    gates: ['G5'],
    icon: <Award className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: '策略建议',
    description: '生成个性化合作策略建议（覆盖频次/资源/活动）',
    gates: ['G6'],
    icon: <Target className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '落库',
    description: 'KOL 记录入库（importance=11）',
    gates: ['G7'],
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: 'KOL 候选名单已拉取' },
  { id: 'G3', label: '画像维度已采集' },
  { id: 'G4', label: '多源数据已聚合' },
  { id: 'G5', label: '画像与分级已生成' },
  { id: 'G6', label: '策略建议已生成并确认' },
  { id: 'G7', label: 'KOL 记录已落库' },
]

const QUICK_STARTERS = [
  '为心内科 Top 10 医生生成 KOL 画像',
  '识别覆盖区域内 A 级 KOL 并推荐合作策略',
  '为新产品上市筛选学术影响力高的 KOL',
  '分析 KOL 合作意愿并生成拜访计划',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderKolDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const config = safeGet<Record<string, unknown>>(draftState, 'config')
  if (config) {
    const candidates = safeArr<Record<string, unknown>>(safeGet(config, 'kol_candidates'))
    if (candidates.length)
      items.push({
        label: 'KOL 候选',
        value: `${candidates.length} 位`,
        icon: <Users className="w-3.5 h-3.5" />,
      })
  }

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const parts: string[] = []
    const academic = safeGet(collection, 'academic_weight')
    const prescription = safeGet(collection, 'prescription_weight')
    const influence = safeGet(collection, 'influence_weight')
    const cooperation = safeGet(collection, 'cooperation_weight')
    if (academic != null) parts.push(`学术=${academic}`)
    if (prescription != null) parts.push(`处方=${prescription}`)
    if (influence != null) parts.push(`影响力=${influence}`)
    if (cooperation != null) parts.push(`合作=${cooperation}`)
    if (parts.length)
      items.push({
        label: '画像维度',
        value: parts.join(' / '),
        icon: <Layers className="w-3.5 h-3.5" />,
      })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  if (titleBg) {
    const aggregated = safeArr<Record<string, unknown>>(safeGet(titleBg, 'aggregated_data'))
    if (aggregated.length)
      items.push({
        label: '多源数据',
        value: `${aggregated.length} 位已聚合`,
        icon: <Database className="w-3.5 h-3.5" />,
      })
  }

  const knowledge = safeGet<Record<string, unknown>>(draftState, 'knowledge')
  if (knowledge) {
    const profiles = safeArr<Record<string, unknown>>(safeGet(knowledge, 'profiles'))
    if (profiles.length)
      items.push({
        label: 'KOL 画像',
        value: `${profiles.length} 份已生成`,
        icon: <FileText className="w-3.5 h-3.5" />,
      })

    const tiers = safeArr<Record<string, unknown>>(safeGet(knowledge, 'tiers'))
    if (tiers.length) {
      const tierCounts: Record<string, number> = {}
      for (const t of tiers) {
        const tier = safeStr(safeGet(t, 'tier'))
        if (tier) tierCounts[tier] = (tierCounts[tier] || 0) + 1
      }
      const summary = Object.entries(tierCounts)
        .map(([t, c]) => `${t}=${c}`)
        .join(' / ')
      if (summary)
        items.push({
          label: '分级',
          value: summary,
          icon: <Award className="w-3.5 h-3.5" />,
        })
    }

    const strategy = safeGet<Record<string, unknown>>(knowledge, 'strategy')
    if (strategy) {
      const coverageFreq = safeGet(strategy, 'coverage_frequency')
      const activity = safeGet(strategy, 'recommended_activity')
      const parts: string[] = []
      if (coverageFreq != null) parts.push(`频次=${coverageFreq}`)
      if (activity != null) parts.push(`活动=${activity}`)
      if (parts.length)
        items.push({
          label: '合作策略',
          value: parts.join(' / '),
          icon: <Target className="w-3.5 h-3.5" />,
        })
    }
  }

  const contextPayload = safeGet<Record<string, unknown>>(draftState, 'context_payload')
  if (contextPayload) {
    const kolIds = safeArr<unknown>(safeGet(contextPayload, 'kol_ids'))
    if (kolIds.length)
      items.push({
        label: '已落库',
        value: `${kolIds.length} 条记录`,
        icon: <CheckCircle2 className="w-3.5 h-3.5" />,
      })
  }

  return items
}

export default function KolAnalyzerChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式 KOL 画像工作流"
      pageDescription="AI 原生 · 门禁驱动工作流 · 多维画像与合作策略"
      breadcrumbs={[{ label: '销售执行' }, { label: '对话式 KOL 画像' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过自然语言对话识别 KOL"
      emptyStateSubtitle="AI 将引导您完成 候选拉取 → 维度采集 → 多源数据 → 画像+分级 → 策略建议 → 落库"
      inputPlaceholder={(isDone) =>
        isDone
          ? 'KOL 画像已完成，输入"再分析一批"开始新工作流...'
          : '描述 KOL 识别需求，AI 将引导你逐步完成...'
      }
      doneMessage="KOL 画像工作流已完成"
      draftFieldRenderer={renderKolDraft}
      finalGateId="G7"
    />
  )
}
