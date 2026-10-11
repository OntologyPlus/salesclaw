import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  FileText, Plus, AlertCircle, Clock, ListChecks, Trophy, Sparkles,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import FormField from '@/components/forms/FormField'
import Tabs from '@/components/ui/Tabs'
import Skeleton from '@/components/ui/Skeleton'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { trainingAPI } from '@/services/training'
import type { PageRes } from '@/types/page'

// 考试行
interface ExamItem extends Record<string, unknown> {
  id: number | string
  title?: string
  description?: string
  duration_minutes?: number
  pass_score?: number
  question_ids?: number[]
  question_count?: number
  status?: string
  start_at?: string
  end_at?: string
  attempt_count?: number
}

// 题目（options 格式为 [{key:"A", text:"..."}]）
interface Question {
  id: number | string
  question_type?: string
  content?: string
  options?: Array<{ key: string; text: string }>
  difficulty?: string
  points?: number
}

// 考试详情（后端返回扁平结构，含 questions 数组）
interface ExamDetail extends ExamItem {
  questions?: Question[]
  max_attempts?: number
}

// 考试结果
interface ExamResult {
  status?: string
  score?: number
  passed?: boolean
  answers?: Array<{ question_id: number | string; answer: string | string[] }>
  ai_comment?: string
  submitted_at?: string
  correct_count?: number
  total_count?: number
}

// 提交结果
interface SubmitResult {
  score?: number
  passed?: boolean
  correct_count?: number
  total_count?: number
  ai_comment?: string
}

// 分页响应

// 状态映射
const statusMap: Record<string, { label: string; variant: 'default' | 'warning' | 'success' | 'error' | 'info' }> = {
  draft: { label: '草稿', variant: 'default' },
  published: { label: '已发布', variant: 'success' },
  closed: { label: '已关闭', variant: 'error' },
}

// 状态 Tabs
const statusTabs = [
  { key: 'all', label: '全部' },
  { key: 'draft', label: '草稿' },
  { key: 'published', label: '已发布' },
  { key: 'closed', label: '已关闭' },
]

// 题型映射
const questionTypeMap: Record<string, string> = {
  single: '单选题',
  multiple: '多选题',
  judge: '判断题',
  fill: '填空题',
  short: '简答题',
}

