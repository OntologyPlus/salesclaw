import { useState, useCallback, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Lightbulb, Gauge, AlertTriangle, TrendingUp, Award, BookOpen, Target, Sparkles, Loader2 } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Empty from '@/components/ui/Empty'
import Skeleton from '@/components/ui/Skeleton'
import AIInlineAnnotation from '@/components/ai/AIInlineAnnotation'
import useFetch from '@/hooks/useFetch'
import { decisionAPI } from '@/services/decision'
import { contextAPI } from '@/services/context'
import { useContextStore } from '@/stores/context'
import ContextSwitcher from '@/components/ai/ContextSwitcher'
import api from '@/services/api'

export default function DecisionOverviewPage() {
  const ctx = useContextStore()
  const [ctxTick, setCtxTick] = useState(0)
  // AI 洞察
  const [aiInsights, setAiInsights] = useState<{ summary: string; insights: { level: string; message: string }[]; risk_alerts: { message: string }[] } | null>(null)
  const [insightLoading, setInsightLoading] = useState(true)

  // 切换上下文后重新拉取（用 contextAPI.overview 替代 decisionAPI.getOverview，支持 period_end）
  const fetcher = useCallback(async () => {
    if (ctx.scope_type === 'post' && !ctx.period_end) {
      // 默认岗位 + 当前周期：走原有 decision overview 接口
      return await decisionAPI.getOverview()
    }
    // 其他场景：走 context/overview，支持 scope/period_end 参数
    return await contextAPI.overview({
      scope_type: ctx.scope_type,
      scope_id: ctx.scope_id,
      period_type: ctx.period_type,
      period_end: ctx.period_end,
      perspective: ctx.perspective,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.scope_type, ctx.scope_id, ctx.period_type, ctx.period_end, ctx.perspective, ctxTick])

  const { data, loading } = useFetch<any>(fetcher, [ctx.scope_type, ctx.scope_id, ctx.period_type, ctx.period_end, ctx.perspective, ctxTick])

  const handleContextChange = useCallback(() => {
    setCtxTick((t) => t + 1)
  }, [])

  // 加载 AI 洞察
  useEffect(() => {
    api.post<{ data?: { summary?: string; insights?: { level: string; message: string }[]; risk_alerts?: { message: string }[] } }>('/decision/ai-insights')
      .then(res => {
        const d = res.data?.data
        setAiInsights({
          summary: d?.summary ?? '',
          insights: d?.insights ?? [],
          risk_alerts: d?.risk_alerts ?? [],
        })
      })
      .catch(() => setAiInsights(null))
      .finally(() => setInsightLoading(false))
  }, [])

  if (loading && !data) return <div className="p-6"><Skeleton lines={6} /></div>
  if (!data) return <Empty description="暂无数据" />

  return (
    <div>
      <PageHeader
        title="决策总览"
        description="KPI 监控、归因分析与智能决策 · 支持空间/时间/视角三维切换"
        breadcrumbs={[{ label: '决策支持' }, { label: '决策总览' }]}
        icon={<Lightbulb className="w-5 h-5" />}
        gradient
      />

      {/* 全局上下文切换器 */}
      <ContextSwitcher className="mb-6" onChange={handleContextChange} />

      {/* 上下文状态徽章 */}
      <div className="mb-4 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <span>当前视图：</span>
        <span className="px-2 py-0.5 rounded bg-brand-50 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300">{ctx.scope_label}</span>
        <span className="px-2 py-0.5 rounded bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-300">
          {ctx.period_type === 'day' ? '日' : ctx.period_type === 'week' ? '周' : ctx.period_type === 'month' ? '月' : ctx.period_type === 'quarter' ? '季度' : '年'}
        </span>
        {ctx.period_end && (
          <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-300">截至 {ctx.period_end}</span>
        )}
        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300">
          {ctx.perspective === 'management' ? '管理视角' : ctx.perspective === 'customer_development' ? '客户开发视角' : '报表视角'}
        </span>
      </div>

      {/* 关键指标卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <StatCard title="综合能力分" value={data.comprehensive_score ?? 0} icon={<Award className="w-5 h-5" />} color="brand" />
        <StatCard title="拜访达成率" value={`${data.visit_completion ?? 0}%`} icon={<Target className="w-5 h-5" />} color="blue" />
        <StatCard title="行为积分" value={data.total_points ?? 0} icon={<TrendingUp className="w-5 h-5" />} color="emerald" />
        <StatCard title="课程完成率" value={`${data.course_completion ?? 0}%`} icon={<BookOpen className="w-5 h-5" />} color="violet" />
        <StatCard title="预警数" value={data.alerts_count ?? 0} icon={<AlertTriangle className="w-5 h-5" />} color={data.high_alerts_count > 0 ? 'rose' : 'amber'} />
      </div>

      {/* 快捷入口 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/decision/kpi" className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-sky-100 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300">
              <Gauge className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">KPI 监控</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">销售域与培训域 KPI 实时监控</p>
        </Link>

        <Link to="/decision/attribution" className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-100 text-violet-600 dark:bg-violet-900/20 dark:text-violet-400">
              <TrendingUp className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">归因分析</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">各维度对综合能力分的贡献度</p>
        </Link>

        <Link to="/decision/simulation" className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-100 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400">
              <Lightbulb className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">模拟推演</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">What-if 场景模拟与预期分析</p>
        </Link>

        <Link to="/decision/alerts" className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-rose-100 text-rose-600 dark:bg-rose-900/20 dark:text-rose-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">预警中心</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">异常预警与行动建议</p>
        </Link>
      </div>

      {/* AI 内联标注区 */}
      <div className="mt-6 space-y-3">
        {insightLoading ? (
          <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-400">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>AI 正在分析决策数据...</span>
          </div>
        ) : aiInsights ? (
          <>
            {aiInsights.summary && (
              <AIInlineAnnotation message={aiInsights.summary} level="info" label="AI 摘要" />
            )}
            {aiInsights.risk_alerts.map((alert, i) => (
              <AIInlineAnnotation key={`risk-${i}`} message={alert.message} level="warning" label="风险告警" />
            ))}
            {aiInsights.insights.slice(0, 3).map((ins, i) => (
              <AIInlineAnnotation
                key={`ins-${i}`}
                message={ins.message}
                level={(ins.level as 'info' | 'warning' | 'success') || 'info'}
                label="AI 洞察"
              />
            ))}
            {aiInsights.insights.length === 0 && !aiInsights.summary && (
              <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-400">
                <Sparkles className="w-3 h-3" />
                <span>暂无 AI 洞察</span>
              </div>
            )}
          </>
        ) : (
          <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-400">
            <Sparkles className="w-3 h-3" />
            <span>AI 洞察暂不可用</span>
          </div>
        )}
      </div>
    </div>
  )
}
