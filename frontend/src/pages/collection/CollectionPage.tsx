import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Database, Plus, Eye, Pencil, Sparkles, RefreshCw, AlertCircle, ListChecks,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Drawer from '@/components/ui/Drawer'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import FormField from '@/components/forms/FormField'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { collectionAPI } from '@/services/collection'
import type { PageRes } from '@/types/page'

// 采集项目
interface CollectionProject extends Record<string, unknown> {
  id: number
  code?: string
  name?: string
  project_type?: string
  period_type?: string
  status?: string
  zone_ids?: number[]
  template_id?: number
  started_at?: string
  ended_at?: string
}

// 数据项
interface CollectionItem extends Record<string, unknown> {
  id: number
  project_id?: number
  zone_id?: number
  period_code?: string
  status?: string
  values?: Record<string, any>
  submitted_at?: string
  review_comment?: string
}

// 分页响应

// 项目状态映射
const projectStatusMap: Record<string, { label: string; variant: 'default' | 'info' | 'warning' | 'success' }> = {
  draft: { label: '草稿', variant: 'default' },
  active: { label: '进行中', variant: 'info' },
  paused: { label: '已暂停', variant: 'warning' },
  completed: { label: '已完成', variant: 'success' },
}

// 数据项状态映射
const itemStatusMap: Record<string, { label: string; variant: 'default' | 'info' | 'warning' | 'success' | 'error' }> = {
  pending_edit: { label: '待填报', variant: 'default' },
  edited: { label: '已编辑', variant: 'info' },
  pending_review: { label: '待审核', variant: 'warning' },
  reviewed: { label: '已审核', variant: 'info' },
  locked: { label: '已锁定', variant: 'warning' },
  published: { label: '已发布', variant: 'success' },
}

// 项目类型映射
const projectTypeMap: Record<string, string> = {
  plan: '计划',
  actual: '实际',
  target: '目标',
}

// 周期类型映射
const periodTypeMap: Record<string, string> = {
  daily: '日',
  weekly: '周',
  monthly: '月',
  quarterly: '季',
  yearly: '年',
  once: '单次',
}

const statusFilterOptions = [
  { label: '全部状态', value: 'all' },
  { label: '草稿', value: 'draft' },
  { label: '进行中', value: 'active' },
  { label: '已暂停', value: 'paused' },
  { label: '已完成', value: 'completed' },
]

const projectTypeOptions = [
  { label: '计划', value: 'plan' },
  { label: '实际', value: 'actual' },
  { label: '目标', value: 'target' },
]

const periodTypeOptions = [
  { label: '日', value: 'daily' },
  { label: '周', value: 'weekly' },
  { label: '月', value: 'monthly' },
  { label: '季', value: 'quarterly' },
  { label: '年', value: 'yearly' },
  { label: '单次', value: 'once' },
]

