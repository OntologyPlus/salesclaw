import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import {
  UserCheck, Award, BookOpen, Route, CheckCircle2, Clock, AlertCircle, ArrowRight,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Badge from '@/components/ui/Badge'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import { trainingAPI } from '@/services/training'

// 我的学习数据
interface MyLearning {
  in_progress_courses?: CourseProgressItem[]
  completed_courses?: CourseProgressItem[]
  in_progress_paths?: PathProgressItem[]
  credits?: number
  certificates_count?: number
}

// 进行中/已完成课程
interface CourseProgressItem {
  id: number | string
  title?: string
  course_type?: string
  category?: string
  difficulty?: string
  duration_minutes?: number
  progress?: number
  status?: string
  enrolled_at?: string
  completed_at?: string
}

// 进行中学习路径
interface PathProgressItem {
  id: number | string
  title?: string
  description?: string
  target_role?: string
  total_credits?: number
  stages?: unknown[]
  progress?: number
}

// 难度映射
const difficultyMap: Record<string, { label: string; variant: 'default' | 'warning' | 'success' | 'error' | 'info' }> = {
  easy: { label: '入门', variant: 'success' },
  medium: { label: '中级', variant: 'warning' },
  hard: { label: '高级', variant: 'error' },
}

export default function MyLearningPage() {
  const { data, loading, error } = useFetch<MyLearning>(
    () => trainingAPI.getMyLearning(),
    []
  )

  const inProgress = data?.in_progress_courses ?? []
  const completed = data?.completed_courses ?? []
  const paths = data?.in_progress_paths ?? []

  const stats = [
    { title: '已获学分', value: data?.credits ?? '-', icon: <Award className="w-5 h-5" />, color: 'amber' as const, trend: 8 },
    { title: '证书数', value: data?.certificates_count ?? '-', icon: <Award className="w-5 h-5" />, color: 'emerald' as const, trend: 5 },
    { title: '进行中课程', value: inProgress.length, icon: <BookOpen className="w-5 h-5" />, color: 'brand' as const, trend: 3 },
    { title: '进行中路径', value: paths.length, icon: <Route className="w-5 h-5" />, color: 'cyan' as const, trend: 2 },
  ]

  return (
    <div>
      <PageHeader
        title="我的学习"
        description="个人学习进度、学分与证书追踪"
        breadcrumbs={[{ label: '智能培训' }, { label: '我的学习' }]}
        icon={<UserCheck className="w-5 h-5" />}
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((stat, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
          >
            {loading ? (
              <div className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                <Skeleton lines={2} />
              </div>
            ) : (
              <StatCard {...stat} />
            )}
          </motion.div>
        ))}
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 进行中课程 */}
        <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">进行中课程</h2>
            <Link to="/training/courses" className="flex items-center gap-1 text-sm text-brand-600 dark:text-brand-400 hover:underline">
              去选课 <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {loading ? (
              <div className="p-5"><Skeleton lines={4} /></div>
            ) : inProgress.length === 0 ? (
              <Empty description="暂无进行中课程" />
            ) : (
              inProgress.map((course, i) => {
                const diff = difficultyMap[course.difficulty ?? 'medium'] ?? difficultyMap.medium
                return (
                  <motion.div
                    key={course.id ?? i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                          {course.title ?? '-'}
                        </span>
                        <Badge variant={diff.variant}>{diff.label}</Badge>
                      </div>
                      <span className="text-xs text-slate-400 shrink-0">{course.progress ?? 0}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-brand-500 to-violet-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${course.progress ?? 0}%` }}
                        transition={{ duration: 0.4, delay: i * 0.05 }}
                      />
                    </div>
                    <div className="mt-1.5 flex items-center gap-1 text-xs text-slate-400">
                      <Clock className="w-3 h-3" /> {course.duration_minutes ?? 0} 分钟
                    </div>
                  </motion.div>
                )
              })
            )}
          </div>
        </div>

        {/* 已完成课程 */}
        <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">已完成课程</h2>
            <span className="text-xs text-slate-400">共 {completed.length} 门</span>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {loading ? (
              <div className="p-5"><Skeleton lines={4} /></div>
            ) : completed.length === 0 ? (
              <Empty description="暂无已完成课程" />
            ) : (
              completed.map((course, i) => {
                const diff = difficultyMap[course.difficulty ?? 'medium'] ?? difficultyMap.medium
                return (
                  <motion.div
                    key={course.id ?? i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                        <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                          {course.title ?? '-'}
                        </span>
                        <Badge variant={diff.variant}>{diff.label}</Badge>
                      </div>
                      <p className="mt-0.5 text-xs text-slate-400">
                        完成于 {course.completed_at ?? '-'}
                      </p>
                    </div>
                  </motion.div>
                )
              })
            )}
          </div>
        </div>
      </div>

      {/* 进行中学习路径 */}
      <div className="mt-6 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">进行中学习路径</h2>
          <Link to="/training/paths" className="flex items-center gap-1 text-sm text-brand-600 dark:text-brand-400 hover:underline">
            查看路径 <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-700">
          {loading ? (
            <div className="p-5"><Skeleton lines={3} /></div>
          ) : paths.length === 0 ? (
            <Empty description="暂无进行中学习路径" />
          ) : (
            paths.map((path, i) => (
              <motion.div
                key={path.id ?? i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
              >
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                      {path.title ?? '-'}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 truncate">
                      {path.target_role ? `目标角色：${path.target_role}` : (path.description ?? '体系化成长路径')}
                    </p>
                  </div>
                  <Badge variant="info">{path.total_credits ?? 0} 学分</Badge>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500"
                      initial={{ width: 0 }}
                      animate={{ width: `${path.progress ?? 0}%` }}
                      transition={{ duration: 0.4, delay: i * 0.05 }}
                    />
                  </div>
                  <span className="text-xs text-slate-400 shrink-0">
                    {path.stages?.length ?? 0} 阶段 · {path.progress ?? 0}%
                  </span>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
