import {
  Activity, Users, UserCheck, FileText, BookOpen, Cpu, Database, Clock, Zap, AlertTriangle,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import { useFetch } from '@/hooks/useFetch'
import { observabilityAPI, type EventStat, type AIEventItem, type DeadLetterItem } from '@/services/observability'
import AIInsightPanel from '@/components/ai/AIInsightPanel'

// 域分布
interface DomainDist {
  domain: string
  count: number
}

// 指标数据
interface Metrics {
  uptime_seconds: number
  total_users: number
  active_users: number
  total_visits: number
  total_courses: number
  llm_calls: number
  llm_success_rate: number
  db_table_count: number
  domain_distribution: DomainDist[]
}

// 格式化运行时间为 Xh Ym
function formatUptime(seconds: number): string {
  if (!seconds || seconds < 0) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

// 域名映射
const domainMap: Record<string, string> = {
  sales: '销售',
  training: '培训',
  knowledge: '知识库',
  crm: '客户关系',
  cfm: '会议论坛',
  collab: '协同',
  decision: '决策',
  platform: '平台',
  mdm: '主数据',
}

export default function ObservabilityPage() {
  const { data, loading } = useFetch<Metrics>(() => observabilityAPI.getMetrics(), [])
  const { data: eventStatsData } = useFetch<{ items: EventStat[] }>(
    () => observabilityAPI.getEventStats(), []
  )
  const { data: eventsData } = useFetch<AIEventItem[]>(
    () => observabilityAPI.getEvents({ limit: 20 }), []
  )
  const { data: deadLettersData } = useFetch<DeadLetterItem[]>(
    () => observabilityAPI.getDeadLetters(20), []
  )

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const eventStats = eventStatsData?.items ?? []

  const domains = data.domain_distribution ?? []
  const maxDomainCount = domains.reduce((m, d) => Math.max(m, d.count || 0), 0) || 1
  // 后端已返回百分比数值（如 100.0 表示 100%），直接 toFixed 即可
  const successRate = typeof data.llm_success_rate === 'number'
    ? data.llm_success_rate.toFixed(1)
    : '0.0'

  return (
    <div>
      <PageHeader
        title="可观测"
        description="系统监控与运行指标"
        breadcrumbs={[{ label: '可观测' }]}
        icon={<Activity className="w-5 h-5" />}
        gradient
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="用户数"
          value={data.total_users}
          icon={<Users className="w-5 h-5" />}
          color="brand"
        />
        <StatCard
          title="活跃用户"
          value={data.active_users}
          icon={<UserCheck className="w-5 h-5" />}
          color="emerald"
        />
        <StatCard
          title="拜访记录"
          value={data.total_visits}
          icon={<FileText className="w-5 h-5" />}
          color="blue"
        />
        <StatCard
          title="课程数"
          value={data.total_courses}
          icon={<BookOpen className="w-5 h-5" />}
          color="violet"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LLM 统计 */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-violet-100 text-violet-600 dark:bg-violet-900/20 dark:text-violet-400">
              <Cpu className="w-4 h-4" />
            </div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">LLM 调用</h2>
          </div>
          <dl className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-slate-500 dark:text-slate-400">调用次数</dt>
              <dd className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                {data.llm_calls ?? 0}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-slate-500 dark:text-slate-400">成功率</dt>
              <dd className="text-lg font-semibold text-emerald-600 dark:text-emerald-400">
                {successRate}%
              </dd>
            </div>
          </dl>
          <div className="mt-3 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all"
              style={{ width: `${successRate}%` }}
            />
          </div>
        </div>

        {/* 域分布 */}
        <div className="lg:col-span-2 p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-4">域分布</h2>
          {domains.length === 0 ? (
            <Empty description="暂无域分布数据" />
          ) : (
            <div className="space-y-2.5">
              {domains.map((d, i) => (
                <div key={`${d.domain}-${i}`} className="flex items-center gap-3">
                  <span className="w-20 shrink-0 text-xs text-slate-600 dark:text-slate-300 truncate">
                    {domainMap[d.domain] ?? d.domain}
                  </span>
                  <div className="flex-1 h-5 bg-slate-100 dark:bg-slate-700 rounded-md overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-brand-500 to-violet-500 rounded-md transition-all"
                      style={{ width: `${(d.count / maxDomainCount) * 100}%` }}
                    />
                  </div>
                  <span className="w-12 text-right text-xs text-slate-600 dark:text-slate-300 shrink-0">
                    {d.count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 系统信息 */}
      <div className="mt-6 p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-4">系统信息</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-cyan-100 text-cyan-600 dark:bg-cyan-900/20 dark:text-cyan-400">
              <Database className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-slate-500 dark:text-slate-400">数据库表数</p>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                {data.db_table_count ?? 0}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-emerald-100 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400">
              <Clock className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-slate-500 dark:text-slate-400">运行时长</p>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                {formatUptime(data.uptime_seconds)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* AI 事件总线 */}
      <div className="mt-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">AI 事件总线</h2>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            共 {eventStats.length} 种事件类型
          </span>
        </div>
        {eventStats.length === 0 ? (
          <div className="px-5 py-6">
            <Empty description="暂无事件数据" />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-5">
            {eventStats.map((evt) => {
              const hasDead = evt.dead_letter_count > 0
              const hasFailed = evt.failed > 0
              return (
                <div
                  key={evt.type}
                  className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-700/40"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500 dark:text-slate-400 truncate" title={evt.type}>
                      {evt.desc}
                    </span>
                    <span className="text-lg font-bold text-slate-900 dark:text-slate-100">
                      {evt.total}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {evt.completed > 0 && (
                      <Badge variant="success">完成 {evt.completed}</Badge>
                    )}
                    {evt.pending > 0 && (
                      <Badge variant="info">待处理 {evt.pending}</Badge>
                    )}
                    {hasFailed && (
                      <Badge variant="warning">失败 {evt.failed}</Badge>
                    )}
                    {hasDead && (
                      <Badge variant="error">死信 {evt.dead_letter_count}</Badge>
                    )}
                    {evt.total === 0 && (
                      <span className="text-xs text-slate-400">无记录</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* AI 事件流 */}
      <div className="mt-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">AI 事件流</h2>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            最近 {(eventsData ?? []).length} 条
          </span>
        </div>
        {(eventsData ?? []).length === 0 ? (
          <div className="px-5 py-6">
            <Empty description="暂无事件流数据" />
          </div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {(eventsData ?? []).slice(0, 20).map((evt) => (
              <div key={evt.event_id} className="flex items-center justify-between px-5 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                    {evt.event_type_desc || evt.event_type}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                    {evt.affected_domains?.length ? `域：${evt.affected_domains.join(' / ')}` : evt.event_type}
                    {evt.published_at ? ` · ${evt.published_at.replace('T', ' ').slice(0, 19)}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-3">
                  {evt.retry_count ? (
                    <span className="text-xs text-slate-400">重试 {evt.retry_count}</span>
                  ) : null}
                  {evt.status === 'completed' && <Badge variant="success">完成</Badge>}
                  {evt.status === 'pending' && <Badge variant="info">待处理</Badge>}
                  {evt.status === 'failed' && <Badge variant="warning">失败</Badge>}
                  {evt.status === 'dead_letter' && <Badge variant="error">死信</Badge>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 死信队列 */}
      <div className="mt-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-500" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">死信队列</h2>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {(deadLettersData ?? []).length} 条待处理
          </span>
        </div>
        {(deadLettersData ?? []).length === 0 ? (
          <div className="px-5 py-6">
            <Empty description="无死信，事件处理正常" />
          </div>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {(deadLettersData ?? []).map((dl) => (
              <div key={dl.dead_letter_id} className="px-5 py-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                    {dl.event_type_desc || dl.event_type}
                  </p>
                  <span className="text-xs text-slate-400 shrink-0 ml-3">
                    {dl.failed_at ? dl.failed_at.replace('T', ' ').slice(0, 19) : ''}
                  </span>
                </div>
                {dl.error_message && (
                  <p className="mt-1 text-xs text-rose-500 dark:text-rose-400 break-all">
                    {dl.error_message}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <AIInsightPanel domain="observability" title="AI 可观测洞察" className="mt-6" />
    </div>
  )
}
