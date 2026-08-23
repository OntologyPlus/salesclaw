import { HeartHandshake, Users, MessageSquare, Calendar, Building2 } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import { useFetch } from '@/hooks/useFetch'
import { crmAPI } from '@/services/crm'
import AIInsightPanel from '@/components/ai/AIInsightPanel'

// 互动记录
interface RecentInteraction {
  id: number | string
  doctor_name: string
  hospital_name: string
  visit_date: string
  summary: string
  visit_type: string
}

// 总览数据
interface CrmOverview {
  kols_count: number
  customers_count: number
  interactions_count: number
  recent_interactions: RecentInteraction[]
}

// 拜访类型映射
const visitTypeMap: Record<string, { label: string; variant: 'default' | 'success' | 'warning' | 'info' }> = {
  academic: { label: '学术拜访', variant: 'info' },
  daily: { label: '日常拜访', variant: 'default' },
  meeting: { label: '会议', variant: 'success' },
  online: { label: '线上', variant: 'warning' },
}

export default function CrmPage() {
  const { data, loading } = useFetch<CrmOverview>(() => crmAPI.getOverview(), [])

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const interactions = data.recent_interactions ?? []

  return (
    <div>
      <PageHeader
        title="客户关系"
        description="KOL管理、客户画像与互动记录"
        breadcrumbs={[{ label: '客户关系' }]}
        icon={<HeartHandshake className="w-5 h-5" />}
        gradient
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <StatCard
          title="KOL"
          value={data.kols_count}
          icon={<HeartHandshake className="w-5 h-5" />}
          color="violet"
        />
        <StatCard
          title="客户数"
          value={data.customers_count}
          icon={<Users className="w-5 h-5" />}
          color="blue"
        />
        <StatCard
          title="互动次数"
          value={data.interactions_count}
          icon={<MessageSquare className="w-5 h-5" />}
          color="cyan"
        />
      </div>

      {/* 最近互动记录 */}
      <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">最近互动记录</h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">共 {interactions.length} 条</span>
        </div>
        {interactions.length === 0 ? (
          <Empty description="暂无互动记录" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-5">
            {interactions.map((item) => {
              const vt = visitTypeMap[item.visit_type] ?? { label: item.visit_type || '拜访', variant: 'default' as const }
              return (
                <div
                  key={item.id}
                  className="p-4 rounded-xl bg-slate-50 dark:bg-slate-700/40 border border-slate-200 dark:border-slate-700"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
                          {item.doctor_name || '-'}
                        </span>
                        <Badge variant={vt.variant}>{vt.label}</Badge>
                      </div>
                      <div className="mt-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                        <Building2 className="w-3 h-3" />
                        <span className="truncate">{item.hospital_name || '-'}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-slate-400 shrink-0">
                      <Calendar className="w-3 h-3" />
                      {item.visit_date || '-'}
                    </div>
                  </div>
                  {item.summary && (
                    <p className="mt-3 text-sm text-slate-600 dark:text-slate-300 line-clamp-2">
                      {item.summary}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <AIInsightPanel domain="crm" title="AI 客户洞察" className="mt-6" />
    </div>
  )
}
