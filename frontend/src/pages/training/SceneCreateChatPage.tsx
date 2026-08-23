/**
 * 对话式场景创建页面（薄包装）
 *
 * F12 收敛：原 784 行 1:1 重复 WorkflowChatLayout，现收敛为 ~140 行薄包装。
 * 仅保留页面专属配置：STEPS / GATES / QUICK_STARTERS / draftFieldRenderer / finalGateId。
 */
import WorkflowChatLayout, { safeGet, safeArr, type DraftFieldItem } from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'
import {
  FileText, BookOpen, Target, Users, Tag, Lightbulb, Database,
  ClipboardList, Lock, CheckCircle2, Sparkles,
} from 'lucide-react'

// 步骤定义（与后端 SKILL.md frontmatter 的 steps 对齐）
const STEPS = [
  { name: 'Step1', label: '鉴权与配置', description: '拉取场景主题/业务领域/受训对象三列表', gates: ['G1'], icon: <Lock className="w-4 h-4" /> },
  { name: 'Step2', label: '采集与回显', description: '采集医生画像/最佳实践点/品种/拜访目的', gates: ['G2', 'G3'], icon: <ClipboardList className="w-4 h-4" /> },
  { name: 'Step3', label: '标题与背景', description: '生成场景标题与背景描述，用户确认', gates: ['G4'], icon: <FileText className="w-4 h-4" /> },
  { name: 'Step4', label: '知识挂载', description: 'RAG 推荐 Top5 知识，用户锁定', gates: ['G5'], icon: <BookOpen className="w-4 h-4" /> },
  { name: 'Step5', label: 'Payload 生成', description: '生成 doctor 5 键 + coach 3 键上下文（对用户不可见）', gates: ['G6'], icon: <Database className="w-4 h-4" /> },
  { name: 'Step6', label: '提交确认', description: '用户确认提交，落库 PracticeScenario', gates: ['G7'], icon: <CheckCircle2 className="w-4 h-4" /> },
  { name: 'Step7', label: '完成', description: '场景已创建，返回 scenario_id', gates: ['G8'], icon: <Sparkles className="w-4 h-4" /> },
]

// 门禁定义（与后端 scene_workspace.validate_gate 对齐）
const GATES = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '三列表已加载' },
  { id: 'G3', label: '采集字段已填写' },
  { id: 'G4', label: '标题与背景已确认' },
  { id: 'G5', label: '知识已锁定' },
  { id: 'G6', label: '上下文 Payload 已就绪' },
  { id: 'G7', label: '用户已确认提交' },
  { id: 'G8', label: '场景已落库' },
]

// 快捷建议
const QUICK_STARTERS = [
  '帮我创建一个拜访主任的场景',
  '设计一个议价对练场景',
  '创建一个异议处理培训场景',
  '新建对话类培训场景',
]

// 安全把未知值转为字符串
function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

// 草稿回显字段提取（从 draftState 抽取关键字段，过滤空值）
function renderDraft(draft: DraftState | null): DraftFieldItem[] {
  if (!draft) return []
  const items: DraftFieldItem[] = []

  const collection = safeGet<Record<string, unknown>>(draft, 'collection')
  const titleBg = safeGet<Record<string, unknown>>(draft, 'title_bg')
  const knowledge = safeGet<Record<string, unknown>>(draft, 'knowledge')
  const contextPayload = safeGet<Record<string, unknown>>(draft, 'context_payload')

  if (collection) {
    const doctorPersona = safeStr(safeGet(collection, 'doctor_persona'))
    if (doctorPersona) items.push({ label: '医生画像', value: doctorPersona, icon: <Users className="w-3.5 h-3.5" /> })
    const bestPractices = safeArr<string>(safeGet(collection, 'best_practice_points'))
    if (bestPractices.length) items.push({ label: '最佳实践点', value: bestPractices.join(' / '), icon: <Target className="w-3.5 h-3.5" /> })
    const products = safeArr<string>(safeGet(collection, 'product_lines'))
    if (products.length) items.push({ label: '品种', value: products.join(' / '), icon: <Tag className="w-3.5 h-3.5" /> })
    const visitPurpose = safeStr(safeGet(collection, 'visit_purpose'))
    if (visitPurpose) items.push({ label: '拜访目的', value: visitPurpose, icon: <Lightbulb className="w-3.5 h-3.5" /> })
  }
  if (titleBg) {
    const title = safeStr(safeGet(titleBg, 'title'))
    if (title) items.push({ label: '场景标题', value: title, icon: <FileText className="w-3.5 h-3.5" /> })
    const sceneBg = safeStr(safeGet(titleBg, 'scene_background'))
    if (sceneBg) items.push({
      label: '场景背景',
      value: sceneBg.length > 80 ? sceneBg.slice(0, 80) + '...' : sceneBg,
      icon: <FileText className="w-3.5 h-3.5" />,
    })
  }
  if (knowledge) {
    const ids = safeArr<number | string>(safeGet(knowledge, 'ids'))
    if (ids.length) items.push({ label: '已挂载知识', value: `${ids.length} 条知识条目`, icon: <BookOpen className="w-3.5 h-3.5" /> })
  }
  if (contextPayload) {
    const ready = safeGet<boolean>(contextPayload, 'ready')
    if (ready) items.push({ label: '上下文 Payload', value: 'doctor + coach 已就绪', icon: <Database className="w-3.5 h-3.5" /> })
  }
  if (draft.scenario_id) {
    items.push({ label: '场景 ID', value: `#${draft.scenario_id}`, icon: <CheckCircle2 className="w-3.5 h-3.5" /> })
  }
  return items
}

export default function SceneCreateChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式场景创建"
      pageDescription="通过自然语言对话，逐步生成拜访对练场景"
      breadcrumbs={[{ label: '培训' }, { label: '场景创建' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="开始创建培训场景"
      emptyStateSubtitle="告诉 AI 你想创建什么样的拜访对练场景"
      inputPlaceholder={(done) => (done ? '场景已创建，可继续追问' : '描述你想创建的场景...')}
      doneMessage="场景已创建成功"
      draftFieldRenderer={renderDraft}
      finalGateId="G8"
      pageKey="scene-create"
    />
  )
}
