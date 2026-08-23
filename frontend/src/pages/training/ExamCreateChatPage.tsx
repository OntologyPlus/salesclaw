/**
 * 考试生成对话式页面（exam-generator 工作流）
 *
 * 复用 WorkflowChatLayout 通用组件，仅提供 exam-generator 特有配置：
 * - 7 步骤 + G1-G8 门禁
 * - 草稿字段渲染：课程 / 题型组合 / 知识点 / 考试标题 / 题目列表 / 校验报告
 */
import {
  Lock, ClipboardList, FileText, BookOpen, CheckCircle2,
  Sparkles, GraduationCap, ListChecks, ClipboardCheck, Award,
} from 'lucide-react'
import WorkflowChatLayout, {
  type StepDef, type GateDef, type DraftFieldItem, safeGet, safeArr,
} from '@/components/workflow/WorkflowChatLayout'
import type { DraftState } from '@/hooks/useAIStream'

const STEPS: StepDef[] = [
  {
    name: 'Step1',
    label: '鉴权与课程',
    description: '拉取课程列表 + 难度分布规则',
    gates: ['G1', 'G2'],
    icon: <Lock className="w-4 h-4" />,
  },
  {
    name: 'Step2',
    label: '题型与知识点',
    description: '采集题型组合 + 知识点覆盖',
    gates: ['G3'],
    icon: <ClipboardList className="w-4 h-4" />,
  },
  {
    name: 'Step3',
    label: '考试标题',
    description: '生成考试标题 + 说明，用户确认',
    gates: ['G4'],
    icon: <FileText className="w-4 h-4" />,
  },
  {
    name: 'Step4',
    label: '题目生成',
    description: '按难度分布批量生成题目',
    gates: ['G5'],
    icon: <ListChecks className="w-4 h-4" />,
  },
  {
    name: 'Step5',
    label: '题卷校验',
    description: '校验题量 + 分值 + 知识点覆盖率',
    gates: ['G6'],
    icon: <ClipboardCheck className="w-4 h-4" />,
  },
  {
    name: 'Step6',
    label: '提交确认',
    description: '用户确认提交，落库 Exam',
    gates: ['G7'],
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
  {
    name: 'Step7',
    label: '完成',
    description: '考试已创建，返回 exam_id',
    gates: ['G8'],
    icon: <Sparkles className="w-4 h-4" />,
  },
]

const GATES: GateDef[] = [
  { id: 'G1', label: '租户与用户已识别' },
  { id: 'G2', label: '课程列表已加载' },
  { id: 'G3', label: '题型与知识点已采集且用户确认' },
  { id: 'G4', label: '考试标题已确认' },
  { id: 'G5', label: '题目已生成' },
  { id: 'G6', label: '题卷校验通过' },
  { id: 'G7', label: '用户已确认提交' },
  { id: 'G8', label: '考试已落库' },
]

const QUICK_STARTERS = [
  '为医药合规课程生成期末考试',
  '为产品知识培训生成 30 题组卷',
  '生成包含单选多选判断的考试',
  '为新人入职培训生成考试',
]

function safeStr(v: unknown, fallback = ''): string {
  if (typeof v === 'string') return v
  if (v == null) return fallback
  return String(v)
}

function renderExamDraft(draftState: DraftState | null): DraftFieldItem[] {
  const items: DraftFieldItem[] = []
  if (!draftState) return items

  const config = safeGet<Record<string, unknown>>(draftState, 'config')
  if (config) {
    const courseList = safeArr<Record<string, unknown>>(safeGet(config, 'course_list'))
    if (courseList.length)
      items.push({
        label: '可选课程',
        value: `${courseList.length} 门课程`,
        icon: <BookOpen className="w-3.5 h-3.5" />,
      })
    const difficultyMix = safeGet<Record<string, unknown>>(config, 'difficulty_mix')
    if (difficultyMix) {
      const easy = safeGet(difficultyMix, 'easy')
      const medium = safeGet(difficultyMix, 'medium')
      const hard = safeGet(difficultyMix, 'hard')
      if (easy != null || medium != null || hard != null) {
        items.push({
          label: '难度分布',
          value: `易${easy ?? 0} / 中${medium ?? 0} / 难${hard ?? 0}`,
          icon: <Award className="w-3.5 h-3.5" />,
        })
      }
    }
  }

  const collection = safeGet<Record<string, unknown>>(draftState, 'collection')
  if (collection) {
    const courseId = safeGet(collection, 'course_id')
    if (courseId != null)
      items.push({
        label: '目标课程',
        value: `课程 #${courseId}`,
        icon: <GraduationCap className="w-3.5 h-3.5" />,
      })
    const questionTypes = safeGet<Record<string, unknown>>(collection, 'question_types')
    if (questionTypes) {
      const parts: string[] = []
      const single = safeGet(questionTypes, 'single')
      const multi = safeGet(questionTypes, 'multi')
      const judge = safeGet(questionTypes, 'judge')
      const qa = safeGet(questionTypes, 'qa')
      if (single != null) parts.push(`单选${single}`)
      if (multi != null) parts.push(`多选${multi}`)
      if (judge != null) parts.push(`判断${judge}`)
      if (qa != null) parts.push(`简答${qa}`)
      if (parts.length)
        items.push({
          label: '题型组合',
          value: parts.join(' / '),
          icon: <ListChecks className="w-3.5 h-3.5" />,
        })
    }
    const knowledgePoints = safeArr<string>(safeGet(collection, 'knowledge_points'))
    if (knowledgePoints.length)
      items.push({
        label: '知识点',
        value: `${knowledgePoints.length} 个知识点`,
        icon: <BookOpen className="w-3.5 h-3.5" />,
      })
    const totalScore = safeGet(collection, 'total_score')
    const passScore = safeGet(collection, 'pass_score')
    if (totalScore != null || passScore != null)
      items.push({
        label: '分值配置',
        value: `总分${totalScore ?? 100} / 及格${passScore ?? 60}`,
        icon: <Award className="w-3.5 h-3.5" />,
      })
  }

  const titleBg = safeGet<Record<string, unknown>>(draftState, 'title_bg')
  if (titleBg) {
    const examTitle = safeStr(safeGet(titleBg, 'exam_title'))
    if (examTitle)
      items.push({ label: '考试标题', value: examTitle, icon: <FileText className="w-3.5 h-3.5" /> })
    const examDescription = safeStr(safeGet(titleBg, 'exam_description'))
    if (examDescription)
      items.push({
        label: '考试说明',
        value: examDescription.length > 80 ? examDescription.slice(0, 80) + '...' : examDescription,
        icon: <FileText className="w-3.5 h-3.5" />,
      })
  }

  const knowledge = safeGet<Record<string, unknown>>(draftState, 'knowledge')
  if (knowledge) {
    const questions = safeArr<Record<string, unknown>>(safeGet(knowledge, 'questions'))
    if (questions.length)
      items.push({
        label: '题目列表',
        value: `${questions.length} 题`,
        icon: <ListChecks className="w-3.5 h-3.5" />,
      })
    const validationPassed = safeGet<boolean>(knowledge, 'validation_passed')
    if (validationPassed)
      items.push({
        label: '题卷校验',
        value: '已通过',
        icon: <ClipboardCheck className="w-3.5 h-3.5" />,
      })
  }

  if (draftState.scenario_id) {
    items.push({
      label: '考试 ID',
      value: `#${draftState.scenario_id}`,
      icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    })
  }

  return items
}

export default function ExamCreateChatPage() {
  return (
    <WorkflowChatLayout
      pageTitle="对话式考试生成"
      pageDescription="AI 原生 · 门禁驱动工作流 · 智能组卷与校验"
      breadcrumbs={[{ label: '智能培训' }, { label: '对话式考试生成' }]}
      steps={STEPS}
      gates={GATES}
      quickStarters={QUICK_STARTERS}
      emptyStateTitle="通过自然语言对话生成考试"
      emptyStateSubtitle="AI 将引导您完成 课程选择 → 题型知识点 → 标题 → 题目生成 → 校验 → 落库"
      inputPlaceholder={(isDone) =>
        isDone
          ? '考试已生成，输入"再生成一份"开始新工作流...'
          : '描述考试需求，AI 将引导你逐步完成...'
      }
      doneMessage="考试已成功生成"
      draftFieldRenderer={renderExamDraft}
      finalGateId="G8"
    />
  )
}
