import { Link } from 'react-router-dom'
import {
  GraduationCap, BookOpen, FileText, Route, Award, UserCheck,
  BarChart3, Sparkles, AlertCircle, Clock, Star, BadgeCheck,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Badge from '@/components/ui/Badge'
import PageGrid from '@/components/layout/PageGrid'
import SectionCard from '@/components/layout/SectionCard'
import DomainNavGrid from '@/components/layout/DomainNavGrid'
import { getNavItemsByPrefixes } from '@/config/navConfig'
import ListSection from '@/components/layout/ListSection'
import AIInsightBlock from '@/components/ai/AIInsightBlock'
import AIInsightPanel from '@/components/ai/AIInsightPanel'
import { useFetch } from '@/hooks/useFetch'
import { trainingAPI } from '@/services/training'
import type { PageRes, StatusMap } from '@/types/page'

interface TrainingOverview {
  courses_count?: number
  enrolled_count?: number
  completed_count?: number
  avg_progress?: number | string
  exam_pass_rate?: number | string
  credits?: number
  certificates_count?: number
  paths_count?: number
}

interface CourseItem extends Record<string, unknown> {
  id: number | string
  title?: string
  difficulty?: string
  duration_minutes?: number
  enroll_count?: number
  avg_rating?: number
}

interface PathItem extends Record<string, unknown> {
  id: number | string
  title?: string
  description?: string
  target_role?: string
  total_credits?: number
}

const difficultyMap: StatusMap = {
  easy: { label: '入门', variant: 'success' },
  medium: { label: '中级', variant: 'warning' },
  hard: { label: '高级', variant: 'error' },
}

const entries = [
  { path: '/training/onboarding', label: '对话式上岗备案', desc: '培训-考核-承诺闭环', icon: <BadgeCheck className="w-5 h-5" />, color: 'emerald' },
  { path: '/training/courses', label: '课程中心', desc: '浏览与选课', icon: <BookOpen className="w-5 h-5" />, color: 'brand' },
  { path: '/training/exams', label: '考试中心', desc: '参加考试测评', icon: <FileText className="w-5 h-5" />, color: 'blue' },
  { path: '/training/paths', label: '学习路径', desc: '体系化成长', icon: <Route className="w-5 h-5" />, color: 'emerald' },
  { path: '/training/practice', label: '场景演练', desc: 'AI 对练', icon: <Sparkles className="w-5 h-5" />, color: 'amber' },
  { path: '/training/my-learning', label: '我的学习', desc: '进度跟踪', icon: <UserCheck className="w-5 h-5" />, color: 'cyan' },
  { path: '/training/certificates', label: '我的证书', desc: '能力认证', icon: <Award className="w-5 h-5" />, color: 'pink' },
] as const

export default function TrainingOverviewPage() {
  const { data: overview, loading: ovLoading, error: ovError } = useFetch<TrainingOverview>(
    () => trainingAPI.getOverview(),
    []
  )
  const { data: coursesRes, loading: coursesLoading } = useFetch<PageRes<CourseItem>>(
    () => trainingAPI.listCourses({ page: 1, page_size: 3 }),
    []
  )
  const { data: pathsRes, loading: pathsLoading } = useFetch<PageRes<PathItem>>(
    () => trainingAPI.listPaths({ page: 1 }),
    []
  )

  const courses = coursesRes?.items ?? []
  const paths = pathsRes?.items ?? []

  const stats = [
    { title: '课程总数', value: overview?.courses_count ?? '-', icon: <BookOpen className="w-5 h-5" />, color: 'brand' as const, trend: 6 },
    { title: '已选课程', value: overview?.enrolled_count ?? '-', icon: <GraduationCap className="w-5 h-5" />, color: 'blue' as const, trend: 10 },
    { title: '已完成', value: overview?.completed_count ?? '-', icon: <UserCheck className="w-5 h-5" />, color: 'emerald' as const, trend: 8 },
    { title: '平均进度', value: overview?.avg_progress ?? '-', icon: <BarChart3 className="w-5 h-5" />, color: 'cyan' as const, trend: 4 },
    { title: '考试通过率', value: overview?.exam_pass_rate ?? '-', icon: <FileText className="w-5 h-5" />, color: 'amber' as const, trend: 2 },
    { title: '证书数', value: overview?.certificates_count ?? '-', icon: <Award className="w-5 h-5" />, color: 'pink' as const, trend: 3 },
  ]

  return (
    <div>
      <PageHeader
        title="培训总览"
        description="智能培训全域数据概览与能力提升"
        breadcrumbs={[{ label: '学习成长' }, { label: '培训总览' }]}
        icon={<GraduationCap className="w-5 h-5" />}
      />

      <PageGrid loading={ovLoading} skeletonCount={6}>
        {stats.map((stat) => (
          <StatCard key={stat.title} {...stat} />
        ))}
      </PageGrid>

      {ovError && (
        <div className="mt-6 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载概览数据失败：{ovError.message}</span>
        </div>
      )}

      {/* 快捷入口 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-6">
        {entries.map((e) => (
          <Link
            key={e.path}
            to={e.path}
            className="block p-4 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark hover:border-brand-300 hover:shadow-md transition-all group"
          >
            <div className={`flex items-center justify-center w-10 h-10 rounded-xl mb-3 ${
              e.color === 'brand' ? 'bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400'
              : e.color === 'blue' ? 'bg-sky-100 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300'
              : e.color === 'emerald' ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400'
              : e.color === 'amber' ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400'
              : e.color === 'cyan' ? 'bg-cyan-100 text-cyan-600 dark:bg-cyan-900/40 dark:text-cyan-300'
              : 'bg-pink-100 text-pink-600 dark:bg-pink-900/40 dark:text-pink-300'
            }`}>
              {e.icon}
            </div>
            <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{e.label}</p>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{e.desc}</p>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <SectionCard title="推荐课程" icon={<BookOpen className="w-4 h-4" />} viewAllTo="/training/courses">
          <ListSection
            items={courses}
            loading={coursesLoading}
            emptyText="暂无推荐课程"
            skeletonRows={3}
            renderRow={(course) => {
              const diff = difficultyMap[course.difficulty ?? 'medium'] ?? difficultyMap.medium
              return (
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                        {course.title ?? '-'}
                      </span>
                      <Badge variant={diff.variant}>{diff.label}</Badge>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {course.duration_minutes ?? 0} 分钟
                      </span>
                      <span className="flex items-center gap-1">
                        <Star className="w-3 h-3 text-amber-400" /> {course.avg_rating ?? '-'}
                      </span>
                      <span>{course.enroll_count ?? 0} 人学习</span>
                    </div>
                  </div>
                </div>
              )
            }}
          />
        </SectionCard>

        <SectionCard title="学习路径" icon={<Route className="w-4 h-4" />} viewAllTo="/training/paths">
          <ListSection
            items={paths}
            loading={pathsLoading}
            emptyText="暂无学习路径"
            skeletonRows={3}
            renderRow={(path) => (
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                    {path.title ?? '-'}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 truncate">
                    {path.target_role ? `目标角色：${path.target_role}` : (path.description ?? '体系化成长路径')}
                  </p>
                </div>
                <Badge variant="info">{path.total_credits ?? 0} 学分</Badge>
              </div>
            )}
          />
        </SectionCard>
      </div>

      <DomainNavGrid
        className="mt-6"
        items={getNavItemsByPrefixes(['/training'], { excludeExact: ['/training'] })}
      />

      {/* AI 学习建议（品牌特色卡片） */}
      <SectionCard title="AI 学习建议" icon={<Sparkles className="w-4 h-4" />} viewAllTo="/training/practice" className="mt-6">
        <div className="p-5">
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            {overview
              ? `当前平均进度 ${overview.avg_progress ?? 0}%，已获得 ${overview.credits ?? 0} 学分、${overview.certificates_count ?? 0} 张证书。建议结合考试通过率（${overview.exam_pass_rate ?? 0}%）针对性复习薄弱知识点，并参与场景演练提升实战能力。`
              : '加载建议中...'}
          </p>
        </div>
      </SectionCard>

      <div className="mt-6">
        <AIInsightBlock title="AI 培训洞察">
          <AIInsightPanel domain="training" title="AI 培训洞察" />
        </AIInsightBlock>
      </div>
    </div>
  )
}
