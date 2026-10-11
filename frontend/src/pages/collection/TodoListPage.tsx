import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  ListTodo, Trash2, RefreshCw, MessageSquare, FileText, AlertCircle, Bot, User,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Drawer from '@/components/ui/Drawer'
import Select from '@/components/ui/Select'
import Input from '@/components/ui/Input'
import Empty from '@/components/ui/Empty'
import Skeleton from '@/components/ui/Skeleton'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { collectionAPI } from '@/services/collection'
import type { PageRes } from '@/types/page'

// 待办任务
interface ProjectTodo extends Record<string, unknown> {
  id: number
  project_id?: number
  item_id?: number
  zone_id?: number
  assignee_id?: number
  period_code?: string
  status?: string
  edit_mode?: string
  dialog_session_id?: number
  submitted_at?: string
}

// 对话消息
interface DialogMessage {
  id: number
  role?: string
  content?: string
  ts?: string
}

// 对话记录响应
interface DialogRes {
  todo_id: number
  session?: { id: number; title?: string; agent_name?: string; status?: string; created_at?: string } | null
  messages?: DialogMessage[]
}

// 提交数据响应
interface SubmissionRes {
  todo_id: number
  status?: string
  submit_data?: Record<string, any>
  submitted_at?: string
}

// 分页响应

// 待办状态映射
const todoStatusMap: Record<string, { label: string; variant: 'default' | 'info' | 'warning' | 'success' }> = {
  pending: { label: '待处理', variant: 'warning' },
  in_progress: { label: '进行中', variant: 'info' },
  done: { label: '已完成', variant: 'success' },
  skipped: { label: '已跳过', variant: 'default' },
}

// 编辑模式映射
const editModeMap: Record<string, string> = {
  grid_edit: '表格编辑',
  dialog: '对话采集',
  manual: '手动录入',
}

const statusFilterOptions = [
  { label: '全部状态', value: 'all' },
  { label: '待处理', value: 'pending' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'done' },
]

