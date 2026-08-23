import { useState } from 'react'
import { TrendingUp, Sparkles, BarChart3, Users, RefreshCw, AlertCircle } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import SectionCard from '@/components/layout/SectionCard'
import { useFetch } from '@/hooks/useFetch'
import { trainingEffectAPI } from '@/services/trainingEffect'

/**
 * 培训效果归因总览（CEO 看板入口）
 *
 * 设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §11.1
 */
export default function EffectOverviewPage() {
  const [period, setPeriod] = useState(30)
  const { data, loading, error, refetch } = useFetch(
    () => trainingEffectAPI.getOverview({ period_days: period }),
    [period],
  )

  const overview = data || {}

  return (
    <div className="space-y-6">
      <PageHeader
        title="培训效果归因"
        description={`近 ${period} 天培训效果整体反馈 — 含滞后期回填、类比组、AI 归因`}
        breadcrumbs={[{ label: '学习成长' }, { label: '培训效果归因' }]}
        icon={<TrendingUp className="w-5 h-5" />}
        actions={
          <>
            <select
              className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={period}
              onChange={e => setPeriod(Number(e.target.value))}
            >
              <option value={30}>近 30 天</option>
              <option value={90}>近 90 天</option>
              <option value={180}>近 180 天</option>
            </select>
            <Button variant="secondary" onClick={refetch}>
              <RefreshCw size={14} className="mr-1" /> 刷新
            </Button>
          </>
        }
      />

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle size={16} className="shrink-0" /> 加载失败：{(error as Error).message}
        </div>
      )}

      {loading || !data ? (
        <Skeleton lines={4} />
      ) : overview.completion_count === 0 ? (
        <Empty
          icon={<BarChart3 size={48} />}
          description={`近 ${period} 天暂无培训完成事件。当用户完成课程 / 演练 / 考试时将自动建归因执行`}
        />
      ) : (
        <>
          {/* 顶部 KPI 卡片 */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <KpiCard
              icon={<TrendingUp size={18} />}
              color="brand"
              label="总培训次数"
              value={overview.completion_count}
              hint={`完成 ${overview.completed_count} / 进行中 ${overview.executing_count} / 待回填 ${overview.planned_count}`}
            />
            <KpiCard
              icon={<Sparkles size={18} />}
              color="amber"
              label="平均 effectiveness_score"
              value={overview.overall_effectiveness_avg ?? '-'}
              hint="确定性算法计算（baseline→actual）"
            />
            <KpiCard
              icon={<BarChart3 size={18} />}
              color="emerald"
              label="达标率（≥ 80 分）"
              value={
                overview.achievement_rate != null
                  ? `${Math.round(overview.achievement_rate * 100)}%`
                  : '-'
              }
              hint="completed 中 ≥ 80 分占比"
            />
            <KpiCard
              icon={<Users size={18} />}
              color="rose"
              label="窗口回填"
              value={`30/180 d`}
              hint="滞后窗口自动调度"
            />
          </div>

          {/* 各维度画像提升 */}
          <SectionCard title="分维度画像提升（已完成执行）" icon={<BarChart3 className="w-4 h-4" />}>
            {overview.by_dimension && overview.by_dimension.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-400 dark:text-slate-500 border-b dark:border-slate-800">
                      <th className="px-5 py-2 font-medium">维度</th>
                      <th className="px-5 py-2 font-medium">样本数</th>
                      <th className="px-5 py-2 font-medium">平均画像 delta</th>
                      <th className="px-5 py-2 font-medium">提升比例</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {overview.by_dimension.map((d: any) => (
                      <tr key={d.dim}>
                        <td className="px-5 py-2 font-medium text-slate-900 dark:text-slate-100">{d.dim}</td>
                        <td className="px-5 py-2 text-slate-600 dark:text-slate-300">{d.n}</td>
                        <td className="px-5 py-2 text-slate-600 dark:text-slate-300">{d.mean_delta.toFixed(2)}</td>
                        <td className="px-5 py-2">
                          <Badge variant={d.achievement_rate >= 0.7 ? 'success' : d.achievement_rate >= 0.5 ? 'warning' : 'default'}>
                            {Math.round(d.achievement_rate * 100)}%
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-5 py-4 text-sm text-slate-400 dark:text-slate-500">暂无完成的执行</p>
            )}
          </SectionCard>

          <div className="text-xs text-slate-400 dark:text-slate-500">
            * AI 归因评估采用 effect-evaluator agent，结果落 reasoning_chain_id，可点开查看推理链与 provenance。
          </div>
        </>
      )}
    </div>
  )
}

const kpiColorMap: Record<string, string> = {
  brand: 'bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400',
  emerald: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400',
  amber: 'bg-amber-100 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400',
  rose: 'bg-rose-100 text-rose-600 dark:bg-rose-900/20 dark:text-rose-400',
}

function KpiCard({ icon, label, value, hint, color = 'brand' }: {
  icon: React.ReactNode
  label: string
  value: any
  hint?: string
  color?: string
}) {
  return (
    <div className="p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark transition-all hover:shadow-md dark:hover:shadow-black/20">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
          {hint && <div className="mt-1 text-xs text-slate-400 dark:text-slate-500">{hint}</div>}
        </div>
        <div className={`flex items-center justify-center w-10 h-10 rounded-xl shrink-0 ${kpiColorMap[color] ?? kpiColorMap.brand}`}>
          {icon}
        </div>
      </div>
    </div>
  )
}
