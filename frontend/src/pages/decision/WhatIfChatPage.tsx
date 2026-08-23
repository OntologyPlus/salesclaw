/**
 * What-if 模拟决策对话式页面（what-if-simulator 工作流）
 *
 * 复用 WorkflowChatLayout 通用组件，仅提供 what-if 特有配置：
 * - 6 步骤 + G1-G7 门禁
 * - 草稿字段渲染：基线 KPI / 策略变量 / 场景名称 / 模拟结果 / 对比
 */
import {
  Lock, ClipboardList, FileText, Target, Database,
  CheckCircle2, Sparkles, TrendingUp, BarChart3, Activity,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '鉴权与基线',
    description: '拉取当前 KPI 基线（拜访积分/覆盖率/质量积分）',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '策略变量采集',
    description: '采集 visit_change / coverage_change / structure_change',
    gates: ['G3'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '场景元数据',
    description: '生成场景名称 + 假设描述，用户确认',
    gates: ['G4'],
    icon: <FileText className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '运行模拟',
    description: '运行模拟（可多轮调参）',
    gates: ['G5'],
    icon: <Activity className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: '多方案对比',
    description: '多方案对比 + 推荐',
    gates: ['G6'],
    icon: <BarChart3 className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '确认保存',
    description: '用户确认保存（可选）',
    gates: ['G7'],
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '基线 KPI 已加载' },
  { id: 'G3', label: '策略变量已采集且用户确认' },
  { id: 'G4', label: '场景名称与假设已确认' },
  { id: 'G5', label: '模拟结果已生成' },
  { id: 'G6', label: '多方案对比完成' },
  { id: 'G7', label: '用户已确认保存或放弃' },
]

const QUICK_STARTERS = [
  '模拟拜访频次+20%对KPI的影响',
  '推演覆盖范围扩大5家医院的效果',
  '对比学术拜访占比+10%的策略',
  '分析拜访结构优化的ROI',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderWhatIfDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const config = safeGet<Record<string, unknown>>(draftState, 'config')
  if (config) {
    const baselineKpi = safeGet<Record<string, unknown>>(config, 'baseline_kpi')
    if (baselineKpi) {
      const visitScore = safeGet(baselineKpi, 'visit_score')
      const coverageRate = safeGet(baselineKpi, 'coverage_rate')
      const qualityScore = safeGet(baselineKpi, 'quality_score')
      if (visitScore != null || coverageRate != null || qualityScore != null) {
        const parts: string[] = []
        if (visitScore != null) parts.push(`拜访=${visitScore}`)
        if (coverageRate != null) parts.push(`覆盖=${coverageRate}`)
        if (qualityScore != null) parts.push(`质量=${qualityScore}`)
        items.push({
          label: '基线 KPI',
          value: parts.join(' / '),
          icon: <TrendingUp className="w-3.5 h-3.5" />,
        })
      }
    }
  }

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const visitChange = safeGet(collection, 'visit_change')
    const coverageChange = safeGet(collection, 'coverage_change')
    const structureChange = safeGet(collection, 'structure_change')
    const parts: string[] = []
    if (visitChange != null) parts.push(`拜访${visitChange}`)
    if (coverageChange != null) parts.push(`覆盖${coverageChange}`)
    if (structureChange != null) parts.push(`结构${structureChange}`)
    if (parts.length)
      items.push({
        label: '策略变量',
        value: parts.join(' / '),
        icon: <Target className="w-3.5 h-3.5" />,
      })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  if (titleBg) {
    const scenarioName = safeStr(safeGet(titleBg, 'scenario_name'))
    if (scenarioName)
      items.push({ label: '场景名称', value: scenarioName, icon: <FileText className="w-3.5 h-3.5" /> })
    const hypothesis = safeStr(safeGet(titleBg, 'hypothesis'))
    if (hypothesis)
      items.push({
        label: '假设描述',
        value: hypothesis.length > 80 ? hypothesis.slice(0, 80) + '...' : hypothesis,
        icon: <FileText className="w-3.5 h-3.5" />,
      })
  }

  const contextPayload = safeGet<Record<string, unknown>>(draftState, 'context_payload')
  if (contextPayload) {
    const simulationResult = safeGet<Record<string, unknown>>(contextPayload, 'simulation_result')
    if (simulationResult) {
      const projectedKpi = safeGet<Record<string, unknown>>(simulationResult, 'projected_kpi')
      const delta = safeGet<Record<string, unknown>>(simulationResult, 'delta')
      if (projectedKpi || delta) {
        items.push({
          label: '模拟结果',
          value: '已生成预测 KPI',
          icon: <Activity className="w-3.5 h-3.5" />,
        })
      }
    }
  }

  const knowledge = safeGet<Record<string, unknown>>(draftState, 'knowledge')
  if (knowledge) {
    const comparisons = safeArr<Record<string, unknown>>(safeGet(knowledge, 'comparisons'))
    if (comparisons.length)
      items.push({
        label: '方案对比',
        value: `${comparisons.length} 个方案`,
        icon: <BarChart3 className="w-3.5 h-3.5" />,
      })
    const recommendation = safeStr(safeGet(knowledge, 'final_recommendation'))
    if (recommendation)
      items.push({
        label: '推荐方案',
        value: recommendation,
        icon: <CheckCircle2 className="w-3.5 h-3.5" />,
      })
  }

  return items
}

export default function WhatIfChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式 What-if 模拟决策"
      pageDescription="AI 原生 · 门禁驱动工作流 · 策略推演与方案优选"
      breadcrumbs={[{ label: '决策支持' }, { label: '对话式 What-if 模拟' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过自然语言对话进行策略模拟"
      emptyStateSubtitle="AI 将引导您完成 基线加载 → 策略变量 → 场景元数据 → 运行模拟 → 多方案对比"
      inputPlaceholder={(isDone) =>
        isDone
          ? '模拟已完成，输入"再模拟一个"开始新工作流...'
          : '描述模拟场景，AI 将引导你逐步完成...'
      }
      doneMessage="模拟决策已完成"
      draftFieldRenderer={renderWhatIfDraft}
      finalGateId="G7"
    />
  )
}