export default function TodoListPage() {
  const toast = useToast()
  const [projectId, setProjectId] = useState<string>('all')
  const [status, setStatus] = useState('all')
  const [keyword] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 10

  // 项目列表（用于筛选）
  const { data: projectData } = useFetch<PageRes<{ id: number; name?: string }>>(
    () => collectionAPI.listProjects({ page: 1, page_size: 100 }),
    []
  )
  const projectOptions = [
    { label: '全部项目', value: 'all' },
    ...(projectData?.items ?? []).map((p) => ({ label: p.name ?? `项目${p.id}`, value: String(p.id) })),
  ]

  const { data, loading, error, refetch } = useFetch<PageRes<ProjectTodo>>(
    () => collectionAPI.listTodos({
      project_id: projectId === 'all' ? undefined : Number(projectId),
      status: status === 'all' ? undefined : status,
      page,
      page_size: pageSize,
    }),
    [projectId, status, keyword, page]
  )

  const todos = data?.items ?? []
  const total = data?.total ?? 0

  // 选中
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [batchDeleting, setBatchDeleting] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }
  const toggleSelectAll = () => {
    if (todos.every((t) => selectedIds.includes(t.id))) {
      setSelectedIds((prev) => prev.filter((x) => !todos.some((t) => t.id === x)))
    } else {
      setSelectedIds((prev) => Array.from(new Set([...prev, ...todos.map((t) => t.id)])))
    }
  }

  // 对话记录抽屉
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialog, setDialog] = useState<DialogRes | null>(null)
  const [dialogLoading, setDialogLoading] = useState(false)
  const [activeTodo, setActiveTodo] = useState<ProjectTodo | null>(null)

  // 提交数据抽屉
  const [subOpen, setSubOpen] = useState(false)
  const [submission, setSubmission] = useState<SubmissionRes | null>(null)
  const [subLoading, setSubLoading] = useState(false)

  const handleViewDialog = async (todo: ProjectTodo) => {
    setActiveTodo(todo)
    setDialogOpen(true)
    setDialog(null)
    setDialogLoading(true)
    try {
      const res = await collectionAPI.getTodoDialog(todo.id)
      setDialog(res)
    } catch (e) {
      toast(`加载失败：${(e as Error).message}`, 'error')
    } finally {
      setDialogLoading(false)
    }
  }

  const handleViewSubmission = async (todo: ProjectTodo) => {
    setActiveTodo(todo)
    setSubOpen(true)
    setSubmission(null)
    setSubLoading(true)
    try {
      const res = await collectionAPI.getTodoSubmissions(todo.id)
      setSubmission(res)
    } catch (e) {
      toast(`加载失败：${(e as Error).message}`, 'error')
    } finally {
      setSubLoading(false)
    }
  }

  const handleDelete = async (todo: ProjectTodo) => {
    if (todo.status !== 'pending') {
      toast('仅待处理状态可删除', 'warning')
      return
    }
    if (!confirm(`确认删除待办 #${todo.id}？`)) return
    try {
      await collectionAPI.batchDeleteTodos([todo.id])
      toast('已删除', 'success')
      refetch()
    } catch (e) {
      toast(`删除失败：${(e as Error).message}`, 'error')
    }
  }

  const handleBatchDelete = async () => {
    if (selectedIds.length === 0) {
      toast('请先选择待办', 'warning')
      return
    }
    if (!confirm(`确认批量删除 ${selectedIds.length} 条待办？仅「待处理」状态可删除。`)) return
    setBatchDeleting(true)
    try {
      const res = await collectionAPI.batchDeleteTodos(selectedIds)
      toast(`已删除 ${res?.deleted ?? 0} 条`, 'success')
      setSelectedIds([])
      refetch()
    } catch (e) {
      toast(`删除失败：${(e as Error).message}`, 'error')
    } finally {
      setBatchDeleting(false)
    }
  }

  const handleRegenerate = async () => {
    if (projectId === 'all') {
      toast('请先选择一个项目再重新生成待办', 'warning')
      return
    }
    if (!confirm('确认重新生成该项目的待办？将清空「待处理」状态待办并基于待填报/已编辑数据项重新生成。')) return
    setRegenerating(true)
    try {
      const res = await collectionAPI.regenerateTodos(Number(projectId))
      toast(`已重新生成 ${res?.created ?? 0} 条待办`, 'success')
      setSelectedIds([])
      refetch()
    } catch (e) {
      toast(`重新生成失败：${(e as Error).message}`, 'error')
    } finally {
      setRegenerating(false)
    }
  }

  const allChecked = todos.length > 0 && todos.every((t) => selectedIds.includes(t.id))

  const columns: Column<ProjectTodo>[] = [
    {
      key: '_select', title: '', width: '40px',
      render: (row) => (
        <input
          type="checkbox"
          className="w-4 h-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          checked={selectedIds.includes(row.id)}
          onChange={() => toggleSelect(row.id)}
          disabled={row.status !== 'pending'}
        />
      ),
    },
    {
      key: 'project_id', title: '项目',
      render: (row) => {
        const p = projectData?.items?.find((x) => x.id === row.project_id)
        return (
          <span className="font-medium text-slate-900 dark:text-slate-100">
            {p?.name ?? `项目 ${row.project_id}`}
          </span>
        )
      },
    },
    {
      key: 'period_code', title: '周期',
      render: (row) => <span className="text-slate-600 dark:text-slate-300">{row.period_code ?? '-'}</span>,
    },
    {
      key: 'assignee_id', title: '指派人',
      render: (row) => (
        <span className="inline-flex items-center gap-1 text-slate-500">
          <User className="w-3.5 h-3.5" /> 用户 {row.assignee_id ?? '-'}
        </span>
      ),
    },
    {
      key: 'status', title: '状态',
      render: (row) => {
        const s = todoStatusMap[row.status ?? 'pending'] ?? todoStatusMap.pending
        return <Badge variant={s.variant}>{s.label}</Badge>
      },
    },
    {
      key: 'edit_mode', title: '编辑模式',
      render: (row) => (
        <Badge variant="default">{editModeMap[row.edit_mode ?? 'grid_edit'] ?? row.edit_mode}</Badge>
      ),
    },
    {
      key: 'actions', title: '操作', width: '160px',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleViewDialog(row)}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-700 transition-colors"
            title="查看对话记录"
          >
            <MessageSquare className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleViewSubmission(row)}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-sky-600 dark:hover:bg-slate-700 transition-colors"
            title="查看提交数据"
          >
            <FileText className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleDelete(row)}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-rose-600 dark:hover:bg-slate-700 transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="待办任务"
        description="查看采集项目待办、AI 对话记录与提交数据，支持批量删除与重新生成"
        breadcrumbs={[{ label: '销售执行' }, { label: '待办任务' }]}
        icon={<ListTodo className="w-5 h-5" />}
        actions={
          <>
            <Button
              variant="secondary"
              loading={regenerating}
              onClick={handleRegenerate}
              disabled={projectId === 'all'}
              title={projectId === 'all' ? '请先选择项目' : '为当前项目重新生成待办'}
            >
              <RefreshCw className="w-4 h-4" />
              重新生成
            </Button>
            <Button
              variant="danger"
              loading={batchDeleting}
              onClick={handleBatchDelete}
              disabled={selectedIds.length === 0}
            >
              <Trash2 className="w-4 h-4" />
              批量删除{selectedIds.length > 0 ? ` (${selectedIds.length})` : ''}
            </Button>
          </>
        }
      />

      <div className="mb-4 flex items-center gap-3 flex-wrap">
        <div className="w-56">
          <Select
            options={projectOptions}
            value={projectId}
            onChange={(e) => { setProjectId(e.target.value); setPage(1); setSelectedIds([]) }}
          />
        </div>
        <div className="w-40">
          <Select
            options={statusFilterOptions}
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1) }}
          />
        </div>
        <div className="flex-1 min-w-[200px]">
          <Input placeholder="搜索待办" value={keyword} disabled />
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

      <DataTable<ProjectTodo>
        columns={columns}
        data={todos}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
        toolbar={
          <label className="flex items-center gap-2 text-sm text-slate-500 cursor-pointer">
            <input
              type="checkbox"
              className="w-4 h-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              checked={allChecked}
              onChange={toggleSelectAll}
            />
            全选当前页
          </label>
        }
      />

      {/* 对话记录抽屉 */}
      <Drawer
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={`AI 对话记录 - 待办 #${activeTodo?.id ?? ''}`}
        width="w-[560px]"
      >
        <div className="p-5 space-y-4">
          {dialogLoading ? (
            <Skeleton lines={4} />
          ) : !dialog?.session ? (
            <Empty description="该待办暂无 AI 对话记录" icon={<MessageSquare className="w-10 h-10" />} />
          ) : (
            <>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40 text-sm">
                <p className="font-medium text-slate-900 dark:text-slate-100">{dialog.session.title ?? 'AI 对话'}</p>
                <p className="mt-1 text-xs text-slate-400">
                  Agent: {dialog.session.agent_name ?? '-'} · 创建于 {dialog.session.created_at ?? '-'}
                </p>
              </div>
              <div className="space-y-3">
                {(dialog.messages ?? []).map((m) => (
                  <motion.div
                    key={m.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex items-start gap-2 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}
                  >
                    <div className={`flex items-center justify-center w-7 h-7 rounded-lg shrink-0 ${
                      m.role === 'user'
                        ? 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                        : 'bg-gradient-to-br from-brand-500 to-violet-500 text-white'
                    }`}>
                      {m.role === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                    </div>
                    <div className={`max-w-[75%] px-3 py-2 rounded-2xl text-sm ${
                      m.role === 'user'
                        ? 'bg-brand-600 text-white rounded-tr-sm'
                        : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-tl-sm'
                    }`}>
                      {m.content ?? ''}
                    </div>
                  </motion.div>
                ))}
              </div>
            </>
          )}
        </div>
      </Drawer>

      {/* 提交数据抽屉 */}
      <Drawer
        open={subOpen}
        onClose={() => setSubOpen(false)}
        title={`提交数据 - 待办 #${activeTodo?.id ?? ''}`}
        width="w-[560px]"
      >
        <div className="p-5 space-y-4">
          {subLoading ? (
            <Skeleton lines={4} />
          ) : !submission?.submit_data || Object.keys(submission.submit_data).length === 0 ? (
            <Empty description="该待办暂无提交数据" icon={<FileText className="w-10 h-10" />} />
          ) : (
            <>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40 text-sm flex items-center justify-between">
                <span className="text-slate-500">提交时间</span>
                <span className="font-medium text-slate-900 dark:text-slate-100">{submission.submitted_at ?? '-'}</span>
              </div>
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800/80">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-slate-600 dark:text-slate-300">字段</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-600 dark:text-slate-300">值</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                    {Object.entries(submission.submit_data).map(([k, v]) => (
                      <tr key={k}>
                        <td className="px-4 py-2 text-slate-500">{k}</td>
                        <td className="px-4 py-2 text-slate-900 dark:text-slate-100">{String(v)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </Drawer>
    </div>
  )
}
