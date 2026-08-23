import { AlertTriangle, AlertCircle, Info, Bell } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import Empty from '@/components/ui/Empty'
import StatCard from '@/components/data/StatCard'
import useFetch from '@/hooks/useFetch'
import { decisionAPI } from '@/services/decision'

const LEVEL_CONFIG: Record<string, { color: string; bg: string; icon: typeof AlertTriangle; label: string }> = {
  high: { color: 'text-rose-600 dark:text-rose-400', bg: 'bg-rose-50 dark:bg-rose-900/20 border-rose-200 dark:border-rose-800', icon: AlertTriangle, label: '高' },
  medium: { color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800', icon: AlertCircle, label: '中' },
  low: { color: 'text-sky-600 dark:text-sky-400', bg: 'bg-sky-50 dark:bg-sky-900/20 border-sky-200 dark:border-sky-800', icon: Info, label: '低' },
}

interface AlertItem {
  level: string
  category: string
  title: string
  description: string
  action: string
}

export default function AlertsPage() {
  const { data, loading } = useFetch(() => decisionAPI.getAlerts(), [])

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const alerts: AlertItem[] = data.items || []

  return (
    <div>
      <PageHeader
        title="预警中心"
        description="异常预警与行动建议"
        breadcrumbs={[{ label: '决策支持', path: '/decision' }, { label: '预警中心' }]}
        icon={<Bell className="w-5 h-5" />}
        actions={<AIActionButton label="AI预警分析" prompt="分析当前预警，给出处理优先级" variant="ghost" size="sm" />}
      />

      {/* 预警统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="总预警数" value={data.total || 0} icon={<Bell className="w-5 h-5" />} color="brand" />
        <StatCard title="高危预警" value={data.high_count || 0} icon={<AlertTriangle className="w-5 h-5" />} color="rose" />
        <StatCard title="中危预警" value={data.medium_count || 0} icon={<AlertCircle className="w-5 h-5" />} color="amber" />
        <StatCard title="低危预警" value={data.low_count || 0} icon={<Info className="w-5 h-5" />} color="cyan" />
      </div>

      {/* 预警列表 */}
      {alerts.length > 0 ? (
        <div className="space-y-3">
          {alerts.map((alert, i) => {
            const cfg = LEVEL_CONFIG[alert.level] || LEVEL_CONFIG.low
            const Icon = cfg.icon
            return (
              <div key={i} className={`p-4 rounded-xl border ${cfg.bg} flex items-start gap-3`}>
                <div className={`flex-shrink-0 ${cfg.color}`}>
                  <Icon className="w-5 h-5 mt-0.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${cfg.color} font-medium`}>
                      {cfg.label}
                    </span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">{alert.category}</span>
                    <h4 className="font-medium text-slate-900 dark:text-slate-100">{alert.title}</h4>
                  </div>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">{alert.description}</p>
                  {alert.action && (
                    <div className="flex items-center gap-1.5 text-xs text-brand-600 dark:text-brand-400">
                      <Info className="w-3 h-3" />
                      <span>建议：{alert.action}</span>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="p-12 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 mb-4">
            <Info className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">一切正常</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">当前无任何预警，继续保持良好的工作状态</p>
        </div>
      )}
    </div>
  )
}
