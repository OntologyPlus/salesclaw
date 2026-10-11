/**
 * 学术活动三流看板：协议 / 签到 / 费用进度一览
 */
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarDays, FileText, UserCheck, Receipt, MessageSquarePlus, LayoutList } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import DataTable, { type Column } from '@/components/data/DataTable'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import ErrorState from '@/components/ui/ErrorState'
import Select from '@/components/ui/Select'
import { useFetch } from '@/hooks/useFetch'
import api from '@/services/api'

interface AcademicActivity extends Record<string, unknown> {
  id: number
  title: string
  activity_type: string
  status: string
  planned_at: string | null
  location: string | null
  meeting_protocol: Record<string, unknown> | null
  checkin_evidence: unknown[] | null
  expense_vouchers: unknown[] | null
  total_expense: number
  violation_count: number
  gates_passed: string[] | null
}

const statusVariant: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
  draft: 'default',
  pending_approval: 'warning',
  approved: 'success',
  ongoing: 'warning',
  completed: 'success',
  archived: 'success',
  cancelled: 'error',
}

const STATUS_OPTIONS = [
  { label: '全部', value: '' },
  { label: '草稿', value: 'draft' },
  { label: '待审批', value: 'pending_approval' },
  { label: '已审批', value: 'approved' },
  { label: '进行中', value: 'ongoing' },
  { label: '已归档', value: 'archived' },
  { label: '已取消', value: 'cancelled' },
]

function streamDot(label: string, ok: boolean) {
  const statusText = ok ? '已完成' : '未完成'
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs ${
        ok ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-500'
      }`}
      aria-label={`${label}${statusText}`}
      title={`${label} · ${statusText}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          ok ? 'bg-brand-500' : 'bg-slate-300 dark:bg-slate-600'
        }`}
        aria-hidden
      />
      {label}
      <span className="sr-only">{statusText}</span>
    </span>
  )
}

export default function AcademicBoardPage() {
  const [status, setStatus] = useState<string>('')
  const { data, loading, error, refetch } = useFetch<{ items: AcademicActivity[]; total: number }>(
    () =>
      api
        .get('/academic/activities', {
          params: { page: 1, page_size: 50, ...(status ? { status } : {}) },
        })
        .then((r) => r.data.data),
    [status],
  )

  const items = data?.items ?? []
  const summary = useMemo(() => {
    let protocol = 0
    let checkin = 0
    let expense = 0
    for (const a of items) {
      if (a.meeting_protocol && Object.keys(a.meeting_protocol).length) protocol += 1
      if ((a.checkin_evidence || []).length) checkin += 1
      if ((a.expense_vouchers || []).length) expense += 1
    }
    return { protocol, checkin, expense, total: items.length }
  }, [items])

  const columns: Column<AcademicActivity>[] = [
    {
      key: 'title',
      title: '活动',
      render: (a) => (
        <div>
          <div className="font-medium text-slate-900 dark:text-slate-100">{a.title}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            #{a.id} · {a.activity_type}
            {a.location ? ` · ${a.location}` : ''}
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      title: '状态',
      render: (a) => <Badge variant={statusVariant[a.status] || 'default'}>{a.status}</Badge>,
    },
    {
      key: 'planned_at',
      title: '计划时间',
      render: (a) => (
        <span className="inline-flex items-center gap-1 text-slate-600 dark:text-slate-300">
          <CalendarDays className="w-3.5 h-3.5 text-slate-400" />
          {a.planned_at || '—'}
        </span>
      ),
    },
    {
      key: 'streams',
      title: '三流',
      render: (a) => {
        const hasProtocol = !!(a.meeting_protocol && Object.keys(a.meeting_protocol).length)
        const hasCheckin = (a.checkin_evidence || []).length > 0
        const hasExpense = (a.expense_vouchers || []).length > 0
        return (
          <div className="flex flex-col gap-1">
            {streamDot('协议', hasProtocol)}
            {streamDot('签到', hasCheckin)}
            {streamDot('费用', hasExpense)}
          </div>
        )
      },
    },
    {
      key: 'total_expense',
      title: '费用',
      render: (a) => (
        <span className="text-slate-700 dark:text-slate-200">
          {a.total_expense ? `¥${(a.total_expense / 100).toFixed(2)}` : '—'}
        </span>
      ),
    },
    {
      key: 'violation_count',
      title: '违规',
      render: (a) =>
        a.violation_count > 0 ? (
          <Badge variant="error">{a.violation_count}</Badge>
        ) : (
          <span className="text-slate-400 dark:text-slate-500">0</span>
        ),
    },
    {
      key: 'actions',
      title: '操作',
      render: (a) => (
        <Link
          className="text-brand-600 dark:text-brand-400 hover:underline text-xs"
          to={`/compliance/audit-pack?activity_id=${a.id}`}
        >
          导出稽查包
        </Link>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="学术活动三流看板"
        description="协议流 · 签到流 · 费用流进度（对应《医药代表管理办法》第 21 条）"
        breadcrumbs={[{ label: '协同办公' }, { label: '学术三流看板' }]}
        icon={<CalendarDays className="w-5 h-5" />}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => refetch()}>
              刷新
            </Button>
            <Link to="/collab/academic-chat">
              <Button>
                <MessageSquarePlus className="w-4 h-4 mr-1" />
                对话式立项
              </Button>
            </Link>
          </div>
        }
      />

      {error && <ErrorState message={error.message} onRetry={refetch} className="mb-4" />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="活动数" value={summary.total} icon={<LayoutList className="w-5 h-5" />} color="brand" />
        <StatCard title="协议已挂" value={summary.protocol} icon={<FileText className="w-5 h-5" />} color="emerald" />
        <StatCard title="已有签到" value={summary.checkin} icon={<UserCheck className="w-5 h-5" />} color="amber" />
        <StatCard title="已有费用" value={summary.expense} icon={<Receipt className="w-5 h-5" />} color="rose" />
      </div>

      <DataTable
        columns={columns}
        data={items}
        loading={loading}
        total={data?.total ?? items.length}
        page={1}
        pageSize={50}
        emptyResource="学术活动"
        emptyDescription="暂无学术活动，可通过对话式工作流发起一场学术讲座或科室会"
        toolbar={
          <div className="flex items-center justify-between w-full gap-3">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">活动列表</span>
            <div className="w-40">
              <Select
                aria-label="状态筛选"
                options={STATUS_OPTIONS}
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              />
            </div>
          </div>
        }
      />

      {!loading && items.length === 0 && (
        <div className="flex justify-center mt-3">
          <Link to="/collab/academic-chat">
            <Button>去对话式立项</Button>
          </Link>
        </div>
      )}
    </div>
  )
}
