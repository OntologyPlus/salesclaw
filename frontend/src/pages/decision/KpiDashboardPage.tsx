import { Gauge } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import { decisionAPI } from '@/services/decision'

const STATUS_COLOR: Record<string, string> = {
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
}

interface KpiItem {
  key: string
  name: string
  value: number
  target: number
  unit: string
  status: string
}

export default function KpiDashboardPage() {
  const { data, loading } = useFetch(() => decisionAPI.getKpi(), [])

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const salesKpis: KpiItem[] = data.sales_kpis || []
  const trainingKpis: KpiItem[] = data.training_kpis || []
  const allKpis = [...salesKpis, ...trainingKpis]
  const chartData = allKpis.map(k => ({ name: k.name, value: k.value, target: k.target, status: k.status }))

  return (
    <div>
      <PageHeader
        title="KPI 监控看板"
        description="销售域与培训域关键指标实时监控"
        breadcrumbs={[{ label: '决策支持', path: '/decision' }, { label: 'KPI 监控' }]}
        icon={<Gauge className="w-5 h-5" />}
        actions={<AIActionButton label="AI KPI分析" prompt="分析我的KPI达标情况，给出提升建议" variant="ghost" size="sm" />}
      />

      {/* 综合能力分概览 */}
      {data.score && (
        <div className="mb-6 p-5 rounded-2xl bg-gradient-to-r from-brand-600 to-violet-500 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-white/80 text-sm">综合能力分</p>
              <p className="text-3xl font-bold mt-1">{data.score.comprehensive_score}</p>
            </div>
            <div className="flex gap-6">
              <div className="text-center">
                <p className="text-white/80 text-xs">行为分</p>
                <p className="text-xl font-semibold">{data.score.behavior_score}</p>
              </div>
              <div className="text-center">
                <p className="text-white/80 text-xs">能力分</p>
                <p className="text-xl font-semibold">{data.score.ability_score}</p>
              </div>
              <div className="text-center">
                <p className="text-white/80 text-xs">业绩分</p>
                <p className="text-xl font-semibold">{data.score.performance_score}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* KPI 柱状图 */}
      <div className="mb-6 p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
        <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-4">KPI 达成情况</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#94a3b8" />
            <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }}
              formatter={(value: number, _name: string, props: { payload?: { target?: number; unit?: string } }) =>
                [`${value}${props?.payload?.unit || ''}（目标 ${props?.payload?.target || 0}）`, '当前']
              }
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={STATUS_COLOR[entry.status] || '#6366f1'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 销售域 KPI */}
      <div className="mb-6">
        <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-3">销售域 KPI</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {salesKpis.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} />
          ))}
        </div>
      </div>

      {/* 培训域 KPI */}
      <div>
        <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-3">培训域 KPI</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {trainingKpis.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} />
          ))}
        </div>
      </div>
    </div>
  )
}

function KpiCard({ kpi }: { kpi: KpiItem }) {
  const ratio = kpi.target > 0 ? kpi.value / kpi.target : 0
  const statusText: Record<string, string> = { success: '达标', warning: '警戒', danger: '危险' }
  return (
    <div className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-slate-500 dark:text-slate-400">{kpi.name}</span>
        <span
          className="text-xs px-2 py-0.5 rounded-full"
          style={{
            backgroundColor: `${STATUS_COLOR[kpi.status]}20`,
            color: STATUS_COLOR[kpi.status],
          }}
        >
          {statusText[kpi.status] || kpi.status}
        </span>
      </div>
      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{kpi.value}</span>
        <span className="text-sm text-slate-400">{kpi.unit}</span>
        <span className="text-xs text-slate-400 ml-auto">目标 {kpi.target}{kpi.unit}</span>
      </div>
      {/* 进度条 */}
      <div className="w-full h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: `${Math.min(100, ratio * 100)}%`,
            backgroundColor: STATUS_COLOR[kpi.status],
          }}
        />
      </div>
    </div>
  )
}
