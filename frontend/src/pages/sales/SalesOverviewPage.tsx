import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart3, CalendarCheck, FileText, Users, TrendingUp, Award, Map, Grid3x3, AlertCircle,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Badge from '@/components/ui/Badge'
import PageGrid from '@/components/layout/PageGrid'
import SectionCard from '@/components/layout/SectionCard'
import ListSection from '@/components/layout/ListSection'
import AIInsightBlock from '@/components/ai/AIInsightBlock'
import { useFetch } from '@/hooks/useFetch'
import { salesAPI } from '@/services/sales'
import api from '@/services/api'
import type { PageRes, StatusMap, AiInsightPayload } from '@/types/page'

interface SalesOverview {
  month_visits?: number
  visit_records?: number
  active_customers?: number
  coverage_rate?: number | string
  score_rank?: string
  matrix_score?: string
  roi?: number | string
  active_plans?: number
}

interface PlanItem extends Record<string, unknown> {
  id: number | string
  period?: string
  status?: string
  target_count?: number
  ai_score?: number
  created_at?: string
}

interface RecordItem extends Record<string, unknown> {
  id: number | string
  visit_date?: string
  hospital?: string | { name?: string }
  doctor?: string | { name?: string }
  product?: string | { name?: string }
  visit_type?: string
}

const statusMap: StatusMap = {
  draft: { label: '草稿', variant: 'default' },
  pending: { label: '待审批', variant: 'warning' },
  approved: { label: '已批准', variant: 'success' },
  rejected: { label: '已驳回', variant: 'error' },
}

const visitTypeMap: Record<string, string> = {
  academic: '学术拜访',
  daily: '日常拜访',
  meeting: '会议',
}

function hospitalName(v: unknown): string {
  if (typeof v === 'string') return v
  if (v && typeof v === 'object' && 'name' in v) return String((v as { name?: string }).name ?? '-')
  return '-'
}

export default function SalesOverviewPage() {
  const [aiInsights, setAiInsights] = useState<AiInsightPayload | null>(null)
  const [insightLoading, setInsightLoading] = useState(true)

  useEffect(() => {
    api.post<{ data?: AiInsightPayload }>('/sales/ai-insights')
      .then((res) => setAiInsights(res.data?.data ?? null))
      .catch(() => setAiInsights(null))
      .finally(() => setInsightLoading(false))
  }, [])

  const { data: overview, loading: ovLoading, error: ovError } = useFetch<SalesOverview>(
    () => salesAPI.getOverview(),
    []
  )
  const { data: plansRes, loading: plansLoading } = useFetch<PageRes<PlanItem>>(
    () => salesAPI.listPlans({ status: 'approved', page: 1, page_size: 3 }),
    []
  )
  const { data: recordsRes, loading: recordsLoading } = useFetch<PageRes<RecordItem>>(
    () => salesAPI.listRecords({ page: 1, page_size: 5 }),
    []
  )

  const plans = plansRes?.items ?? []
  const records = recordsRes?.items ?? []

  const stats = [
    { title: '本月拜访', value: overview?.month_visits ?? '-', icon: <CalendarCheck className="w-5 h-5" />, color: 'brand' as const, trend: 12 },
    { title: '拜访记录', value: overview?.visit_records ?? '-', icon: <FileText className="w-5 h-5" />, color: 'blue' as const, trend: 8 },
    { title: '活跃客户', value: overview?.active_customers ?? '-', icon: <Users className="w-5 h-5" />, color: 'emerald' as const, trend: 5 },
    { title: '覆盖率', value: overview?.coverage_rate ?? '-', icon: <Map className="w-5 h-5" />, color: 'cyan' as const, trend: 3 },
    { title: '积分排名', value: overview?.score_rank ?? '-', icon: <Award className="w-5 h-5" />, color: 'amber' as const, trend: -2 },
    { title: '矩阵评分', value: overview?.matrix_score ?? '-', icon: <Grid3x3 className="w-5 h-5" />, color: 'pink' as const, trend: 0 },
    { title: 'ROI', value: overview?.roi ?? '-', icon: <TrendingUp className="w-5 h-5" />, color: 'rose' as const, trend: 15 },
    { title: '进行中计划', value: overview?.active_plans ?? '-', icon: <CalendarCheck className="w-5 h-5" />, color: 'brand' as const, trend: 6 },
  ]

  return (
    <div>
      <PageHeader
        title="销售总览"
        description="销售执行全域数据概览与关键指标"
        breadcrumbs={[{ label: '拜访执行' }, { label: '销售总览' }]}
        icon={<BarChart3 className="w-5 h-5" />}
      />

      <PageGrid loading={ovLoading} skeletonCount={8}>
        {stats.map((stat) => (
          <StatCard key={stat.title} {...stat} />
        ))}
      </PageGrid>

      {ovError && (
        <div className="mt-6 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载概览数据失败：{ovError.message}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <SectionCard title="进行中的拜访计划" icon={<CalendarCheck className="w-4 h-4" />} viewAllTo="/sales/plans">
          <ListSection
            items={plans}
            loading={plansLoading}
            emptyText="暂无进行中的计划"
            skeletonRows={3}
            renderRow={(plan) => {
              const st = statusMap[plan.status ?? 'approved'] ?? statusMap.approved
              return (
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                        {plan.period ?? '-'}
                      </span>
                      <Badge variant={st.variant}>{st.label}</Badge>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      目标 {plan.target_count ?? 0} 次 · 创建于 {plan.created_at ?? '-'}
                    </p>
                  </div>
                  {typeof plan.ai_score === 'number' && (
                    <div className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 shrink-0">
                      <Award className="w-3.5 h-3.5" />
                      AI {plan.ai_score}
                    </div>
                  )}
                </div>
              )
            }}
          />
        </SectionCard>

        <SectionCard title="最近拜访记录" icon={<FileText className="w-4 h-4" />} viewAllTo="/sales/records">
          <ListSection
            items={records}
            loading={recordsLoading}
            emptyText="暂无拜访记录"
            skeletonRows={5}
            renderRow={(rec) => (
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      {hospitalName(rec.hospital)}
                    </span>
                    {rec.visit_type && (
                      <Badge variant="info">{visitTypeMap[rec.visit_type] ?? rec.visit_type}</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 truncate">
                    {hospitalName(rec.doctor)} · {hospitalName(rec.product)}
                  </p>
                </div>
                <span className="text-xs text-slate-400 shrink-0">{rec.visit_date ?? '-'}</span>
              </div>
            )}
          />
        </SectionCard>
      </div>

      <div className="mt-6">
        <AIInsightBlock payload={aiInsights ?? undefined} loading={insightLoading} title="AI 销售洞察" />
      </div>
    </div>
  )
}
