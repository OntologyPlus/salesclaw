import {
  UsersRound, CalendarDays, Flame, MapPin, Users, Eye, MessageCircle, User,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import { useFetch } from '@/hooks/useFetch'
import { cfmAPI } from '@/services/cfm'
import AIInsightPanel from '@/components/ai/AIInsightPanel'

// 即将开始的会议
interface UpcomingMeeting {
  id: number | string
  title: string
  meeting_type: string
  status: string
  start_date: string
  location: string
  attendees_count: number
}

// 热门话题
interface HotTopic {
  id: number | string
  title: string
  category: string
  views: number
  replies_count: number
  author_name: string
}

// 总览数据
interface CfmOverview {
  meetings_count: number
  forums_count: number
  upcoming_meetings: UpcomingMeeting[]
  hot_topics: HotTopic[]
}

// 会议类型映射
const meetingTypeMap: Record<string, string> = {
  academic: '学术会议',
  department: '科室宣讲',
  salon: '沙龙',
  webinar: '线上会',
}

// 会议状态映射
const statusMap: Record<string, { label: string; variant: 'default' | 'success' | 'warning' | 'info' }> = {
  draft: { label: '草稿', variant: 'default' },
  upcoming: { label: '即将开始', variant: 'warning' },
  ongoing: { label: '进行中', variant: 'success' },
  ended: { label: '已结束', variant: 'default' },
  cancelled: { label: '已取消', variant: 'default' },
}

export default function CfmPage() {
  const { data, loading } = useFetch<CfmOverview>(() => cfmAPI.getOverview(), [])

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const meetings = data.upcoming_meetings ?? []
  const topics = data.hot_topics ?? []

  return (
    <div>
      <PageHeader
        title="会议论坛"
        description="学术会议、科室宣讲与交流社区"
        breadcrumbs={[{ label: '会议论坛' }]}
        icon={<UsersRound className="w-5 h-5" />}
        gradient
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <StatCard
          title="会议数"
          value={data.meetings_count}
          icon={<CalendarDays className="w-5 h-5" />}
          color="brand"
        />
        <StatCard
          title="话题数"
          value={data.forums_count}
          icon={<Flame className="w-5 h-5" />}
          color="cyan"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 即将开始的会议 */}
        <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">即将开始的会议</h2>
            <span className="text-xs text-slate-500 dark:text-slate-400">共 {meetings.length} 场</span>
          </div>
          {meetings.length === 0 ? (
            <Empty description="暂无即将开始的会议" />
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-700">
              {meetings.map((m) => {
                const st = statusMap[m.status] ?? { label: m.status || '-', variant: 'default' as const }
                return (
                  <div key={m.id} className="px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                            {m.title || '-'}
                          </span>
                          <Badge variant="info">{meetingTypeMap[m.meeting_type] ?? m.meeting_type}</Badge>
                          <Badge variant={st.variant}>{st.label}</Badge>
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                          <span className="flex items-center gap-1">
                            <CalendarDays className="w-3 h-3" />
                            {m.start_date || '-'}
                          </span>
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3 h-3" />
                            {m.location || '-'}
                          </span>
                          <span className="flex items-center gap-1">
                            <Users className="w-3 h-3" />
                            {m.attendees_count ?? 0} 人
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 热门话题 */}
        <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">热门话题</h2>
            <span className="text-xs text-slate-500 dark:text-slate-400">共 {topics.length} 条</span>
          </div>
          {topics.length === 0 ? (
            <Empty description="暂无热门话题" />
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-700">
              {topics.map((t) => (
                <div key={t.id} className="px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                          {t.title || '-'}
                        </span>
                        <Badge variant="warning">{t.category || '通用'}</Badge>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {t.author_name || '-'}
                        </span>
                        <span className="flex items-center gap-1">
                          <Eye className="w-3 h-3" />
                          {t.views ?? 0}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageCircle className="w-3 h-3" />
                          {t.replies_count ?? 0}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AIInsightPanel domain="cfm" title="AI 会议洞察" className="mt-6" />
    </div>
  )
}
