import { useState } from 'react'
import { Presentation, Plus, Play, Square, Check, AlertCircle, Trophy, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import PageHeader from '@/components/data/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Input from '@/components/ui/Input'
import Modal from '@/components/ui/Modal'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { pptSpeechAPI } from '@/services/pptSpeech'

interface PPTScenario extends Record<string, unknown> {
  id: number
  title: string
  description?: string
  ppt_url?: string
  ppt_pages?: any[]
  pass_score?: number
  scoring_dimensions?: any[]
  is_published?: boolean | number
}

interface PPTSession extends Record<string, unknown> {
  id: number
  scenario_id: number
  status: string
  current_page: number
  final_score?: number
  radar_scores?: Record<string, number>
  ai_review?: string
  started_at?: string
}

// 7 维度雷达图配置
const DIMENSION_LABELS: Record<string, string> = {
  content_accuracy: '内容准确性',
  keyword_coverage: '关键词覆盖',
  structure_logic: '结构逻辑',
  fluency: '表达流畅',
  qa_response: '问答应对',
  transition: '过渡衔接',
  time_management: '时间管理',
}

export default function PPTSpeechPage() {
  const toast = useToast()
  const { data, loading, error, refetch } = useFetch<{ items: PPTScenario[]; total: number }>(
    () => pptSpeechAPI.listScenarios({ page: 1, page_size: 50 }),
    []
  )

  const [showCreate, setShowCreate] = useState(false)
  const [activeScenario, setActiveScenario] = useState<PPTScenario | null>(null)
  const [session, setSession] = useState<PPTSession | null>(null)
  const [creating, setCreating] = useState(false)
  const [starting, setStarting] = useState(false)
  const [submittingPage, setSubmittingPage] = useState(false)
  const [completing, setCompleting] = useState(false)
  const [showResult, setShowResult] = useState(false)

  // 创建表单
  const [form, setForm] = useState({
    title: '',
    description: '',
    ppt_url: '',
    pass_score: 60,
  })

  // 新建场景
  const handleCreate = async () => {
    if (!form.title.trim()) {
      toast('请输入场景标题', 'warning')
      return
    }
    setCreating(true)
    try {
      await pptSpeechAPI.createScenario({
        title: form.title.trim(),
        description: form.description.trim() || null,
        ppt_url: form.ppt_url.trim() || null,
        pass_score: Number(form.pass_score) || 60,
        mode: 'practice',
      })
      toast('PPT 演讲场景已创建（已自动触发 Mock 解析）', 'success')
      setShowCreate(false)
      setForm({ title: '', description: '', ppt_url: '', pass_score: 60 })
      refetch()
    } catch (e) {
      toast(`创建失败：${(e as Error).message}`, 'error')
    } finally {
      setCreating(false)
    }
  }

  // 开始演讲会话
  const handleStart = async (scenario: PPTScenario) => {
    setActiveScenario(scenario)
    setSession(null)
    setShowResult(false)
    setStarting(true)
    try {
      const res = await pptSpeechAPI.startSession({ scenario_id: scenario.id, mode: 'practice' })
      setSession(res)
      toast('演讲会话已启动', 'success')
    } catch (e) {
      toast(`启动失败：${(e as Error).message}`, 'error')
      setActiveScenario(null)
    } finally {
      setStarting(false)
    }
  }

  // 提交当前页录音（Mock：标记完成）
  const handleSubmitPage = async () => {
    if (!session) return
    setSubmittingPage(true)
    try {
      const res = await pptSpeechAPI.submitPage(session.id, {
        page_no: session.current_page,
        recording: { url: null, duration: 60 }, // Mock 录音
      })
      setSession(res)
      toast(`第 ${session.current_page} 页已完成`, 'success')
    } catch (e) {
      toast(`提交失败：${(e as Error).message}`, 'error')
    } finally {
      setSubmittingPage(false)
    }
  }

  // 完成会话并获取评分
  const handleComplete = async () => {
    if (!session) return
    if (!confirm('确认结束本次演讲训战？结束后将获得 AI 评分。')) return
    setCompleting(true)
    try {
      const res = await pptSpeechAPI.completeSession(session.id)
      setSession(res)
      setShowResult(true)
      toast(`演讲已结束，得分：${res.final_score ?? '-'}`, 'success')
    } catch (e) {
      toast(`结束失败：${(e as Error).message}`, 'error')
    } finally {
      setCompleting(false)
    }
  }

  const scenarios = data?.items ?? []
  const pages = (activeScenario?.ppt_pages ?? []) as any[]
  const currentPageIdx = session ? session.current_page - 1 : -1

  return (
    <div>
      <PageHeader
        title="PPT 演讲训战"
        description="PPT 场景演讲训练，7 维度 AI 评分与雷达图反馈"
        breadcrumbs={[{ label: '智能培训' }, { label: 'PPT 演讲' }]}
        icon={<Presentation className="w-5 h-5" />}
        actions={<Button size="sm" onClick={() => setShowCreate(true)}><Plus className="w-4 h-4" /> 新建场景</Button>}
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：场景列表 */}
        <div className="lg:col-span-1">
          <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">PPT 场景</h2>
            </div>
            <div className="divide-y divide-slate-100 dark:divide-slate-700 max-h-[600px] overflow-y-auto">
              {loading ? (
                <div className="p-5"><Skeleton lines={5} /></div>
              ) : scenarios.length === 0 ? (
                <Empty description="暂无 PPT 场景" />
              ) : (
                scenarios.map((s, i) => {
                  const active = activeScenario?.id === s.id
                  const isPublished = s.is_published === true || s.is_published === 1
                  return (
                    <motion.button
                      key={s.id ?? i}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.04 }}
                      onClick={() => handleStart(s)}
                      className={`w-full text-left px-5 py-3 transition-colors ${
                        active ? 'bg-brand-50 dark:bg-brand-900/20 border-l-2 border-brand-500' : 'hover:bg-slate-50 dark:hover:bg-slate-700/40'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{s.title ?? '-'}</span>
                        {isPublished ? <Badge variant="success">已发布</Badge> : <Badge variant="default">草稿</Badge>}
                      </div>
                      {s.description && <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2">{s.description}</p>}
                      <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                        <span>及格 {s.pass_score ?? 60} 分</span>
                        <span>·</span>
                        <span>{(s.ppt_pages ?? []).length} 页</span>
                      </div>
                    </motion.button>
                  )
                })
              )}
            </div>
          </div>
        </div>

        {/* 右侧：演讲播放器 / 结果 */}
        <div className="lg:col-span-2">
          {!activeScenario ? (
            <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 h-[600px] flex items-center justify-center">
              <div className="text-center">
                <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-100 to-violet-100 dark:from-brand-900/40 dark:to-violet-900/40 mx-auto mb-4">
                  <Presentation className="w-8 h-8 text-brand-500" />
                </div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200">选择 PPT 场景开始演讲训战</p>
                <p className="mt-1 text-xs text-slate-400">系统将模拟 PPT 翻页演讲，AI 实时评估 7 个维度</p>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col h-[600px]">
              {/* 头部 */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-500 text-white shrink-0">
                    <Presentation className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{activeScenario.title}</p>
                    <p className="text-xs text-slate-400">
                      {session ? `会话 #${session.id} · 第 ${session.current_page}/${pages.length} 页` : '准备开始...'}
                    </p>
                  </div>
                </div>
                {session && session.status !== 'completed' && !showResult && (
                  <Button size="sm" variant="danger" loading={completing} onClick={handleComplete}>
                    <Square className="w-3.5 h-3.5" /> 结束评分
                  </Button>
                )}
              </div>

              {/* 内容区 */}
              <div className="flex-1 overflow-y-auto p-5 bg-slate-50/50 dark:bg-slate-900/20">
                {starting ? (
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Sparkles className="w-4 h-4 animate-pulse text-brand-500" />
                    正在启动演讲会话...
                  </div>
                ) : showResult && session ? (
                  <ResultView session={session} />
                ) : session && pages.length > 0 ? (
                  <PageView
                    page={pages[currentPageIdx]}
                    pageNo={session.current_page}
                    total={pages.length}
                  />
                ) : (
                  <div className="text-sm text-slate-500">无可用 PPT 页面数据</div>
                )}
              </div>

              {/* 操作栏 */}
              {session && !showResult && session.status !== 'completed' && pages.length > 0 && (
                <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1">
                    {pages.map((_, i) => (
                      <span key={i} className={`w-2 h-2 rounded-full ${i < currentPageIdx ? 'bg-emerald-500' : i === currentPageIdx ? 'bg-brand-500' : 'bg-slate-300 dark:bg-slate-600'}`} />
                    ))}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </Button>
                    <Button size="sm" onClick={handleSubmitPage} loading={submittingPage}>
                      <Check className="w-4 h-4" /> 完成本页
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 新建 Modal */}
      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="新建 PPT 演讲场景"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowCreate(false)}>取消</Button>
            <Button onClick={handleCreate} loading={creating}>创建并自动解析</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">场景标题 *</label>
            <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="例：产品 X 上市演讲" />
          </div>
          <div>
            <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">PPT 链接（可选）</label>
            <Input value={form.ppt_url} onChange={(e) => setForm({ ...form, ppt_url: e.target.value })} placeholder="https://..." />
            <p className="mt-1 text-xs text-slate-400">填写后系统将自动触发 Mock 解析（5 页占位结构）</p>
          </div>
          <div>
            <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">描述</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 dark:text-slate-100 min-h-[60px] resize-y"
            />
          </div>
          <div>
            <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">及格分</label>
            <Input type="number" value={form.pass_score} onChange={(e) => setForm({ ...form, pass_score: Number(e.target.value) })} />
          </div>
        </div>
      </Modal>
    </div>
  )
}

// PPT 单页视图
function PageView({ page, pageNo, total }: { page: any; pageNo: number; total: number }) {
  const title = page?.title ?? `第 ${pageNo} 页`
  const keyPoints: string[] = page?.key_points ?? []
  const keywords: string[] = page?.keywords ?? []

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
        <Badge variant="info">{pageNo} / {total}</Badge>
      </div>
      {keyPoints.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">讲解要点</p>
          <ul className="space-y-1">
            {keyPoints.map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-400">
                <span className="text-brand-500 mt-0.5">•</span>
                <span>{p}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {keywords.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">必须覆盖关键词</p>
          <div className="flex flex-wrap gap-1">
            {keywords.map((k, i) => (
              <span key={i} className="px-2 py-0.5 rounded text-xs bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-300">#{k}</span>
            ))}
          </div>
        </div>
      )}
      <div className="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-xs text-amber-700 dark:text-amber-300">
        <Sparkles className="w-3 h-3 inline mr-1" />
        点击下方「完成本页」提交本页讲解录音（当前为 Mock：自动判定完成并翻页）
      </div>
    </div>
  )
}

// 评分结果视图（7 维度雷达图 + AI 反馈）
function ResultView({ session }: { session: PPTSession }) {
  const radar = session.radar_scores ?? {}
  const score = session.final_score ?? 0
  const passed = score >= 60

  // 解析 ai_review
  let review: { summary?: string; page_reviews?: any[] } = {}
  try {
    review = session.ai_review ? JSON.parse(session.ai_review as string) : {}
  } catch {
    review = { summary: session.ai_review as string }
  }

  // 雷达图数据（取最大值为参考）
  const values = Object.values(radar)
  const maxValue = Math.max(100, ...(values.length > 0 ? values : [100]))

  return (
    <div className="space-y-5">
      {/* 总分 */}
      <div className={`p-4 rounded-xl border ${passed ? 'bg-emerald-50 border-emerald-200 dark:bg-emerald-900/20 dark:border-emerald-800' : 'bg-rose-50 border-rose-200 dark:bg-rose-900/20 dark:border-rose-800'}`}>
        <div className="flex items-center gap-3">
          <div className={`flex items-center justify-center w-12 h-12 rounded-xl text-white ${passed ? 'bg-gradient-to-br from-emerald-400 to-brand-500' : 'bg-gradient-to-br from-rose-400 to-orange-500'}`}>
            <Trophy className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400">演讲总分</p>
            <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{score} 分</p>
          </div>
          <Badge variant={passed ? 'success' : 'error'}>{passed ? '通过' : '未通过'}</Badge>
        </div>
      </div>

      {/* 7 维度评分（简化条形雷达） */}
      <div>
        <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-2">7 维度评分</p>
        <div className="space-y-2">
          {Object.entries(DIMENSION_LABELS).map(([key, label]) => {
            const v = radar[key] ?? 0
            const pct = Math.min(100, (v / maxValue) * 100)
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="w-24 text-xs text-slate-600 dark:text-slate-400 shrink-0">{label}</span>
                <div className="flex-1 h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.6, ease: 'easeOut' }}
                    className={`h-full rounded-full ${v >= 80 ? 'bg-emerald-500' : v >= 60 ? 'bg-amber-500' : 'bg-rose-500'}`}
                  />
                </div>
                <span className="w-10 text-xs text-slate-500 dark:text-slate-400 text-right">{v}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* AI 总评 */}
      {review.summary && (
        <div>
          <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">AI 总评</p>
          <p className="text-sm text-slate-600 dark:text-slate-300 p-3 rounded-lg bg-slate-50 dark:bg-slate-900/30">{review.summary}</p>
        </div>
      )}

      {/* 分页点评 */}
      {(review.page_reviews?.length ?? 0) > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">分页点评</p>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {(review.page_reviews ?? []).map((pr, i) => (
              <div key={i} className="px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-900/30 text-xs">
                <span className="font-medium text-slate-700 dark:text-slate-300">第 {pr.page_no ?? i + 1} 页：</span>
                <span className="text-slate-600 dark:text-slate-400">{pr.feedback ?? pr.comment}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
