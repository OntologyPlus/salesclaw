import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  GitBranch, CheckCircle, Clock, XCircle, AlertCircle,
  TrendingUp, ChevronRight, Target, BookOpen, BarChart3, Search,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import { decisionAPI } from '@/services/decision'

const STEP_LABELS: Record<string, string> = {
  diagnosis: '诊断归因',
  confirmation: '确认执行',
  execution: '执行中',
  verification: '效果验证',
  closure_judgment: '判定闭环',
}

const STATUS_ICON: Record<string, { icon: any; color: string }> = {
  done: { icon: CheckCircle, color: '#10b981' },
  active: { icon: Clock, color: '#3b82f6' },
  pending: { icon: AlertCircle, color: '#94a3b8' },
}

const CLOSURE_COLORS: Record<string, string> = {
  closed: '#10b981',
  partial: '#f59e0b',
  unresolved: '#ef4444',
}

export default function FollowupPage() {
  const navigate = useNavigate()
  const { data: panelData, loading: panelLoading } = useFetch(
    () => decisionAPI.getTeamClosure(),
    [],
  )

  if (panelLoading) return <div className="p-6 text-slate-500 dark:text-slate-400 dark:text-slate-500">加载中...</div>
  if (!panelData) return <Empty description="暂无随访闭环数据" />

  const dist = panelData.status_distribution || {}
  const total = panelData.total_executions || 0
  const rate = panelData.signal_elimination_rate || 0

  return (
    <div>
      <PageHeader
        title="随访闭环"
        description="诊断建议 → 确认执行 → 效果验证 → 信号消除矩阵判定 → 范式沉淀"
        breadcrumbs={[{ label: '决策支持' }, { label: '随访闭环' }]}
        icon={<GitBranch className="w-5 h-5" />}
      />

      {/* 当月汇总卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500 mb-1">当月执行总数</p>
          <p className="text-3xl font-bold text-slate-800 dark:text-slate-100">{total}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500 mb-1">已闭环</p>
          <p className="text-3xl font-bold" style={{ color: '#10b981' }}>
            {dist.closed || 0}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500 mb-1">部分闭环</p>
          <p className="text-3xl font-bold" style={{ color: '#f59e0b' }}>
            {dist.partial || 0}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500 mb-1">信号消除率</p>
          <p className="text-3xl font-bold" style={{ color: rate >= 80 ? '#10b981' : rate >= 50 ? '#f59e0b' : '#ef4444' }}>
            {rate}%
          </p>
        </div>
      </div>

      {/* 信号消除矩阵 + 未解决项 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* 领域闭环分布 */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-slate-500 dark:text-slate-400 dark:text-slate-500" />
            各领域闭环情况
          </h3>
          <div className="space-y-3">
            {Object.entries(panelData.domain_breakdown || {}).map(([domain, info]: any) => {
              const dr = info.closure_rate || 0
              return (
                <div key={domain} className="flex items-center gap-3">
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-200 w-16">{domain}</span>
                  <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden dark:bg-slate-700">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${dr}%`,
                        background: `linear-gradient(90deg, ${dr >= 80 ? '#10b981' : dr >= 50 ? '#f59e0b' : '#ef4444'}, ${dr >= 80 ? '#34d399' : '#fbbf24'})`,
                      }}
                    />
                  </div>
                  <span className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500 w-12 text-right">{dr}%</span>
                  <span className="text-xs text-slate-400 dark:text-slate-500">({info.closed}/{info.total})</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* 未解决问题 */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-4 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-amber-500" />
            待解决问题
            {(panelData.unresolved_items || []).length > 0 && (
              <span className="ml-auto text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full dark:bg-red-900/40 dark:text-red-300">
                {panelData.unresolved_items.length} 项
              </span>
            )}
          </h3>
          {(!panelData.unresolved_items || panelData.unresolved_items.length === 0) ? (
            <p className="text-sm text-slate-400 dark:text-slate-500">暂无未解决问题</p>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {(panelData.unresolved_items || []).slice(0, 8).map((item: any) => (
                <div
                  key={item.execution_id}
                  className="flex items-center gap-3 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50 hover:bg-red-50 dark:hover:bg-red-900/20 cursor-pointer transition-colors"
                  onClick={() => navigate(`/decision/loop/followup/${item.execution_id}`)}
                >
                  <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-700 dark:text-slate-200 truncate">{item.title}</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      {item.domain} · 代表 {item.rep_id} · {item.escalation}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-300" />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 范式库入口 */}
      <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-indigo-50 to-purple-50 p-5 mb-6 dark:border-slate-800 dark:from-slate-800 dark:to-slate-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BookOpen className="w-6 h-6 text-indigo-500" />
            <div>
              <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">通用范式库</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500">
                从成功闭环中提取有效方法 · 已沉淀 {panelData.paradigm_library?.total_paradigms || 0} 条范式
              </p>
            </div>
          </div>
          <button
            onClick={() => navigate('/decision/paradigms')}
            className="flex items-center gap-1 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            查看范式库 <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 信号消除矩阵说明 */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
        <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-3 flex items-center gap-2">
          <Target className="w-4 h-4 text-slate-500 dark:text-slate-400 dark:text-slate-500" />
          信号消除矩阵
        </h3>
        <div className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500 mb-3">
          {panelData.reference_2_matrix?.concept}
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 rounded-lg bg-green-50 border border-green-200 dark:bg-green-900/30 dark:border-green-700">
            <p className="text-sm font-semibold text-green-700 dark:text-green-300">closed · 闭环</p>
            <p className="text-xs text-green-600 dark:text-green-400 mt-1">{panelData.reference_2_matrix?.closed_definition}</p>
          </div>
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-900/30 dark:border-amber-700">
            <p className="text-sm font-semibold text-amber-700 dark:text-amber-300">partial · 部分闭环</p>
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">{panelData.reference_2_matrix?.partial_definition}</p>
          </div>
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 dark:bg-red-900/30 dark:border-red-700">
            <p className="text-sm font-semibold text-red-700 dark:text-red-300">unresolved · 未解决</p>
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">{panelData.reference_2_matrix?.unresolved_definition}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// 辅助子组件：五步进度条
function StepBar({ steps }: { steps: any[] }) {
  if (!steps || steps.length === 0) return null
  return (
    <div className="flex items-center gap-0">
      {steps.map((s: any, idx: number) => {
        const meta = STATUS_ICON[s.status] || STATUS_ICON.pending
        const Icon = meta.icon
        return (
          <div key={s.step} className="flex items-center flex-1">
            <div className="flex flex-col items-center flex-1">
              <Icon className="w-5 h-5" style={{ color: meta.color }} />
              <span className="text-xs mt-1 text-slate-600 dark:text-slate-300">{STEP_LABELS[s.step] || s.step}</span>
            </div>
            {idx < steps.length - 1 && (
              <div className="h-px flex-1 min-w-[20px] bg-slate-200 mx-1 dark:bg-slate-700" />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function FollowupDetailPage() {
  const navigate = useNavigate()
  const executionId = parseInt(window.location.pathname.split('/').pop() || '0')
  const [actualMetrics, setActualMetrics] = useState('{}')
  const [submitting, setSubmitting] = useState(false)

  const { data, loading, refetch } = useFetch(
    () => decisionAPI.getFollowup(executionId),
    [executionId],
  )

  if (loading) return <div className="p-6 text-slate-500 dark:text-slate-400 dark:text-slate-500">加载中...</div>
  if (!data || data.error) return <Empty description={data?.error || '执行记录不存在'} />

  const ex = data.execution || {}

  const handleComplete = async () => {
    setSubmitting(true)
    try {
      let metrics = {}
      try { metrics = JSON.parse(actualMetrics); } catch { /* keep empty */ }
      await decisionAPI.completeLoop(executionId, metrics)
      refetch()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="随访详情"
        description={`执行记录 #${executionId}`}
        breadcrumbs={[
          { label: '决策支持' },
          { label: '随访闭环', path: '/decision/followup' },
          { label: `#${executionId}` },
        ]}
        icon={<GitBranch className="w-5 h-5" />}
      />

      {/* 五步进度 */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 mb-6 dark:bg-slate-900 dark:border-slate-800">
        <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 dark:text-slate-500 mb-4 uppercase tracking-wide">全链路进度</h3>
        <StepBar steps={data.chain_steps || []} />
      </div>

      {/* 执行信息 + 效果 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-3">执行信息</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400 dark:text-slate-500">标题</dt>
              <dd className="text-slate-800 dark:text-slate-100 font-medium">{ex.title}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400 dark:text-slate-500">领域</dt>
              <dd className="text-slate-800 dark:text-slate-100">{ex.domain}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400 dark:text-slate-500">代表</dt>
              <dd className="text-slate-800 dark:text-slate-100">#{ex.rep_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400 dark:text-slate-500">状态</dt>
              <dd>
                <span
                  className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
                  style={{ background: CLOSURE_COLORS[ex.status] || '#94a3b8' }}
                >
                  {ex.status}
                </span>
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400 dark:text-slate-500">创建时间</dt>
              <dd className="text-slate-600 dark:text-slate-300">{ex.created_at}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:bg-slate-900 dark:border-slate-800">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-3">效果验证</h3>
          {data.effectiveness_score != null ? (
            <div className="text-center py-4">
              <div
                className="inline-flex items-center justify-center w-24 h-24 rounded-full text-3xl font-bold text-white"
                style={{
                  background:
                    (data.effectiveness_score || 0) >= 80 ? '#10b981'
                    : (data.effectiveness_score || 0) >= 50 ? '#f59e0b'
                    : '#ef4444',
                }}
              >
                {data.effectiveness_score}
              </div>
              <p className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500 mt-2">有效性评分 / 100</p>
            </div>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500 text-center py-4">尚未完成效果验证</p>
          )}
          {/* 三项指标对比 */}
          {(data.baseline_metrics || data.target_metrics || data.actual_metrics) && (
            <div className="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
              <div>
                <p className="text-slate-400 dark:text-slate-500 mb-0.5">基线</p>
                <p className="text-slate-700 dark:text-slate-200 font-mono">
                  {JSON.stringify(data.baseline_metrics || {}).slice(0, 40)}
                </p>
              </div>
              <div>
                <p className="text-slate-400 dark:text-slate-500 mb-0.5">目标</p>
                <p className="text-slate-700 dark:text-slate-200 font-mono">
                  {JSON.stringify(data.target_metrics || {}).slice(0, 40)}
                </p>
              </div>
              <div>
                <p className="text-slate-400 dark:text-slate-500 mb-0.5">实际</p>
                <p className="text-slate-700 dark:text-slate-200 font-mono">
                  {JSON.stringify(data.actual_metrics || {}).slice(0, 40)}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 关联任务 */}
      {data.tasks && data.tasks.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 mb-6 dark:bg-slate-900 dark:border-slate-800">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-3">关联任务</h3>
          <div className="space-y-2">
            {data.tasks.map((t: any) => (
              <div key={t.id} className="flex items-center gap-3 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                <CheckCircle
                  className="w-4 h-4"
                  style={{ color: t.status === 'completed' ? '#10b981' : '#94a3b8' }}
                />
                <span className="text-sm text-slate-700 dark:text-slate-200 flex-1">{t.title}</span>
                <span className="text-xs text-slate-400 dark:text-slate-500">{t.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 完成执行表单 */}
      {data.can_complete && (
        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 mb-6">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-3">完成执行 & 触发效果验证</h3>
          <textarea
            className="w-full rounded-lg border border-slate-300 p-3 text-sm font-mono bg-white mb-3 dark:bg-slate-900 dark:border-slate-800"
            rows={4}
            placeholder='实际指标 JSON，例如 {"visit_completion_rate": 0.92, "training_score": 85}'
            value={actualMetrics}
            onChange={(e) => setActualMetrics(e.target.value)}
          />
          <button
            disabled={submitting}
            onClick={handleComplete}
            className="px-5 py-2.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {submitting ? '处理中...' : '完成执行 → 验证效果 → 判定闭环'}
          </button>
          <p className="text-xs text-slate-500 dark:text-slate-400 dark:text-slate-500 mt-2">
            提交后将自动调用效果验证（effect_tracking）和闭环判定（信号消除矩阵）
          </p>
        </div>
      )}

      {/* 范式提取入口 */}
      {data.can_extract_paradigm && (
        <div className="rounded-2xl border border-green-200 bg-gradient-to-r from-green-50 to-emerald-50 p-5 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BookOpen className="w-6 h-6 text-green-600" />
              <div>
                <h3 className="text-base font-semibold text-green-800">闭环成功 · 可沉淀为通用范式</h3>
                <p className="text-sm text-green-600">
                  有效性评分 {data.effectiveness_score}/100，高于阈值，可提取解决方法为通用范式
                </p>
              </div>
            </div>
            <button
              onClick={() => navigate(`/decision/paradigms?execution_id=${executionId}`)}
              className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition-colors"
            >
              提取范式
            </button>
          </div>
        </div>
      )}

      {/* 下游提示 */}
      {data.next_action && (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:bg-slate-800 dark:border-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400 dark:text-slate-500 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            下一步: {data.next_action}
          </p>
        </div>
      )}
    </div>
  )
}