export default function CollectionPage() {
  const toast = useToast()
  const [status, setStatus] = useState('all')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 10

  const { data, loading, error, refetch } = useFetch<PageRes<CollectionProject>>(
    () => collectionAPI.listProjects({
      status: status === 'all' ? undefined : status,
      keyword: keyword || undefined,
      page,
      page_size: pageSize,
    }),
    [status, keyword, page]
  )

  // 创建/编辑
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<CollectionProject | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    code: '',
    name: '',
    project_type: 'plan',
    period_type: 'monthly',
    zone_ids: '',
    started_at: '',
    ended_at: '',
  })

  // 数据项抽屉
  const [itemsDrawerOpen, setItemsDrawerOpen] = useState(false)
  const [itemsProject, setItemsProject] = useState<CollectionProject | null>(null)
  const [items, setItems] = useState<CollectionItem[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)
  const [itemActionLoading, setItemActionLoading] = useState<number | null>(null)

  // 生成数据项
  const [generatingId, setGeneratingId] = useState<number | null>(null)

  const projects = data?.items ?? []
  const total = data?.total ?? 0

  const openCreate = () => {
    setEditing(null)
    setForm({ code: '', name: '', project_type: 'plan', period_type: 'monthly', zone_ids: '', started_at: '', ended_at: '' })
    setModalOpen(true)
  }

  const openEdit = (p: CollectionProject) => {
    setEditing(p)
    setForm({
      code: p.code ?? '',
      name: p.name ?? '',
      project_type: p.project_type ?? 'plan',
      period_type: p.period_type ?? 'monthly',
      zone_ids: Array.isArray(p.zone_ids) ? p.zone_ids.join(', ') : '',
      started_at: p.started_at ?? '',
      ended_at: p.ended_at ?? '',
    })
    setModalOpen(true)
  }

  const handleSave = async () => {
    if (!form.code || !form.name) {
      toast('请填写项目编码与名称', 'warning')
      return
    }
    setSaving(true)
    try {
      const payload = {
        code: form.code,
        name: form.name,
        project_type: form.project_type,
        period_type: form.period_type,
        zone_ids: form.zone_ids
          ? form.zone_ids.split(',').map((s) => Number(s.trim())).filter((n) => !Number.isNaN(n) && n > 0)
          : [],
        started_at: form.started_at || null,
        ended_at: form.ended_at || null,
      }
      if (editing) {
        await collectionAPI.updateProject(editing.id, payload)
        toast('更新成功', 'success')
      } else {
        await collectionAPI.createProject(payload)
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

  // 生成数据项
  const handleGenerate = async (p: CollectionProject) => {
    if (!confirm(`确认按项目「${p.name}」的 zone 生成数据项？`)) return
    setGeneratingId(p.id)
    try {
      const res = await collectionAPI.generateItems(p.id)
      toast(`已生成 ${res?.created ?? 0} 条数据项`, 'success')
      refetch()
    } catch (e) {
      toast(`生成失败：${(e as Error).message}`, 'error')
    } finally {
      setGeneratingId(null)
    }
  }

  // 查看数据项
  const handleViewItems = async (p: CollectionProject) => {
    setItemsProject(p)
    setItemsDrawerOpen(true)
    setItems([])
    setItemsLoading(true)
    try {
      const res = await collectionAPI.listItems({ project_id: p.id, page: 1, page_size: 100 })
      setItems(res?.items ?? [])
    } catch (e) {
      toast(`加载失败：${(e as Error).message}`, 'error')
    } finally {
      setItemsLoading(false)
    }
  }

  // 数据项操作（审批/锁定/发布）
  const handleItemAction = async (item: CollectionItem, action: 'approve' | 'reject' | 'lock' | 'publish') => {
    if (action === 'reject') {
      const reason = prompt('请输入驳回原因')
      if (!reason) return
      setItemActionLoading(item.id)
      try {
        await collectionAPI.rejectItem(item.id, reason)
        toast('已驳回', 'success')
      } catch (e) {
        toast(`驳回失败：${(e as Error).message}`, 'error')
      } finally {
        setItemActionLoading(null)
        if (itemsProject) handleViewItems(itemsProject)
      }
      return
    }
    setItemActionLoading(item.id)
    try {
      if (action === 'approve') await collectionAPI.approveItem(item.id)
      if (action === 'lock') await collectionAPI.lockItem(item.id)
      if (action === 'publish') await collectionAPI.publishItem(item.id)
      toast('操作成功', 'success')
    } catch (e) {
      toast(`操作失败：${(e as Error).message}`, 'error')
    } finally {
      setItemActionLoading(null)
      if (itemsProject) handleViewItems(itemsProject)
    }
  }

  const columns: Column<CollectionProject>[] = [
    {
      key: 'name', title: '项目名称',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-medium text-slate-900 dark:text-slate-100">{row.name ?? '-'}</span>
          <span className="text-xs text-slate-400">{row.code ?? ''}</span>
        </div>
      ),
    },
    {
      key: 'project_type', title: '类型',
      render: (row) => (
        <Badge variant="info">{projectTypeMap[row.project_type ?? 'plan'] ?? row.project_type}</Badge>
      ),
    },
    {
      key: 'period_type', title: '周期',
      render: (row) => (
        <span className="text-slate-600 dark:text-slate-300">
          {periodTypeMap[row.period_type ?? 'monthly'] ?? row.period_type}
        </span>
      ),
    },
    {
      key: 'status', title: '状态',
      render: (row) => {
        const s = projectStatusMap[row.status ?? 'draft'] ?? projectStatusMap.draft
        return <Badge variant={s.variant}>{s.label}</Badge>
      },
    },
    {
      key: 'zone_ids', title: '区划数',
      render: (row) => (
        <span className="text-slate-500">{Array.isArray(row.zone_ids) ? row.zone_ids.length : 0}</span>
      ),
    },
    {
      key: 'actions', title: '操作', width: '180px',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleViewItems(row)}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-700 transition-colors"
            title="查看数据项"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleGenerate(row)}
            disabled={generatingId === row.id}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-violet-600 dark:hover:bg-slate-700 transition-colors disabled:opacity-40"
            title="生成数据项"
          >
            <Sparkles className={`w-4 h-4 ${generatingId === row.id ? 'animate-pulse' : ''}`} />
          </button>
          <button
            onClick={() => openEdit(row)}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-sky-600 dark:hover:bg-slate-700 transition-colors"
            title="编辑"
          >
            <Pencil className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="数据采集"
        description="采集项目编排、数据项状态机与发布管理"
        breadcrumbs={[{ label: '销售执行' }, { label: '数据采集' }]}
        icon={<Database className="w-5 h-5" />}
        actions={
          <Button onClick={openCreate}>
            <Plus className="w-4 h-4" />
            创建项目
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
            placeholder="搜索项目名称"
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

      <DataTable<CollectionProject>
        columns={columns}
        data={projects}
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
        title={editing ? '编辑采集项目' : '创建采集项目'}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>取消</Button>
            <Button loading={saving} onClick={handleSave}>{editing ? '保存' : '创建'}</Button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="项目编码" required>
            <Input placeholder="如：PLAN-2026-01" value={form.code} onChange={(e) => setForm(p => ({ ...p, code: e.target.value }))} />
          </FormField>
          <FormField label="项目名称" required>
            <Input placeholder="请输入项目名称" value={form.name} onChange={(e) => setForm(p => ({ ...p, name: e.target.value }))} />
          </FormField>
          <FormField label="项目类型" required>
            <Select options={projectTypeOptions} value={form.project_type} onChange={(e) => setForm(p => ({ ...p, project_type: e.target.value }))} />
          </FormField>
          <FormField label="周期类型" required>
            <Select options={periodTypeOptions} value={form.period_type} onChange={(e) => setForm(p => ({ ...p, period_type: e.target.value }))} />
          </FormField>
          <div className="sm:col-span-2">
            <FormField label="区划 ID" hint="多个 ID 用英文逗号分隔">
              <Input placeholder="如：1, 2, 3" value={form.zone_ids} onChange={(e) => setForm(p => ({ ...p, zone_ids: e.target.value }))} />
            </FormField>
          </div>
          <FormField label="开始时间">
            <Input type="date" value={form.started_at?.slice(0, 10) ?? ''} onChange={(e) => setForm(p => ({ ...p, started_at: e.target.value }))} />
          </FormField>
          <FormField label="结束时间">
            <Input type="date" value={form.ended_at?.slice(0, 10) ?? ''} onChange={(e) => setForm(p => ({ ...p, ended_at: e.target.value }))} />
          </FormField>
        </div>
      </Modal>

      {/* 数据项抽屉 */}
      <Drawer
        open={itemsDrawerOpen}
        onClose={() => setItemsDrawerOpen(false)}
        title={`数据项 - ${itemsProject?.name ?? ''}`}
        width="w-[640px]"
      >
        <div className="p-5 space-y-3">
          {itemsLoading ? (
            <div className="text-sm text-slate-400">加载中...</div>
          ) : items.length === 0 ? (
            <Empty description="暂无数据项，可点击「生成数据项」按钮创建" icon={<ListChecks className="w-10 h-10" />} />
          ) : (
            items.map((item, i) => {
              const s = itemStatusMap[item.status ?? 'pending_edit'] ?? itemStatusMap.pending_edit
              return (
                <motion.div
                  key={item.id ?? i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="p-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                        数据项 #{item.id}
                      </span>
                      <Badge variant={s.variant}>{s.label}</Badge>
                    </div>
                    <span className="text-xs text-slate-400">{item.period_code ?? '-'}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400 mb-3">
                    <span>区划：{item.zone_id ?? '-'}</span>
                    <span>提交时间：{item.submitted_at ?? '-'}</span>
                  </div>
                  {item.review_comment && (
                    <p className="mb-2 text-xs text-rose-500">驳回原因：{item.review_comment}</p>
                  )}
                  <div className="flex items-center gap-2 flex-wrap">
                    {item.status === 'pending_review' && (
                      <>
                        <Button
                          size="sm"
                          loading={itemActionLoading === item.id}
                          onClick={() => handleItemAction(item, 'approve')}
                        >
                          通过
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          loading={itemActionLoading === item.id}
                          onClick={() => handleItemAction(item, 'reject')}
                        >
                          驳回
                        </Button>
                      </>
                    )}
                    {item.status === 'reviewed' && (
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={itemActionLoading === item.id}
                        onClick={() => handleItemAction(item, 'lock')}
                      >
                        锁定
                      </Button>
                    )}
                    {item.status === 'locked' && (
                      <Button
                        size="sm"
                        loading={itemActionLoading === item.id}
                        onClick={() => handleItemAction(item, 'publish')}
                      >
                        发布
                      </Button>
                    )}
                  </div>
                </motion.div>
              )
            })
          )}
        </div>
      </Drawer>
    </div>
  )
}
