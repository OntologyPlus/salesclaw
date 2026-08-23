import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  BookOpen, Plus, Eye, Pencil, Trash2, AlertCircle, Star, Clock, Users, Search,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import AIEnhancedPage from '@/components/ai/AIEnhancedPage'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import FormField from '@/components/forms/FormField'
import Tabs from '@/components/ui/Tabs'
import Skeleton from '@/components/ui/Skeleton'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { trainingAPI } from '@/services/training'

// 课程行
interface CourseItem extends Record<string, unknown> {
  id: number | string
  title?: string
  description?: string
  course_type?: string
  category?: string
  difficulty?: string
  duration_minutes?: number
  enroll_count?: number
  avg_rating?: number
  is_published?: boolean
  content_url?: string
  tags?: string[]
}

// 课程进度
interface CourseProgress {
  status?: string
  progress?: number
  last_position?: number
  enrolled_at?: string
  completed_at?: string
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 课程类型映射
const courseTypeMap: Record<string, string> = {
  video: '视频',
  article: '图文',
  live: '直播',
  scorm: 'SCORM',
}

// 难度映射
const difficultyMap: Record<string, { label: string; variant: 'default' | 'warning' | 'success' | 'error' | 'info' }> = {
  easy: { label: '入门', variant: 'success' },
  medium: { label: '中级', variant: 'warning' },
  hard: { label: '高级', variant: 'error' },
}

// 分类 Tabs
const categoryTabs = [
  { key: 'all', label: '全部' },
  { key: 'product', label: '产品知识' },
  { key: 'skill', label: '销售技能' },
  { key: 'compliance', label: '合规' },
  { key: 'industry', label: '行业' },
]

// 难度过滤
const difficultyTabs = [
  { key: 'all', label: '全部难度' },
  { key: 'easy', label: '入门' },
  { key: 'medium', label: '中级' },
  { key: 'hard', label: '高级' },
]

export default function CoursesPage() {
  const toast = useToast()
  const [category, setCategory] = useState('all')
  const [difficulty, setDifficulty] = useState('all')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 10

  // 列表数据
  const { data, loading, error, refetch } = useFetch<PageRes<CourseItem>>(
    () => trainingAPI.listCourses({
      category: category === 'all' ? undefined : category,
      difficulty: difficulty === 'all' ? undefined : difficulty,
      keyword: keyword || undefined,
      page,
      page_size: pageSize,
    }),
    [category, difficulty, keyword, page]
  )

  // 新建/编辑 Modal
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<CourseItem | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    title: '',
    description: '',
    course_type: 'video',
    category: 'product',
    difficulty: 'medium',
    duration_minutes: 30,
    content_url: '',
    tags: '',
  })

  // 详情 Modal
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailCourse, setDetailCourse] = useState<CourseItem | null>(null)
  const [progress, setProgress] = useState<CourseProgress | null>(null)
  const [progressLoading, setProgressLoading] = useState(false)
  const [enrolling, setEnrolling] = useState(false)

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const courseTypeOptions = [
    { label: '视频', value: 'video' },
    { label: '图文', value: 'article' },
    { label: '直播', value: 'live' },
    { label: 'SCORM', value: 'scorm' },
  ]
  const categoryOptions = [
    { label: '产品知识', value: 'product' },
    { label: '销售技能', value: 'skill' },
    { label: '合规', value: 'compliance' },
    { label: '行业', value: 'industry' },
  ]
  const difficultyOptions = [
    { label: '入门', value: 'easy' },
    { label: '中级', value: 'medium' },
    { label: '高级', value: 'hard' },
  ]

  // 打开新建
  const openCreate = () => {
    setEditing(null)
    setForm({
      title: '', description: '', course_type: 'video', category: 'product',
      difficulty: 'medium', duration_minutes: 30, content_url: '', tags: '',
    })
    setModalOpen(true)
  }

  // 打开编辑
  const openEdit = (course: CourseItem) => {
    setEditing(course)
    setForm({
      title: course.title ?? '',
      description: course.description ?? '',
      course_type: course.course_type ?? 'video',
      category: course.category ?? 'product',
      difficulty: course.difficulty ?? 'medium',
      duration_minutes: course.duration_minutes ?? 30,
      content_url: course.content_url ?? '',
      tags: Array.isArray(course.tags) ? course.tags.join(', ') : '',
    })
    setModalOpen(true)
  }

  // 保存
  const handleSave = async () => {
    if (!form.title) {
      toast('请填写课程标题', 'warning')
      return
    }
    setSaving(true)
    try {
      const payload = {
        title: form.title,
        description: form.description,
        course_type: form.course_type,
        category: form.category,
        difficulty: form.difficulty,
        duration_minutes: Number(form.duration_minutes) || 0,
        content_url: form.content_url,
        tags: form.tags ? form.tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
      }
      if (editing) {
        await trainingAPI.updateCourse(editing.id as number, payload)
        toast('更新成功', 'success')
      } else {
        await trainingAPI.createCourse(payload)
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

  // 删除
  const handleDelete = async (id: number | string) => {
    if (!confirm('确认删除该课程？')) return
    try {
      await trainingAPI.deleteCourse(id as number)
      toast('已删除', 'success')
      refetch()
    } catch (e) {
      toast(`删除失败：${(e as Error).message}`, 'error')
    }
  }

  // 查看详情（含进度）
  const handleView = async (course: CourseItem) => {
    setDetailCourse(course)
    setDetailOpen(true)
    setProgress(null)
    setProgressLoading(true)
    try {
      const p = await trainingAPI.getCourseProgress(course.id as number)
      setProgress(p)
    } catch {
      // 未选课时接口可能返回错误，忽略
      setProgress(null)
    } finally {
      setProgressLoading(false)
    }
  }

  // 选课
  const handleEnroll = async () => {
    if (!detailCourse) return
    setEnrolling(true)
    try {
      await trainingAPI.enrollCourse(detailCourse.id as number)
      toast('选课成功', 'success')
      const p = await trainingAPI.getCourseProgress(detailCourse.id as number)
      setProgress(p)
    } catch (e) {
      toast(`选课失败：${(e as Error).message}`, 'error')
    } finally {
      setEnrolling(false)
    }
  }

  // 更新进度
  const handleUpdateProgress = async (val: number) => {
    if (!detailCourse) return
    try {
      await trainingAPI.updateCourseProgress(detailCourse.id as number, { progress: val })
      setProgress((prev) => ({ ...prev, progress: val }))
      toast('进度已更新', 'success')
    } catch (e) {
      toast(`更新失败：${(e as Error).message}`, 'error')
    }
  }

  // 表格列定义
  const columns: Column<CourseItem>[] = [
    {
      key: 'title', title: '标题',
      render: (row) => (
        <span className="font-medium text-slate-900 dark:text-slate-100">{row.title ?? '-'}</span>
      ),
    },
    {
      key: 'course_type', title: '类型',
      render: (row) => row.course_type ? (
        <Badge variant="info">{courseTypeMap[row.course_type] ?? row.course_type}</Badge>
      ) : <span className="text-slate-400">-</span>,
    },
    {
      key: 'category', title: '分类',
      render: (row) => {
        const opt = categoryOptions.find((o) => o.value === row.category)
        return <span>{opt?.label ?? row.category ?? '-'}</span>
      },
    },
    {
      key: 'difficulty', title: '难度',
      render: (row) => {
        const d = difficultyMap[row.difficulty ?? 'medium'] ?? difficultyMap.medium
        return <Badge variant={d.variant}>{d.label}</Badge>
      },
    },
    {
      key: 'duration_minutes', title: '时长',
      render: (row) => (
        <span className="inline-flex items-center gap-1 text-slate-500">
          <Clock className="w-3.5 h-3.5" /> {row.duration_minutes ?? 0} 分钟
        </span>
      ),
    },
    {
      key: 'enroll_count', title: '选课数',
      render: (row) => (
        <span className="inline-flex items-center gap-1 text-slate-500">
          <Users className="w-3.5 h-3.5" /> {row.enroll_count ?? 0}
        </span>
      ),
    },
    {
      key: 'avg_rating', title: '评分',
      render: (row) => (
        <span className="inline-flex items-center gap-1 text-amber-500">
          <Star className="w-3.5 h-3.5" /> {row.avg_rating ?? '-'}
        </span>
      ),
    },
    {
      key: 'actions', title: '操作', width: '140px',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button onClick={() => handleView(row)} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-700 transition-colors" title="查看详情">
            <Eye className="w-4 h-4" />
          </button>
          <button onClick={() => openEdit(row)} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-sky-600 dark:hover:bg-slate-700 transition-colors" title="编辑">
            <Pencil className="w-4 h-4" />
          </button>
          <button onClick={() => handleDelete(row.id)} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-rose-600 dark:hover:bg-slate-700 transition-colors" title="删除">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ]

  return (
    <AIEnhancedPage
      header={
        <PageHeader
          title="课程中心"
          description="课程浏览、选课、学习与进度管理"
          breadcrumbs={[{ label: '智能培训' }, { label: '课程中心' }]}
          icon={<BookOpen className="w-5 h-5" />}
          actions={
            <>
              <AIActionButton label="AI推荐课程" prompt="根据我的能力缺口，推荐最适合的课程" variant="ghost" size="sm" />
              <Button onClick={openCreate}>
                <Plus className="w-4 h-4" />
                新建课程
              </Button>
            </>
          }
        />
      }
    >
      {/* 分类过滤 */}
      <div className="mb-3">
        <Tabs tabs={categoryTabs} activeKey={category} onChange={(k) => { setCategory(k); setPage(1) }} />
      </div>
      <div className="mb-4 flex items-center gap-3 flex-wrap">
        <div className="w-48">
          <Select
            options={difficultyTabs.map((t) => ({ label: t.label, value: t.key }))}
            value={difficulty}
            onChange={(e) => { setDifficulty(e.target.value); setPage(1) }}
          />
        </div>
        <div className="flex-1 min-w-[200px]">
          <Input
            placeholder="搜索课程标题"
            prefix={<Search className="w-4 h-4" />}
            value={keyword}
            onChange={(e) => { setKeyword(e.target.value); setPage(1) }}
          />
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <DataTable<CourseItem>
        columns={columns}
        data={items}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
        emptyResource="课程"
        emptyDescription="还没有任何课程"
        emptyContext={`当前分类：${category}；当前时间：${new Date().toISOString().slice(0, 10)}`}
        aiExplainable={(r) => `课程：标题=${r.title}，分类=${r.category}，时长=${r.duration_minutes}分钟，难度=${r.difficulty}，选课数=${r.enroll_count}`}
      />

      {/* 新建/编辑 Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? '编辑课程' : '新建课程'}
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
            <FormField label="课程标题" required>
              <Input placeholder="请输入课程标题" value={form.title} onChange={(e) => setForm(p => ({ ...p, title: e.target.value }))} />
            </FormField>
          </div>
          <div className="sm:col-span-2">
            <FormField label="课程描述">
              <textarea
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100 min-h-[80px]"
                placeholder="请输入课程描述"
                value={form.description}
                onChange={(e) => setForm(p => ({ ...p, description: e.target.value }))}
              />
            </FormField>
          </div>
          <FormField label="课程类型" required>
            <Select options={courseTypeOptions} value={form.course_type} onChange={(e) => setForm(p => ({ ...p, course_type: e.target.value }))} />
          </FormField>
          <FormField label="分类" required>
            <Select options={categoryOptions} value={form.category} onChange={(e) => setForm(p => ({ ...p, category: e.target.value }))} />
          </FormField>
          <FormField label="难度" required>
            <Select options={difficultyOptions} value={form.difficulty} onChange={(e) => setForm(p => ({ ...p, difficulty: e.target.value }))} />
          </FormField>
          <FormField label="时长（分钟）" required>
            <Input type="number" min={1} value={form.duration_minutes} onChange={(e) => setForm(p => ({ ...p, duration_minutes: Number(e.target.value) || 0 }))} />
          </FormField>
          <div className="sm:col-span-2">
            <FormField label="内容链接" hint="视频/图文 URL">
              <Input placeholder="https://..." value={form.content_url} onChange={(e) => setForm(p => ({ ...p, content_url: e.target.value }))} />
            </FormField>
          </div>
          <div className="sm:col-span-2">
            <FormField label="标签" hint="多个标签用英文逗号分隔">
              <Input placeholder="如：降压药, 心血管" value={form.tags} onChange={(e) => setForm(p => ({ ...p, tags: e.target.value }))} />
            </FormField>
          </div>
        </div>
      </Modal>

      {/* 详情 Modal */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title="课程详情"
        size="lg"
        footer={
          <>
            {progress?.status && progress.status !== 'not_enrolled' && (
              <Button
                variant="ghost"
                onClick={() => progress && handleUpdateProgress(Math.min(100, (progress.progress ?? 0) + 20))}
              >
                更新进度 +20%
              </Button>
            )}
            <Button variant="secondary" onClick={() => setDetailOpen(false)}>关闭</Button>
            {!progress?.status || progress.status === 'not_enrolled' ? (
              <Button loading={enrolling} onClick={handleEnroll}>立即选课</Button>
            ) : progress.status === 'completed' ? (
              <Button variant="secondary" disabled>已完成</Button>
            ) : (
              <Button variant="secondary" disabled>学习中</Button>
            )}
          </>
        }
      >
        {detailCourse && (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{detailCourse.title}</h3>
              {detailCourse.description && (
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{detailCourse.description}</p>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-400">类型</p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">
                  {detailCourse.course_type ? (courseTypeMap[detailCourse.course_type] ?? detailCourse.course_type) : '-'}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-400">难度</p>
                <p className="mt-0.5">
                  {(() => {
                    const d = difficultyMap[detailCourse.difficulty ?? 'medium'] ?? difficultyMap.medium
                    return <Badge variant={d.variant}>{d.label}</Badge>
                  })()}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-400">时长</p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">{detailCourse.duration_minutes ?? 0} 分钟</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-400">评分</p>
                <p className="mt-0.5 text-sm font-medium text-amber-500 inline-flex items-center gap-1">
                  <Star className="w-3.5 h-3.5" /> {detailCourse.avg_rating ?? '-'}
                </p>
              </div>
            </div>

            {/* 学习进度 */}
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">学习进度</span>
                {progress?.status && progress.status !== 'not_enrolled' && (
                  <Badge variant={progress.status === 'completed' ? 'success' : 'warning'}>
                    {progress.status === 'completed' ? '已完成' : '学习中'}
                  </Badge>
                )}
              </div>
              {progressLoading ? (
                <Skeleton lines={1} />
              ) : progress?.status && progress.status !== 'not_enrolled' ? (
                <div>
                  <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-brand-500 to-violet-500"
                      initial={{ width: 0 }}
                      animate={{ width: `${progress.progress ?? 0}%` }}
                      transition={{ duration: 0.4 }}
                    />
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                    <span>{progress.progress ?? 0}%</span>
                    <span>选课时间：{progress.enrolled_at ?? '-'}</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-400">尚未选课，点击"立即选课"开始学习</p>
              )}
            </div>
          </div>
        )}
      </Modal>
    </AIEnhancedPage>
  )
}
