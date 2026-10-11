import { useState } from 'react'
import { FileCheck, Clock, CheckCircle, XCircle } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { collabAPI } from '@/services/collab'
import type { PageRes } from '@/types/page'

interface ApprovalItem {
  id: number
  title: string
  approval_type?: string
  status?: string
  applicant_id?: number
  approver_id?: number
  content?: string
  related_type?: string
  related_id?: number
  reviewed_at?: string
  review_comment?: string
  created_at?: string
}


const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  pending: { label: '待审批', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  approved: { label: '已通过', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
  rejected: { label: '已驳回', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
}

const TYPE_LABEL: Record<string, string> = {
  visit_plan: '拜访计划',
  expense: '费用报销',
  leave: '请假',
  sample: '样品申请',
}

export default function ApprovalListPage() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [actingId, setActingId] = useState<number | null>(null)

  const { data, loading, refetch } = useFetch<PageRes<ApprovalItem>>(
    () =>
      collabAPI.getApprovals({
        status: statusFilter === 'all' ? undefined : statusFilter,
        approval_type: typeFilter === 'all' ? undefined : typeFilter,
        page: 1,
        page_size: 50,
      }),
    [statusFilter, typeFilter]
  )

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const handleReview = async (id: number, decision: 'approve' | 'reject') => {
    const comment = window.prompt(decision === 'approve' ? '请输入审批意见（可留空）' : '请输入驳回原因（可留空）') ?? ''
    setActingId(id)
    try {
      await collabAPI.reviewApproval(id, decision, comment || undefined)
      toast(decision === 'approve' ? '已通过' : '已驳回', 'success')
      refetch()
    } catch (e) {
      toast(`操作失败：${(e as Error).message}`, 'error')
    } finally {
      setActingId(null)
    }
  }

  return (
    <div>
      <PageHeader
        title="审批中心"
        description="审批申请与处理"
        breadcrumbs={[{ label: '协同办公' }, { label: '审批中心' }]}
        icon={<FileCheck className="w-5 h-5" />}
        actions={<AIActionButton label="AI审批建议" prompt="分析待审批事项，给出审批建议" variant="ghost" size="sm" />}
      />

      {/* 筛选栏 */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-500 dark:text-slate-400">状态</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="all">全部</option>
            <option value="pending">待审批</option>
            <option value="approved">已通过</option>
            <option value="rejected">已驳回</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-500 dark:text-slate-400">类型</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="all">全部</option>
            <option value="visit_plan">拜访计划</option>
            <option value="expense">费用报销</option>
            <option value="leave">请假</option>
            <option value="sample">样品申请</option>
          </select>
        </div>
        <span className="text-sm text-slate-400">共 {total} 条</span>
      </div>

      {/* 审批列表 */}
      {loading ? (
        <div className="p-6 text-slate-500">加载中...</div>
      ) : items.length === 0 ? (
        <Empty description="暂无审批" />
      ) : (
        <div className="space-y-3">
          {items.map((ap) => {
            const stCfg = STATUS_CONFIG[ap.status ?? 'pending'] || STATUS_CONFIG.pending
            return (
              <div key={ap.id} className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-medium text-slate-900 dark:text-slate-100">{ap.title}</h3>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${stCfg.cls}`}>
                      {stCfg.label}
                    </span>
                    {ap.approval_type && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                        {TYPE_LABEL[ap.approval_type] || ap.approval_type}
                      </span>
                    )}
                  </div>
                  {ap.status === 'pending' && (
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => handleReview(ap.id, 'approve')}
                        disabled={actingId === ap.id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                        通过
                      </button>
                      <button
                        onClick={() => handleReview(ap.id, 'reject')}
                        disabled={actingId === ap.id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-rose-600 text-white text-xs font-medium hover:bg-rose-700 disabled:opacity-50 transition-colors"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        驳回
                      </button>
                    </div>
                  )}
                </div>
                {ap.content && (
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">{ap.content}</p>
                )}
                <div className="flex items-center gap-4 text-xs text-slate-400">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    申请于 {ap.created_at ?? '-'}
                  </span>
                  {ap.reviewed_at && <span>审批于 {ap.reviewed_at}</span>}
                </div>
                {ap.review_comment && (
                  <div className="mt-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-700/40 text-xs text-slate-600 dark:text-slate-300">
                    审批意见：{ap.review_comment}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