export default function ExamsPage() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(1)
  const pageSize = 10

  // 列表数据
  const { data, loading, error, refetch } = useFetch<PageRes<ExamItem>>(
    () => trainingAPI.listExams({
      status: statusFilter === 'all' ? undefined : statusFilter,
      page,
    }),
    [statusFilter, page]
  )

  // 新建 Modal
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [form, setForm] = useState({
    title: '',
    description: '',
    duration_minutes: 60,
    pass_score: 60,
    question_ids: '',
    start_at: '',
    end_at: '',
  })

  // 答题 Modal
  const [takeOpen, setTakeOpen] = useState(false)
  const [examDetail, setExamDetail] = useState<ExamDetail | null>(null)
  const [takeLoading, setTakeLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [answers, setAnswers] = useState<Record<number, string | string[]>>({})

  // 结果 Modal
  const [resultOpen, setResultOpen] = useState(false)
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null)

  const items = data?.items ?? []
  const total = data?.total ?? 0

  // 创建考试
  const handleCreate = async () => {
    if (!form.title) {
      toast('请填写考试标题', 'warning')
      return
    }
    setCreateLoading(true)
    try {
      const qids = form.question_ids
        ? form.question_ids.split(',').map((s) => Number(s.trim())).filter((n) => !isNaN(n) && n > 0)
        : []
      await trainingAPI.createExam({
        title: form.title,
        description: form.description,
        duration_minutes: Number(form.duration_minutes) || 60,
        pass_score: Number(form.pass_score) || 60,
        question_ids: qids,
        start_at: form.start_at || undefined,
        end_at: form.end_at || undefined,
      })
      toast('考试创建成功', 'success')
      setCreateOpen(false)
      setForm({ title: '', description: '', duration_minutes: 60, pass_score: 60, question_ids: '', start_at: '', end_at: '' })
      refetch()
    } catch (e) {
      toast(`创建失败：${(e as Error).message}`, 'error')
    } finally {
      setCreateLoading(false)
    }
  }

  // 参加考试
  const handleTake = async (exam: ExamItem) => {
    if (exam.status !== 'published') {
      toast('该考试当前不可参加', 'warning')
      return
    }
    setTakeOpen(true)
    setTakeLoading(true)
    setExamDetail(null)
    setAnswers({})
    try {
      const detail = await trainingAPI.getExam(exam.id as number)
      setExamDetail(detail)
    } catch (e) {
      toast(`加载考试失败：${(e as Error).message}`, 'error')
      setTakeOpen(false)
    } finally {
      setTakeLoading(false)
    }
  }

  // 选择答案
  const setAnswer = (qid: number, value: string, multi: boolean) => {
    setAnswers((prev) => {
      const next = { ...prev }
      if (multi) {
        const arr = Array.isArray(next[qid]) ? [...(next[qid] as string[])] : []
        const idx = arr.indexOf(value)
        if (idx >= 0) arr.splice(idx, 1)
        else arr.push(value)
        next[qid] = arr
      } else {
        next[qid] = value
      }
      return next
    })
  }

  // 提交考试
  const handleSubmit = async () => {
    const exam = examDetail
    const questions = examDetail?.questions ?? []
    if (!exam) return
    if (Object.keys(answers).length < questions.length) {
      toast(`还有 ${questions.length - Object.keys(answers).length} 题未作答`, 'warning')
      return
    }
    setSubmitting(true)
    try {
      const payload = questions.map((q) => {
        const raw = answers[q.id as number]
        // 统一为数组格式：字符串转为单元素数组，后端按集合比较
        const answer = Array.isArray(raw) ? raw : (raw != null && raw !== '' ? [raw] : [])
        return { question_id: q.id as number, answer }
      })
      const res = await trainingAPI.submitExam(exam.id as number, payload)
      setSubmitResult(res)
      setTakeOpen(false)
      setResultOpen(true)
      refetch()
    } catch (e) {
      toast(`提交失败：${(e as Error).message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // 表格列定义
  const columns: Column<ExamItem>[] = [
    {
      key: 'title', title: '标题',
      render: (row) => (
        <div>
          <span className="font-medium text-slate-900 dark:text-slate-100">{row.title ?? '-'}</span>
          {row.description && (
            <p className="mt-0.5 text-xs text-slate-400 truncate max-w-[240px]">{row.description}</p>
          )}
        </div>
      ),
    },
    {
      key: 'duration_minutes', title: '时长',
      render: (row) => (
        <span className="inline-flex items-center gap-1 text-slate-500">
          <Clock className="w-3.5 h-3.5" /> {row.duration_minutes ?? 0} 分钟
        </span>
      ),
    },
    {
      key: 'pass_score', title: '及格分',
      render: (row) => <span>{row.pass_score ?? 60} 分</span>,
    },
    {
      key: 'question_count', title: '题目数',
      render: (row) => (
        <span className="inline-flex items-center gap-1 text-slate-500">
          <ListChecks className="w-3.5 h-3.5" /> {row.question_count ?? (Array.isArray(row.question_ids) ? row.question_ids.length : 0)}
        </span>
      ),
    },
    {
      key: 'attempt_count', title: '参加次数',
      render: (row) => <span>{row.attempt_count ?? 0}</span>,
    },
    {
      key: 'status', title: '状态',
      render: (row) => {
        const st = statusMap[row.status ?? 'draft'] ?? statusMap.draft
        return <Badge variant={st.variant}>{st.label}</Badge>
      },
    },
    {
      key: 'actions', title: '操作', width: '140px',
      render: (row) => (
        <div className="flex items-center gap-2">
          {row.status === 'published' && (
            <Button size="sm" onClick={() => handleTake(row)}>参加考试</Button>
          )}
          {row.status !== 'published' && (
            <span className="text-xs text-slate-400">不可参加</span>
          )}
        </div>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="考试中心"
        description="考试管理、在线答题与 AI 评分"
        breadcrumbs={[{ label: '智能培训' }, { label: '考试中心' }]}
        icon={<FileText className="w-5 h-5" />}
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="w-4 h-4" />
            新建考试
          </Button>
        }
      />

      {/* 状态过滤 */}
      <div className="mb-4">
        <Tabs tabs={statusTabs} activeKey={statusFilter} onChange={(k) => { setStatusFilter(k); setPage(1) }} />
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <DataTable<ExamItem>
        columns={columns}
        data={items}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
      />

      {/* 新建考试 Modal */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建考试"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button loading={createLoading} onClick={handleCreate}>创建</Button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <FormField label="考试标题" required>
              <Input placeholder="请输入考试标题" value={form.title} onChange={(e) => setForm(p => ({ ...p, title: e.target.value }))} />
            </FormField>
          </div>
          <div className="sm:col-span-2">
            <FormField label="考试描述">
              <textarea
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100 min-h-[80px]"
                placeholder="请输入考试描述"
                value={form.description}
                onChange={(e) => setForm(p => ({ ...p, description: e.target.value }))}
              />
            </FormField>
          </div>
          <FormField label="时长（分钟）" required>
            <Input type="number" min={1} value={form.duration_minutes} onChange={(e) => setForm(p => ({ ...p, duration_minutes: Number(e.target.value) || 0 }))} />
          </FormField>
          <FormField label="及格分" required>
            <Input type="number" min={0} max={100} value={form.pass_score} onChange={(e) => setForm(p => ({ ...p, pass_score: Number(e.target.value) || 0 }))} />
          </FormField>
          <div className="sm:col-span-2">
            <FormField label="题目 ID 列表" hint="多个题目 ID 用英文逗号分隔">
              <Input placeholder="如：1, 2, 3" value={form.question_ids} onChange={(e) => setForm(p => ({ ...p, question_ids: e.target.value }))} />
            </FormField>
          </div>
          <FormField label="开始时间">
            <Input type="datetime-local" value={form.start_at} onChange={(e) => setForm(p => ({ ...p, start_at: e.target.value }))} />
          </FormField>
          <FormField label="结束时间">
            <Input type="datetime-local" value={form.end_at} onChange={(e) => setForm(p => ({ ...p, end_at: e.target.value }))} />
          </FormField>
        </div>
      </Modal>

      {/* 答题 Modal */}
      <Modal
        open={takeOpen}
        onClose={() => setTakeOpen(false)}
        title={`参加考试：${examDetail?.title ?? ''}`}
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setTakeOpen(false)}>取消</Button>
            <Button loading={submitting} onClick={handleSubmit}>提交答卷</Button>
          </>
        }
      >
        {takeLoading ? (
          <div className="py-8"><Skeleton lines={6} /></div>
        ) : examDetail?.questions && examDetail.questions.length > 0 ? (
          <div className="space-y-5">
            {examDetail.questions.map((q, idx) => {
              const qid = q.id as number
              const multi = q.question_type === 'multiple'
              const cur = answers[qid]
              return (
                <motion.div
                  key={qid}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.03 }}
                  className="p-4 rounded-xl border border-slate-200 dark:border-slate-700"
                >
                  <div className="flex items-start gap-2 mb-3">
                    <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      {idx + 1}. {q.content ?? '-'}
                    </span>
                    <Badge variant="info">{questionTypeMap[q.question_type ?? 'single'] ?? '单选题'}</Badge>
                  </div>
                  <div className="space-y-2">
                    {(q.options ?? []).map((opt, oi) => {
                      const value = opt.key || String.fromCharCode(65 + oi)
                      const checked = multi ? Array.isArray(cur) && cur.includes(value) : cur === value
                      return (
                        <label
                          key={oi}
                          className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                            checked ? 'bg-brand-50 dark:bg-brand-900/20 border border-brand-300' : 'hover:bg-slate-50 dark:hover:bg-slate-700/40 border border-transparent'
                          }`}
                        >
                          <input
                            type={multi ? 'checkbox' : 'radio'}
                            name={`q-${qid}`}
                            checked={checked}
                            onChange={() => setAnswer(qid, value, multi)}
                            className="w-4 h-4 accent-brand-600"
                          />
                          <span className="text-sm text-slate-700 dark:text-slate-200">
                            <span className="font-medium mr-1">{value}.</span>{opt.text}
                          </span>
                        </label>
                      )
                    })}
                    {/* 填空题无选项时显示输入框 */}
                    {q.question_type === 'fill' && (
                      <Input
                        placeholder="请输入答案"
                        value={Array.isArray(cur) ? cur.join('') : (cur as string) ?? ''}
                        onChange={(e) => setAnswer(qid, e.target.value, false)}
                      />
                    )}
                  </div>
                </motion.div>
              )
            })}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-slate-500">该考试暂无题目</p>
        )}
      </Modal>

      {/* 结果 Modal */}
      <Modal
        open={resultOpen}
        onClose={() => setResultOpen(false)}
        title="考试结果"
        size="md"
        footer={<Button variant="secondary" onClick={() => setResultOpen(false)}>关闭</Button>}
      >
        {submitResult && (
          <div className="space-y-4">
            <div className={`p-6 rounded-2xl text-center ${
              submitResult.passed
                ? 'bg-gradient-to-br from-emerald-50 to-cyan-50 dark:from-emerald-900/20 dark:to-cyan-900/20'
                : 'bg-gradient-to-br from-rose-50 to-amber-50 dark:from-rose-900/20 dark:to-amber-900/20'
            }`}>
              <div className={`flex items-center justify-center w-14 h-14 rounded-2xl mx-auto mb-3 ${
                submitResult.passed ? 'bg-emerald-500 text-white' : 'bg-rose-500 text-white'
              }`}>
                <Trophy className="w-7 h-7" />
              </div>
              <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">{submitResult.score ?? 0} 分</p>
              <Badge variant={submitResult.passed ? 'success' : 'error'} className="mt-2">
                {submitResult.passed ? '恭喜通过' : '未通过'}
              </Badge>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-400">答对题数</p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">{submitResult.correct_count ?? 0} / {submitResult.total_count ?? 0}</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-400">正确率</p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">
                  {submitResult.total_count ? Math.round(((submitResult.correct_count ?? 0) / submitResult.total_count) * 100) : 0}%
                </p>
              </div>
            </div>
            {submitResult.ai_comment && (
              <div className="p-4 rounded-xl bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20 border border-brand-200 dark:border-brand-800">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-4 h-4 text-brand-500" />
                  <span className="text-sm font-medium text-slate-900 dark:text-slate-100">AI 评语</span>
                </div>
                <p className="text-sm text-slate-600 dark:text-slate-300">{submitResult.ai_comment}</p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
