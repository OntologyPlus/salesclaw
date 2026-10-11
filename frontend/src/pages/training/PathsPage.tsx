import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Route, Plus, Eye, AlertCircle, Users, Award, Layers, Target, BookOpen,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import FormField from '@/components/forms/FormField'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { trainingAPI } from '@/services/training'
import type { PageRes } from '@/types/page'

// 学习路径
interface PathItem extends Record<string, unknown> {
  id: number | string
  title?: string
  description?: string
  target_role?: string
  total_credits?: number
  enroll_count?: number
  is_published?: boolean
  stages?: PathStage[]
}

// 路径阶段
interface PathStage {
  id?: number | string
  name?: string
  description?: string
  course_ids?: number[]
  required_credits?: number
}

// 分页响应

export default function PathsPage() {
  const toast = useToast()
  const [page, setPage] = useState(1)
  const pageSize = 12

  // 列表数据
  const { data, loading, error, refetch } = useFetch<PageRes<PathItem>>(
    () => trainingAPI.listPaths({ page }),
    [page]
  )

  // 新建 Modal
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [form, setForm] = useState({
    title: '',
    description: '',
    target_role: '',
    total_credits: 10,
  })

  // 详情 Modal
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailPath, setDetailPath] = useState<PathItem | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [enrolling, setEnrolling] = useState(false)

  const items = data?.items ?? []

  // 创建路径
  const handleCreate = async () => {
    if (!form.title) {
      toast('请填写路径标题', 'warning')
      return
    }
    setCreateLoading(true)
    try {
      await trainingAPI.createPath({
        title: form.title,
        description: form.description,
        target_role: form.target_role,
        total_credits: Number(form.total_credits) || 0,
      })
      toast('路径创建成功', 'success')
      setCreateOpen(false)
      setForm({ title: '', description: '', target_role: '', total_credits: 10 })
      refetch()
    } catch (e) {
      toast(`创建失败：${(e as Error).message}`, 'error')
    } finally {
      setCreateLoading(false)
    }
  }

  // 查看详情
  const handleView = async (path: PathItem) => {
    setDetailOpen(true)
    setDetailLoading(true)
    setDetailPath(path)
    try {
      const detail = await trainingAPI.getPath(path.id as number)
      setDetailPath(detail ?? path)
    } catch {
      // 详情加载失败时保留列表数据
    } finally {
      setDetailLoading(false)
    }
  }

  // 选路径
  const handleEnroll = async () => {
    if (!detailPath) return
    setEnrolling(true)
    try {
      await trainingAPI.enrollPath(detailPath.id as number)
      toast('已加入学习路径', 'success')
    } catch (e) {
      toast(`加入失败：${(e as Error).message}`, 'error')
    } finally {
      setEnrolling(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="学习路径"
        description="体系化成长路径，按角色规划学习进阶"
        breadcrumbs={[{ label: '智能培训' }, { label: '学习路径' }]}
        icon={<Route className="w-5 h-5" />}
        actions={
          <>
            <AIActionButton label="AI路径优化" prompt="分析我的学习路径进度，给出优化建议" variant="ghost" size="sm" />
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="w-4 h-4" />
              新建路径
            </Button>
          </>
        }
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      {/* 卡片网格 */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <Skeleton lines={3} />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <Empty description="暂无学习路径" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((path, i) => (
            <motion.div
              key={path.id ?? i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 hover:shadow-md hover:border-brand-300 transition-all flex flex-col"
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-white shrink-0">
                  <Route className="w-5 h-5" />
                </div>
                <Badge variant="info">{path.total_credits ?? 0} 学分</Badge>
              </div>
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-1">
                {path.title ?? '-'}
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-2 mb-3 flex-1">
                {path.description ?? '体系化成长路径'}
              </p>
              <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400 mb-4">
                {path.target_role && (
                  <span className="inline-flex items-center gap-1">
                    <Target className="w-3.5 h-3.5" /> {path.target_role}
                  </span>
                )}
                <span className="inline-flex items-center gap-1">
                  <Layers className="w-3.5 h-3.5" /> {path.stages?.length ?? 0} 阶段
                </span>
                <span className="inline-flex items-center gap-1">
                  <Users className="w-3.5 h-3.5" /> {path.enroll_count ?? 0}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="secondary" onClick={() => handleView(path)}>
                  <Eye className="w-3.5 h-3.5" /> 查看详情
                </Button>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* 分页 */}
      {!loading && items.length > 0 && (
        <div className="mt-4 flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            上一页
          </button>
          <span className="px-3 text-slate-600 dark:text-slate-300">第 {page} 页</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={items.length < pageSize}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            下一页
          </button>
        </div>
      )}

      {/* 新建路径 Modal */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建学习路径"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button loading={createLoading} onClick={handleCreate}>创建</Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField label="路径标题" required>
            <Input placeholder="请输入路径标题" value={form.title} onChange={(e) => setForm(p => ({ ...p, title: e.target.value }))} />
          </FormField>
          <FormField label="路径描述">
            <textarea
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-100 min-h-[80px]"
              placeholder="请输入路径描述"
              value={form.description}
              onChange={(e) => setForm(p => ({ ...p, description: e.target.value }))}
            />
          </FormField>
          <FormField label="目标角色" hint="如：医药代表、区域经理">
            <Input placeholder="请输入目标角色" value={form.target_role} onChange={(e) => setForm(p => ({ ...p, target_role: e.target.value }))} />
          </FormField>
          <FormField label="总学分" required>
            <Input type="number" min={0} value={form.total_credits} onChange={(e) => setForm(p => ({ ...p, total_credits: Number(e.target.value) || 0 }))} />
          </FormField>
        </div>
      </Modal>

      {/* 详情 Modal */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title="学习路径详情"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDetailOpen(false)}>关闭</Button>
            <Button loading={enrolling} onClick={handleEnroll}>加入学习</Button>
          </>
        }
      >
        {detailLoading ? (
          <div className="py-6"><Skeleton lines={5} /></div>
        ) : detailPath && (
          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{detailPath.title}</h3>
                <Badge variant="info">{detailPath.total_credits ?? 0} 学分</Badge>
              </div>
              {detailPath.description && (
                <p className="text-sm text-slate-500 dark:text-slate-400">{detailPath.description}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-400">目标角色</p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100 inline-flex items-center gap-1">
                  <Target className="w-3.5 h-3.5" /> {detailPath.target_role ?? '-'}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-400">已加入</p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100 inline-flex items-center gap-1">
                  <Users className="w-3.5 h-3.5" /> {detailPath.enroll_count ?? 0} 人
                </p>
              </div>
            </div>

            {/* 阶段列表 */}
            <div>
              <p className="text-xs text-slate-400 mb-2">学习阶段</p>
              {detailPath.stages && detailPath.stages.length > 0 ? (
                <div className="space-y-3">
                  {detailPath.stages.map((stage, idx) => (
                    <div key={stage.id ?? idx} className="p-4 rounded-xl border border-slate-200 dark:border-slate-800">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="flex items-center justify-center w-6 h-6 rounded-lg bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400 text-xs font-bold">
                            {idx + 1}
                          </span>
                          <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{stage.name ?? `阶段 ${idx + 1}`}</span>
                        </div>
                        <Badge variant="info">
                          <Award className="w-3 h-3 mr-1" /> {stage.required_credits ?? 0} 学分
                        </Badge>
                      </div>
                      {stage.description && (
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{stage.description}</p>
                      )}
                      {Array.isArray(stage.course_ids) && stage.course_ids.length > 0 && (
                        <p className="mt-1 text-xs text-slate-400 inline-flex items-center gap-1">
                          <BookOpen className="w-3 h-3" /> 含 {stage.course_ids.length} 门课程
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400 py-4 text-center">暂无阶段信息</p>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
