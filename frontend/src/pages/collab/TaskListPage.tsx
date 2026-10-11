import { useState } from 'react'
import { CheckSquare, Clock, AlertCircle, Play, Check, Plus } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { collabAPI } from '@/services/collab'
import type { PageRes } from '@/types/page'

interface TaskItem {
  id: number
  title: string
  description?: string
  task_type?: string
  status?: string
  priority?: string
  assignee_id?: number
  creator_id?: number
  due_date?: string
  completed_at?: string
  related_type?: string
  related_id?: number
  created_at?: string
}


const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  pending: { label: '待处理', cls: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300' },
  in_progress: { label: '进行中', cls: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300' },
  completed: { label: '已完成', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
  cancelled: { label: '已取消', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
}

const PRIORITY_CONFIG: Record<string, { label: string; cls: string }> = {
  high: { label: '高', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
  medium: { label: '中', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  low: { label: '低', cls: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300' },
}

const TYPE_LABEL: Record<string, string> = {
  general: '常规',
  visit: '拜访',
  follow_up: '跟进',
  training: '培训',
}

function isOverdue(dueDate?: string, status?: string): boolean {
  if (!dueDate || status === 'completed' || status === 'cancelled') return false
  return new Date(dueDate).getTime() < Date.now()
}

export default function TaskListPage() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [actingId, setActingId] = useState<number | null>(null)

  const { data, loading, refetch } = useFetch<PageRes<TaskItem>>(
    () =>
      collabAPI.getTasks({
        status: statusFilter === 'all' ? undefined : statusFilter,
        task_type: typeFilter === 'all' ? undefined : typeFilter,
        page: 1,
        page_size: 50,
      }),
    [statusFilter, typeFilter]
  )

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const handleUpdateStatus = async (id: number, status: string) => {
    setActingId(id)
    try {
      await collabAPI.updateTaskStatus(id, status)
      toast('状态已更新', 'success')
      refetch()
    } catch (e) {
      toast(`更新失败：${(e as Error).message}`, 'error')
    } finally {
      setActingId(null)
    }
  }

  return (
    <div>
      <PageHeader
        title="任务管理"
        description="创建、跟踪与完成任务"
        breadcrumbs={[{ label: '协同办公' }, { label: '任务管理' }]}
        icon={<CheckSquare className="w-5 h-5" />}
        actions={
          <>
            <AIActionButton label="AI优先排序" prompt="分析我的待办任务，给出优先级排序" variant="ghost" size="sm" />
            <button
              onClick={() => toast('新建任务功能开发中', 'info')}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              新建任务
            </button>
          </>
        }
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
            <option value="pending">待处理</option>
            <option value="in_progress">进行中</option>
            <option value="completed">已完成</option>
            <option value="cancelled">已取消</option>
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
            <option value="general">常规</option>
            <option value="visit">拜访</option>
            <option value="follow_up">跟进</option>
            <option value="training">培训</option>
          </select>
        </div>
        <span className="text-sm text-slate-400">共 {total} 条</span>
      </div>

      {/* 任务列表 */}
      {loading ? (
        <div className="p-6 text-slate-500">加载中...</div>
      ) : items.length === 0 ? (
        <Empty description="暂无任务" />
      ) : (
        <div className="space-y-3">
          {items.map((task) => {
            const stCfg = STATUS_CONFIG[task.status ?? 'pending'] || STATUS_CONFIG.pending
            const prCfg = PRIORITY_CONFIG[task.priority ?? 'low'] || PRIORITY_CONFIG.low
            const overdue = isOverdue(task.due_date, task.status)
            return (
              <div key={task.id} className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="font-medium text-slate-900 dark:text-slate-100">{task.title}</h3>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${stCfg.cls}`}>
                        {stCfg.label}
                      </span>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${prCfg.cls}`}>
                        {prCfg.label}优先级
                      </span>
                      {task.task_type && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                          {TYPE_LABEL[task.task_type] || task.task_type}
                        </span>
                      )}
                    </div>
                    {task.description && (
                      <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">{task.description}</p>
                    )}
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      {task.due_date && (
                        <span className={`inline-flex items-center gap-1 ${overdue ? 'text-rose-600 dark:text-rose-400 font-medium' : ''}`}>
                          {overdue ? <AlertCircle className="w-3.5 h-3.5" /> : <Clock className="w-3.5 h-3.5" />}
                          截止 {task.due_date}
                        </span>
                      )}
                      <span>创建于 {task.created_at ?? '-'}</span>
                    </div>
                  </div>
                  {/* 操作按钮 */}
                  <div className="flex items-center gap-2 shrink-0">
                    {task.status === 'pending' && (
                      <button
                        onClick={() => handleUpdateStatus(task.id, 'in_progress')}
                        disabled={actingId === task.id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-sky-600 text-white text-xs font-medium hover:bg-sky-700 disabled:opacity-50 transition-colors"
                      >
                        <Play className="w-3.5 h-3.5" />
                        开始
                      </button>
                    )}
                    {task.status === 'in_progress' && (
                      <button
                        onClick={() => handleUpdateStatus(task.id, 'completed')}
                        disabled={actingId === task.id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                      >
                        <Check className="w-3.5 h-3.5" />
                        完成
                      </button>
                    )}
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
