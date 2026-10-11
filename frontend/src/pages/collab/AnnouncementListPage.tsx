import { useState } from 'react'
import { Megaphone, Pin, Eye, Clock } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import { collabAPI } from '@/services/collab'
import type { PageRes } from '@/types/page'

interface AnnouncementItem {
  id: number
  title: string
  content?: string
  ann_type?: string
  publisher_id?: number
  published_at?: string
  is_pinned?: boolean
  view_count?: number
  created_at?: string
}


const ANN_TYPE_CONFIG: Record<string, { label: string; cls: string }> = {
  urgent: { label: '紧急', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
  warning: { label: '预警', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  info: { label: '通知', cls: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300' },
}

export default function AnnouncementListPage() {
  const [typeFilter, setTypeFilter] = useState('all')

  const { data, loading } = useFetch<PageRes<AnnouncementItem>>(
    () =>
      collabAPI.getAnnouncements({
        ann_type: typeFilter === 'all' ? undefined : typeFilter,
        page: 1,
        page_size: 50,
      }),
    [typeFilter]
  )

  const items = data?.items ?? []
  const total = data?.total ?? 0

  // 置顶优先
  const sorted = [...items].sort((a, b) => {
    if (!!a.is_pinned !== !!b.is_pinned) return a.is_pinned ? -1 : 1
    return 0
  })

  return (
    <div>
      <PageHeader
        title="公告栏"
        description="企业公告与通知"
        breadcrumbs={[{ label: '协同办公' }, { label: '公告栏' }]}
        icon={<Megaphone className="w-5 h-5" />}
      />

      {/* 筛选栏 */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-500 dark:text-slate-400">类型</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="all">全部</option>
            <option value="info">通知</option>
            <option value="warning">预警</option>
            <option value="urgent">紧急</option>
          </select>
        </div>
        <span className="text-sm text-slate-400">共 {total} 条</span>
      </div>

      {/* 公告列表 */}
      {loading ? (
        <div className="p-6 text-slate-500">加载中...</div>
      ) : sorted.length === 0 ? (
        <Empty description="暂无公告" />
      ) : (
        <div className="space-y-3">
          {sorted.map((ann) => {
            const cfg = ANN_TYPE_CONFIG[ann.ann_type ?? 'info'] || ANN_TYPE_CONFIG.info
            return (
              <div key={ann.id} className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                <div className="flex items-start gap-3">
                  {ann.is_pinned ? (
                    <Pin className="w-4 h-4 text-amber-500 mt-1 shrink-0" />
                  ) : null}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="font-medium text-slate-900 dark:text-slate-100">{ann.title}</h3>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
                        {cfg.label}
                      </span>
                    </div>
                    {ann.content && (
                      <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-2 mb-2">{ann.content}</p>
                    )}
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {ann.published_at ?? '-'}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Eye className="w-3.5 h-3.5" />
                        {ann.view_count ?? 0} 次浏览
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
  )
}
