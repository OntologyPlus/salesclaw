import { useState, useCallback } from 'react'
import { TrendingUp, Plus, Play, CheckCircle, Activity, Target, X, Sparkles, Bot, Link2 } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Button from '@/components/ui/Button'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { effectTrackingApi } from '@/services/effectTracking'

// 执行记录
interface Execution {
  execution_id: number
  decision_type: string
  title: string
  description?: string
  baseline_metrics?: Record<string, number>
  target_metrics?: Record<string, number>
  actual_metrics?: Record<string, number>
  status: string
  started_at?: string | null
  completed_at?: string | null
  effectiveness_score?: number | null
  created_at?: string | null
}

// 效果计算结果
interface Effectiveness {
  score: number
  dimensions?: Record<string, {
    baseline: number | null
    target: number | null
    actual: number | null
    achievement_rate: number
  }>
  insights?: string[]
}

// 状态配置
const STATUS_CONFIG: Record<string, { label: string; color: string; badge: string }> = {
  planned: { label: '待执行', color: 'text-sky-600 dark:text-sky-400', badge: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300' },
  executing: { label: '执行中', color: 'text-amber-600 dark:text-amber-400', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  completed: { label: '已完成', color: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
  failed: { label: '失败', color: 'text-rose-600 dark:text-rose-400', badge: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
}

// 决策类型映射
const TYPE_LABELS: Record<string, string> = {
  visit_plan: '拜访计划',
  training: '培训投入',
  coverage: '覆盖策略',
}

// 效果分颜色
function scoreColor(score: number | null | undefined): string {
  if (score == null) return 'bg-slate-300'
  if (score >= 80) return 'bg-emerald-500'
  if (score >= 60) return 'bg-amber-500'
  return 'bg-rose-500'
}

export default function EffectTrackingPage() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [showCreate, setShowCreate] = useState(false)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [effectiveness, setEffectiveness] = useState<Effectiveness | null>(null)
  const [loadingEffect, setLoadingEffect] = useState(false)
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  // 新建表单
  const [form, setForm] = useState({
    title: '',
    description: '',
    decision_type: 'visit_plan',
    baselineText: '',
    targetText: '',
  })

  const { data, loading } = useFetch<{ items: Execution[] } | Execution[]>(
    () => effectTrackingApi.list(statusFilter || undefined, 50),
    [statusFilter, refreshKey]
  )

  const executions: Execution[] = Array.isArray(data) ? data : (data?.items ?? [])

  // 统计
  const total = executions.length
  const inProgress = executions.filter(e => e.status === 'executing').length
  const completed = executions.filter(e => e.status === 'completed').length
  const scores = executions.filter(e => e.effectiveness_score != null).map(e => e.effectiveness_score as number)
  const avgScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0

  // 刷新
  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  // 解析指标文本（每行 key=value）
  const parseMetrics = (text: string): Record<string, number> => {
    const result: Record<string, number> = {}
    text.split('\n').forEach(line => {
      const trimmed = line.trim()
      if (!trimmed) return
      const [k, v] = trimmed.split('=')
      if (k && v != null) {
        const num = Number(v.trim())
        if (!isNaN(num)) result[k.trim()] = num
      }
    })
    return result
  }

  // 创建执行
  const handleCreate = async () => {
    if (!form.title.trim()) {
      toast('请输入标题', 'error')
      return
    }
    try {
      await effectTrackingApi.create({
        decision_type: form.decision_type,
        title: form.title.trim(),
        description: form.description.trim(),
        baseline: parseMetrics(form.baselineText),
        target: parseMetrics(form.targetText),
      })
      toast('创建成功', 'success')
      setShowCreate(false)
      setForm({ title: '', description: '', decision_type: 'visit_plan', baselineText: '', targetText: '' })
      refresh()
    } catch {
      toast('创建失败', 'error')
    }
  }

  // 操作（开始/完成）
  const handleAction = async (id: number, action: 'start' | 'complete') => {
    setActionLoading(id)
    try {
      if (action === 'start') {
        await effectTrackingApi.start(id)
        toast('已开始执行', 'success')
      } else {
        await effectTrackingApi.complete(id)
        toast('已完成执行', 'success')
      }
      refresh()
    } catch {
      toast('操作失败', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  // 查看效果
  const handleViewEffect = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null)
      setEffectiveness(null)
      return
    }
    setExpandedId(id)
    setLoadingEffect(true)
    try {
      const result = await effectTrackingApi.getEffectiveness(id)
      setEffectiveness(result)
    } catch {
      setEffectiveness(null)
    } finally {
      setLoadingEffect(false)
    }
  }

  // N+AI原生闭环：经编排器 evaluate 意图做 AI 效果归因评估
  const [aiEval, setAiEval] = useState<{
    source?: string
    summary?: string
    achievement_rate?: number
    verdict?: string
    reasons?: { factor?: string; status?: string; contribution?: number; detail?: string }[]
    reasoning_chain_id?: string | number | null
    provenance?: Record<string, unknown>
  } | null>(null)
  const [loadingAiEval, setLoadingAiEval] = useState(false)

  // decision_type → 业务域映射，供 AI 效果评估的 domain 入参
  const DOMAIN_OF: Record<string, string> = {
    visit_plan: 'visit',
    training: 'training',
    coverage: 'coverage',
  }

  const handleAiEvaluate = async (id: number, decisionType?: string) => {
    setLoadingAiEval(true)
    try {
      const domain = (decisionType && DOMAIN_OF[decisionType]) || 'general'
      const result = await effectTrackingApi.aiEvaluate(id, domain)
      setAiEval(result)
      toast('AI 评估完成', 'success')
    } catch {
      toast('AI 评估失败', 'error')
      setAiEval(null)
    } finally {
      setLoadingAiEval(false)
    }
  }

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>

  return (
    <div>
      <PageHeader
        title="效果追踪"
        description="决策执行全生命周期追踪与效果评估"
        breadcrumbs={[{ label: '决策支持', path: '/decision' }, { label: '效果追踪' }]}
        icon={<TrendingUp className="w-5 h-5" />}
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="总执行数" value={total} icon={<Activity className="w-5 h-5" />} color="brand" />
        <StatCard title="执行中" value={inProgress} icon={<Play className="w-5 h-5" />} color="amber" />
        <StatCard title="已完成" value={completed} icon={<CheckCircle className="w-5 h-5" />} color="emerald" />
        <StatCard title="平均效果分" value={avgScore} icon={<Target className="w-5 h-5" />} color="violet" />
      </div>

      {/* 筛选栏 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">状态：</span>
          {['', 'planned', 'executing', 'completed'].map(s => (
            <button
              key={s || 'all'}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                statusFilter === s
                  ? 'bg-brand-600 text-white'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
              }`}
            >
              {s === '' ? '全部' : STATUS_CONFIG[s]?.label || s}
            </button>
          ))}
        </div>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4" />
          新建执行
        </Button>
      </div>

      {/* 执行列表 */}
      {executions.length > 0 ? (
        <div className="space-y-3">
          {executions.map(exec => {
            const cfg = STATUS_CONFIG[exec.status] || STATUS_CONFIG.planned
            const score = exec.effectiveness_score
            const isExpanded = expandedId === exec.execution_id
            return (
              <div key={exec.execution_id} className="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
                {/* 行主体 */}
                <div className="p-4 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg.badge}`}>
                        {cfg.label}
                      </span>
                      <span className="text-xs text-slate-400">
                        {TYPE_LABELS[exec.decision_type] || exec.decision_type}
                      </span>
                      <span className="text-xs text-slate-400">#{exec.execution_id}</span>
                    </div>
                    <h4 className="font-medium text-slate-900 dark:text-slate-100 truncate">
                      {exec.title}
                    </h4>
                    {exec.description && (
                      <p className="text-sm text-slate-500 dark:text-slate-400 truncate mt-0.5">
                        {exec.description}
                      </p>
                    )}
                  </div>

                  {/* 效果分 */}
                  <div className="flex-shrink-0 w-24">
                    {score != null ? (
                      <div>
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="text-lg font-semibold text-slate-900 dark:text-slate-100">{score}</span>
                          <span className="text-xs text-slate-400">分</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                          <div className={`h-full ${scoreColor(score)}`} style={{ width: `${score}%` }} />
                        </div>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">未评估</span>
                    )}
                  </div>

                  {/* 创建时间 */}
                  <div className="flex-shrink-0 w-32 text-right">
                    <p className="text-xs text-slate-400">
                      {exec.created_at ? new Date(exec.created_at).toLocaleDateString('zh-CN') : '-'}
                    </p>
                  </div>

                  {/* 操作 */}
                  <div className="flex-shrink-0 flex items-center gap-1.5">
                    {exec.status === 'planned' && (
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={actionLoading === exec.execution_id}
                        onClick={() => handleAction(exec.execution_id, 'start')}
                      >
                        <Play className="w-3.5 h-3.5" />
                        开始
                      </Button>
                    )}
                    {exec.status === 'executing' && (
                      <Button
                        size="sm"
                        variant="primary"
                        loading={actionLoading === exec.execution_id}
                        onClick={() => handleAction(exec.execution_id, 'complete')}
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                        完成
                      </Button>
                    )}
                    {exec.status === 'completed' && (
                      <div className="flex items-center gap-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleViewEffect(exec.execution_id)}
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          {isExpanded ? '收起' : '效果'}
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={loadingAiEval && expandedId === exec.execution_id}
                          onClick={() => {
                            setExpandedId(exec.execution_id)
                            handleAiEvaluate(exec.execution_id, exec.decision_type)
                          }}
                          title="经 AI 编排器生成可解释的效果归因"
                        >
                          <Bot className="w-3.5 h-3.5" />
                          AI 评估
                        </Button>
                      </div>
                    )}
                  </div>
                </div>

                {/* 展开效果详情 */}
                {isExpanded && exec.status === 'completed' && (
                  <div className="border-t border-slate-100 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-900/40 space-y-4">
                    {loadingEffect ? (
                      <p className="text-sm text-slate-400">计算效果中...</p>
                    ) : effectiveness ? (
                      <EffectDetail effectiveness={effectiveness} />
                    ) : (
                      <p className="text-sm text-slate-400">暂无效果数据</p>
                    )}

                    {/* N+AI原生闭环：编排器 evaluate 意图产出可解释效果归因 */}
                    <div className="border-t border-slate-200 dark:border-slate-700 pt-4">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs font-medium text-slate-500 uppercase flex items-center gap-1.5">
                          <Bot className="w-3.5 h-3.5 text-indigo-500" />
                          AI 效果归因（编排器）
                        </p>
                        {aiEval && (
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                            aiEval.source === 'ai'
                              ? 'bg-indigo-500/15 text-indigo-400'
                              : 'bg-slate-500/15 text-slate-400'
                          }`}>
                            {aiEval.source === 'ai' ? 'AI 编排生成' : '规则降级'}
                          </span>
                        )}
                      </div>
                      {loadingAiEval ? (
                        <p className="text-sm text-slate-400">AI 推理中...</p>
                      ) : aiEval ? (
                        <div className="space-y-3">
                          {aiEval.summary && (
                            <p className="text-sm text-slate-600 dark:text-slate-300">{aiEval.summary}</p>
                          )}
                          {aiEval.reasons && aiEval.reasons.length > 0 && (
                            <div className="space-y-1.5">
                              {aiEval.reasons.map((r, i) => (
                                <div key={i} className="flex items-start gap-2 text-sm">
                                  <span className={`mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                    r.status === 'above_target'
                                      ? 'bg-emerald-500/15 text-emerald-500'
                                      : r.status === 'below_target'
                                        ? 'bg-rose-500/15 text-rose-500'
                                        : 'bg-slate-500/15 text-slate-400'
                                  }`}>
                                    {r.factor}
                                  </span>
                                  <span className="text-slate-500 dark:text-slate-400">
                                    {r.detail}
                                    {r.contribution != null && `（贡献 ${Math.round(r.contribution * 100)}%）`}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                          {aiEval.reasoning_chain_id && (
                            <a
                              href={`/decision/reasoning-chain/${aiEval.reasoning_chain_id}`}
                              className="inline-flex items-center gap-1 text-xs text-indigo-500 hover:underline"
                            >
                              <Link2 className="w-3.5 h-3.5" />
                              查看推理链 {String(aiEval.reasoning_chain_id).slice(0, 8)}
                            </a>
                          )}
                        </div>
                      ) : (
                        <p className="text-sm text-slate-400">点击「AI 评估」生成可解释的效果归因</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <Empty description="暂无执行记录，点击「新建执行」开始追踪决策效果" />
      )}

      {/* 创建对话框 */}
      {showCreate && (
        <CreateDialog
          form={form}
          setForm={setForm}
          onCreate={handleCreate}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  )
}

// 效果详情组件
function EffectDetail({ effectiveness }: { effectiveness: Effectiveness }) {
  const { score, dimensions, insights } = effectiveness
  return (
    <div className="space-y-4">
      {/* 总分 */}
      <div className="flex items-center gap-3">
        <div className={`flex items-center justify-center w-14 h-14 rounded-xl ${scoreColor(score)} text-white`}>
          <span className="text-xl font-bold">{score}</span>
        </div>
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">综合效果得分</p>
          <p className="text-xs text-slate-400">
            {score >= 80 ? '优秀' : score >= 60 ? '良好' : '待改进'}
          </p>
        </div>
      </div>

      {/* 各维度达成率 */}
      {dimensions && Object.keys(dimensions).length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500 mb-2 uppercase">维度达成率</p>
          <div className="space-y-2">
            {Object.entries(dimensions).map(([metric, info]) => {
              const ratePct = Math.round((info.achievement_rate || 0) * 100)
              return (
                <div key={metric} className="flex items-center gap-3">
                  <span className="text-sm text-slate-600 dark:text-slate-300 w-28 truncate">{metric}</span>
                  <div className="flex-1 h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                    <div
                      className={`h-full ${scoreColor(ratePct)}`}
                      style={{ width: `${Math.min(100, ratePct)}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-500 w-12 text-right">{ratePct}%</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 洞察 */}
      {insights && insights.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500 mb-2 uppercase">洞察</p>
          <ul className="space-y-1">
            {insights.map((ins, i) => (
              <li key={i} className="text-sm text-slate-600 dark:text-slate-300 flex items-start gap-1.5">
                <span className="text-brand-500 mt-0.5">•</span>
                <span>{ins}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// 创建对话框
function CreateDialog({
  form,
  setForm,
  onCreate,
  onClose,
}: {
  form: { title: string; description: string; decision_type: string; baselineText: string; targetText: string }
  setForm: (f: typeof form) => void
  onCreate: () => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-lg mx-4 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between p-4 border-b border-slate-100 dark:border-slate-700">
          <h3 className="font-semibold text-slate-900 dark:text-slate-100">新建决策执行</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 表单 */}
        <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="block text-sm text-slate-500 mb-1">标题 *</label>
            <input
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 dark:bg-slate-900 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.title}
              onChange={e => setForm({ ...form, title: e.target.value })}
              placeholder="如：提升本月拜访频次"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-500 mb-1">决策类型</label>
            <select
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 dark:bg-slate-900 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.decision_type}
              onChange={e => setForm({ ...form, decision_type: e.target.value })}
            >
              <option value="visit_plan">拜访计划</option>
              <option value="training">培训投入</option>
              <option value="coverage">覆盖策略</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-slate-500 mb-1">描述</label>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 dark:bg-slate-900 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              rows={2}
              value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder="决策背景与预期"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-slate-500 mb-1">
                Baseline 指标
                <span className="text-xs text-slate-400 ml-1">每行 key=value</span>
              </label>
              <textarea
                className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 dark:bg-slate-900 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none font-mono"
                rows={4}
                value={form.baselineText}
                onChange={e => setForm({ ...form, baselineText: e.target.value })}
                placeholder={'visit_count=5\ncoverage_rate=60'}
              />
            </div>
            <div>
              <label className="block text-sm text-slate-500 mb-1">
                Target 指标
                <span className="text-xs text-slate-400 ml-1">每行 key=value</span>
              </label>
              <textarea
                className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 dark:bg-slate-900 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none font-mono"
                rows={4}
                value={form.targetText}
                onChange={e => setForm({ ...form, targetText: e.target.value })}
                placeholder={'visit_count=12\ncoverage_rate=80'}
              />
            </div>
          </div>
        </div>

        {/* 底部 */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-slate-100 dark:border-slate-700">
          <Button variant="secondary" size="sm" onClick={onClose}>取消</Button>
          <Button size="sm" onClick={onCreate}>
            <Plus className="w-4 h-4" />
            创建
          </Button>
        </div>
      </div>
    </div>
  )
}
