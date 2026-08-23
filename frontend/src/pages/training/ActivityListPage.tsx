import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Trophy, Plus, Send, Square, Archive, BarChart3, Pencil, AlertCircle, RefreshCw,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import FormField from '@/components/forms/FormField'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { activityAPI } from '@/services/activity'

// 培训活动
interface TrainingActivity extends Record<string, unknown> {
  id: number
  title?: string
  description?: string
  status?: string
  domain?: string
  period_start?: string
  period_end?: string
  scenario_count?: number
  pass_score?: number
  published_at?: string
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 活动状态映射
const statusMap: Record<string, { label: string; variant: 'default' | 'info' | 'warning' | 'error' }> = {
  draft: { label: '草稿', variant: 'default' },
  ongoing: { label: '进行中', variant: 'info' },
  ended: { label: '已结束', variant: 'warning' },
  off_shelf: { label: '已下架', variant: 'error' },
}

const statusFilterOptions = [
  { label: '全部状态', value: 'all' },
  { label: '草稿', value: 'draft' },
  { label: '进行中', value: 'ongoing' },
  { label: '已结束', value: 'ended' },
  { label: '已下架', value: 'off_shelf' },
]

const domainOptions = [
  { label: '通用', value: 'general' },
  { label: '产品', value: 'product' },
  { label: '技能', value: 'skill' },
]

export default function ActivityListPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [status, setStatus] = useState('all')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 10

  const { data, loading, error, refetch } = useFetch<PageRes<TrainingActivity>>(
    () => activityAPI.list({
      status: status === 'all' ? undefined : status,
      keyword: keyword || undefined,
      page,
      page_size: pageSize,
    }),
    [status, keyword, page]
  )

  const activities = data?.items ?? []
  const total = data?.total ?? 0

