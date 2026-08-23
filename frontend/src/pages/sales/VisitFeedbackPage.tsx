import { useState } from 'react'
import { MessageSquare, Eye, AlertCircle } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import DataTable, { type Column } from '@/components/data/DataTable'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import { useFetch } from '@/hooks/useFetch'
import { salesAPI } from '@/services/sales'

// 反馈行
interface Feedback extends Record<string, unknown> {
  id: number | string
  record_id?: number | string
  record?: { id?: number | string; hospital?: string; doctor?: string; visit_date?: string } | string
  sentiment?: string
  interest_points?: string[]
  objections?: string[]
  action_items?: string[]
  summary?: string
  created_at?: string
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 情感映射
const sentimentMap: Record<string, { label: string; variant: 'success' | 'default' | 'error' }> = {
  positive: { label: '积极', variant: 'success' },
  neutral: { label: '中性', variant: 'default' },
  negative: { label: '消极', variant: 'error' },
}

// 取关联记录名称
function recordTitle(rec: unknown): string {
  if (typeof rec === 'string') return rec
  if (rec && typeof rec === 'object') {
    const r = rec as { hospital?: string; doctor?: string; visit_date?: string; id?: string | number }
    if (r.hospital) return r.hospital
    if (r.doctor) return r.doctor
    if (r.visit_date) return r.visit_date
    return r.id ? `记录 #${r.id}` : '-'
  }
  return '-'
}

// 标签数组渲染
function TagList({ tags }: { tags?: string[] }) {
  if (!tags || tags.length === 0) return <span className="text-slate-400 text-xs">-</span>
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((t, i) => (
        <span key={i} className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300">
          {t}
        </span>
      ))}
    </div>
  )
}

export default function VisitFeedbackPage() {
  const [page, setPage] = useState(1)
  const pageSize = 10
  const [detailOpen, setDetailOpen] = useState(false)
  const [detail, setDetail] = useState<Feedback | null>(null)

  // 列表数据
  const { data, loading, error } = useFetch<PageRes<Feedback>>(
    () => salesAPI.listFeedbacks({ page, page_size: pageSize }),
    [page]
  )

  const items = data?.items ?? []
  const total = data?.total ?? 0

  // 查看详情
  const handleView = (fb: Feedback) => {
    setDetail(fb)
    setDetailOpen(true)
  }

  const columns: Column<Feedback>[] = [
    {
      key: 'record', title: '关联记录',
      render: (r) => <span className="font-medium text-slate-900 dark:text-slate-100">{recordTitle(r.record)}</span>,
    },
    {
      key: 'sentiment', title: '情感',
      render: (r) => {
        const st = sentimentMap[r.sentiment ?? 'neutral'] ?? sentimentMap.neutral
        return <Badge variant={st.variant}>{st.label}</Badge>
      },
    },
    {
      key: 'interest_points', title: '兴趣点',
      render: (r) => <TagList tags={r.interest_points} />,
    },
    {
      key: 'objections', title: '异议点',
      render: (r) => <TagList tags={r.objections} />,
    },
    {
      key: 'action_items', title: '行动项',
      render: (r) => <TagList tags={r.action_items} />,
    },
    {
      key: 'actions', title: '操作', width: '80px',
      render: (r) => (
        <button onClick={() => handleView(r)} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-700 transition-colors" title="查看详情">
          <Eye className="w-4 h-4" />
        </button>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="拜访反馈"
        description="拜访结果反馈、客户意见与跟进记录"
        breadcrumbs={[{ label: '销售执行' }, { label: '拜访反馈' }]}
        icon={<MessageSquare className="w-5 h-5" />}
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <DataTable<Feedback>
        columns={columns}
        data={items}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
      />

      {/* 详情 Modal */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title="反馈详情"
        size="lg"
        footer={<Button variant="secondary" onClick={() => setDetailOpen(false)}>关闭</Button>}
      >
        {detail && (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-slate-400">关联记录</p>
              <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{recordTitle(detail.record)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">情感倾向</p>
              {(() => {
                const st = sentimentMap[detail.sentiment ?? 'neutral'] ?? sentimentMap.neutral
                return <Badge variant={st.variant}>{st.label}</Badge>
              })()}
            </div>
            {detail.summary && (
              <div>
                <p className="text-xs text-slate-400">摘要</p>
                <p className="text-sm text-slate-700 dark:text-slate-200">{detail.summary}</p>
              </div>
            )}
            <div>
              <p className="text-xs text-slate-400 mb-1">兴趣点</p>
              <TagList tags={detail.interest_points} />
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">异议点</p>
              <TagList tags={detail.objections} />
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">行动项</p>
              <TagList tags={detail.action_items} />
            </div>
            {detail.created_at && (
              <div>
                <p className="text-xs text-slate-400">反馈时间</p>
                <p className="text-sm text-slate-500">{detail.created_at}</p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
