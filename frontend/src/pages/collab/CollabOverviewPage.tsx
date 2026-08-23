import { Link } from 'react-router-dom'
import { Users, CheckSquare, Clock, FileCheck, Megaphone, AlertTriangle, Pin } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import SectionCard from '@/components/layout/SectionCard'
import ListSection from '@/components/layout/ListSection'
import AIInsightBlock from '@/components/ai/AIInsightBlock'
import AIInsightPanel from '@/components/ai/AIInsightPanel'
import useFetch from '@/hooks/useFetch'
import { collabAPI } from '@/services/collab'

interface Announcement {
  id: number
  title: string
  ann_type?: string
  published_at?: string
  is_pinned?: boolean
}

const ANN_TYPE_CONFIG: Record<string, { label: string; cls: string }> = {
  urgent: { label: '紧急', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
  warning: { label: '预警', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  info: { label: '通知', cls: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300' },
}

export default function CollabOverviewPage() {
  const { data, loading } = useFetch(() => collabAPI.getOverview(), [])

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <div className="p-6 text-slate-500">暂无数据</div>

  const recentAnnouncements: Announcement[] = data.recent_announcements || []
  const overdue = data.overdue_tasks ?? 0

  return (
    <div>
      <PageHeader
        title="协同办公"
        description="任务管理、审批流与公告"
        breadcrumbs={[{ label: '协同与知识' }, { label: '协同总览' }]}
        icon={<Users className="w-5 h-5" />}
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <StatCard title="总任务" value={data.total_tasks ?? 0} icon={<CheckSquare className="w-5 h-5" />} color="brand" />
        <StatCard title="待处理" value={data.pending_tasks ?? 0} icon={<Clock className="w-5 h-5" />} color="blue" />
        <StatCard title="已逾期" value={overdue} icon={<AlertTriangle className="w-5 h-5" />} color={overdue > 0 ? 'rose' : 'amber'} />
        <StatCard title="待审批" value={data.pending_approvals ?? 0} icon={<FileCheck className="w-5 h-5" />} color="violet" />
        <StatCard title="公告数" value={data.announcements_count ?? 0} icon={<Megaphone className="w-5 h-5" />} color="cyan" />
      </div>

      {/* 快捷入口 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Link to="/collab/tasks" className="p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400">
              <CheckSquare className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">任务管理</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">创建、跟踪与完成任务</p>
        </Link>

        <Link to="/collab/approvals" className="p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-100 text-violet-600 dark:bg-violet-900/20 dark:text-violet-400">
              <FileCheck className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">审批中心</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">审批申请与处理</p>
        </Link>

        <Link to="/collab/announcements" className="p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-100 text-cyan-600 dark:bg-cyan-900/40 dark:text-cyan-300">
              <Megaphone className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">公告栏</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">企业公告与通知</p>
        </Link>
      </div>

      <SectionCard title="最近公告" icon={<Megaphone className="w-4 h-4" />} viewAllTo="/collab/announcements">
        <ListSection<Announcement>
          items={recentAnnouncements}
          emptyText="暂无公告"
          skeletonRows={3}
          renderRow={(ann) => {
            const cfg = ANN_TYPE_CONFIG[ann.ann_type ?? 'info'] || ANN_TYPE_CONFIG.info
            return (
              <div className="flex items-center gap-3">
                {ann.is_pinned && <Pin className="w-4 h-4 text-amber-500 shrink-0" />}
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
                  {cfg.label}
                </span>
                <span className="flex-1 truncate text-sm text-slate-900 dark:text-slate-100">{ann.title}</span>
                <span className="text-xs text-slate-400 shrink-0">{ann.published_at ?? '-'}</span>
              </div>
            )
          }}
        />
      </SectionCard>

      <div className="mt-6">
        <AIInsightBlock title="AI 协同洞察">
          <AIInsightPanel domain="collab" />
        </AIInsightBlock>
      </div>
    </div>
  )
}