  // 创建/编辑
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<TrainingActivity | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    title: '',
    description: '',
    domain: 'general',
    period_start: '',
    period_end: '',
    pass_score: 60,
  })

  // 状态流转
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  const openCreate = () => {
    setEditing(null)
    setForm({ title: '', description: '', domain: 'general', period_start: '', period_end: '', pass_score: 60 })
    setModalOpen(true)
  }

  const openEdit = (a: TrainingActivity) => {
    setEditing(a)
    setForm({
      title: a.title ?? '',
      description: a.description ?? '',
      domain: a.domain ?? 'general',
      period_start: a.period_start?.slice(0, 10) ?? '',
      period_end: a.period_end?.slice(0, 10) ?? '',
      pass_score: a.pass_score ?? 60,
    })
    setModalOpen(true)
  }

  const handleSave = async () => {
    if (!form.title) {
      toast('请填写活动标题', 'warning')
      return
    }
    setSaving(true)
    try {
      const payload = {
        title: form.title,
        description: form.description,
        domain: form.domain,
        period_start: form.period_start || null,
        period_end: form.period_end || null,
        pass_score: Number(form.pass_score) || 60,
      }
      if (editing) {
        await activityAPI.update(editing.id, payload)
        toast('更新成功', 'success')
      } else {
        await activityAPI.create(payload)
        toast('创建成功', 'success')
      }
      setModalOpen(false)
      refetch()
    } catch (e) {
      toast(`保存失败：${(e as Error).message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleStateChange = async (a: TrainingActivity, action: 'publish' | 'end' | 'offShelf') => {
    const confirmText = {
      publish: '确认发布该活动？发布后将进入「进行中」状态。',
      end: '确认结束该活动？结束后将无法编辑。',
      offShelf: '确认下架该活动？',
    }[action]
    if (!confirm(confirmText)) return
    setActionLoading(a.id)
    try {
      await activityAPI[action](a.id)
      toast('操作成功', 'success')
      refetch()
    } catch (e) {
      toast(`操作失败：${(e as Error).message}`, 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const columns: Column<TrainingActivity>[] = [
    {
      key: 'title', title: '活动标题',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-medium text-slate-900 dark:text-slate-100">{row.title ?? '-'}</span>
          {row.description && (
            <span className="text-xs text-slate-400 line-clamp-1">{row.description}</span>
          )}
        </div>
      ),
    },
    {
      key: 'status', title: '状态',
      render: (row) => {
        const s = statusMap[row.status ?? 'draft'] ?? statusMap.draft
        return <Badge variant={s.variant}>{s.label}</Badge>
      },
    },
    {
      key: 'period', title: '时间范围',
      render: (row) => (
        <span className="text-slate-600 dark:text-slate-300">
          {row.period_start ?? '-'} ~ {row.period_end ?? '-'}
        </span>
      ),
    },
    {
      key: 'scenario_count', title: '场景数',
      render: (row) => (
        <span className="inline-flex items-center gap-1 text-slate-500">
          <BarChart3 className="w-3.5 h-3.5" /> {row.scenario_count ?? 0}
        </span>
      ),
    },
    {
      key: 'pass_score', title: '达标分',
      render: (row) => <span className="text-slate-500">{row.pass_score ?? 60}</span>,
    },
    {
      key: 'actions', title: '操作', width: '200px',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => navigate(`/training/activities/${row.id}/data`)}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-700 transition-colors"
            title="查看数据看板"
          >
            <BarChart3 className="w-4 h-4" />
          </button>
          {row.status === 'draft' && (
            <button
              onClick={() => handleStateChange(row, 'publish')}
              disabled={actionLoading === row.id}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-emerald-600 dark:hover:bg-slate-700 transition-colors disabled:opacity-40"
              title="发布"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
          {row.status === 'ongoing' && (
            <button
              onClick={() => handleStateChange(row, 'end')}
              disabled={actionLoading === row.id}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-amber-600 dark:hover:bg-slate-700 transition-colors disabled:opacity-40"
              title="结束"
            >
              <Square className="w-4 h-4" />
            </button>
          )}
          {row.status === 'ended' && (
            <button
              onClick={() => handleStateChange(row, 'offShelf')}
              disabled={actionLoading === row.id}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-rose-600 dark:hover:bg-slate-700 transition-colors disabled:opacity-40"
              title="下架"
            >
              <Archive className="w-4 h-4" />
            </button>
          )}
          {row.status === 'draft' && (
            <button
              onClick={() => openEdit(row)}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-sky-600 dark:hover:bg-slate-700 transition-colors"
              title="编辑"
            >
              <Pencil className="w-4 h-4" />
            </button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="培训活动"
        description="培训活动编排、发布与生命周期管理"
        breadcrumbs={[{ label: '智能培训' }, { label: '培训活动' }]}
        icon={<Trophy className="w-5 h-5" />}
        actions={
          <Button onClick={openCreate}>
            <Plus className="w-4 h-4" />
            创建活动
          </Button>
        }
      />

      <div className="mb-4 flex items-center gap-3 flex-wrap">
        <div className="w-40">
          <Select
            options={statusFilterOptions}
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1) }}
          />
        </div>
        <div className="flex-1 min-w-[200px]">
          <Input
            placeholder="搜索活动标题"
            value={keyword}
            onChange={(e) => { setKeyword(e.target.value); setPage(1) }}
          />
        </div>
        <Button variant="secondary" onClick={refetch}>
          <RefreshCw className="w-4 h-4" />
          刷新
        </Button>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <DataTable<TrainingActivity>
        columns={columns}
        data={activities}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
      />

      {/* 创建/编辑 Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? '编辑培训活动' : '创建培训活动'}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>取消</Button>
            <Button loading={saving} onClick={handleSave}>{editing ? '保存' : '创建'}</Button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <FormField label="活动标题" required>
              <Input placeholder="请输入活动标题" value={form.title} onChange={(e) => setForm(p => ({ ...p, title: e.target.value }))} />
            </FormField>
          </div>
          <div className="sm:col-span-2">
            <FormField label="活动描述">
              <textarea
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100 min-h-[80px]"
                placeholder="请输入活动描述"
                value={form.description}
                onChange={(e) => setForm(p => ({ ...p, description: e.target.value }))}
              />
            </FormField>
          </div>
          <FormField label="领域">
            <Select options={domainOptions} value={form.domain} onChange={(e) => setForm(p => ({ ...p, domain: e.target.value }))} />
          </FormField>
          <FormField label="达标分" required>
            <Input type="number" min={0} max={100} value={form.pass_score} onChange={(e) => setForm(p => ({ ...p, pass_score: Number(e.target.value) || 0 }))} />
          </FormField>
          <FormField label="开始时间">
            <Input type="date" value={form.period_start} onChange={(e) => setForm(p => ({ ...p, period_start: e.target.value }))} />
          </FormField>
          <FormField label="结束时间">
            <Input type="date" value={form.period_end} onChange={(e) => setForm(p => ({ ...p, period_end: e.target.value }))} />
          </FormField>
        </div>
      </Modal>
    </div>
  )
}
