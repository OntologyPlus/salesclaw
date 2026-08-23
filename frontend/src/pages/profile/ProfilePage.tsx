import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts'
import {
  Target, TrendingUp, GraduationCap, Award, AlertTriangle,
  CalendarCheck, FileText, BookOpen, ArrowRight,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import useAuthStore from '@/stores/auth'
import { useFetch } from '@/hooks/useFetch'
import { profileAPI } from '@/services/profile'
import Skeleton from '@/components/ui/Skeleton'

// 综合能力评分数据
interface ScoreData {
  comprehensive_score: number
  level: string
  behavior_score: number
  ability_score: number
  performance_score: number
  behavior_details: {
    visit_completion: number
    coverage_new: number
    points_score: number
    feedback_quality: number
    actual_visits: number
    target_total: number
    total_points: number
    feedbacks_count: number
  }
  ability_details: {
    course_completion: number
    avg_exam: number
    avg_practice: number
    credits_score: number
    enrolled_count: number
    completed_count: number
    exam_count: number
    practice_count: number
    credits: number
  }
  performance_details: {
    sales_completion: number
    growth_rate: number
    customer_dev: number
    new_doctors: number
  }
}

// 雷达图维度
interface RadarDimension {
  name: string
  value: number
  full_mark: number
}

// 推荐课程
interface Recommendation {
  type: string
  id: number
  title: string
  category?: string
  difficulty?: string
  duration_minutes?: number
  reason: string
  priority: string
}

// 薄弱点
interface Weakness {
  dimension: string
  value: number
  suggestion: string
}

// 学习需求数据
interface LearningNeedsData {
  recommendations: Recommendation[]
  objections: Array<{ keyword: string; count: number }>
  weaknesses: Weakness[]
}

// 全息画像中的活动项
interface ActivityItem {
  type: string
  title: string
  date?: string
}

export default function ProfilePage() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)

  const { data: score, loading: scoreLoading } = useFetch<ScoreData>(
    () => profileAPI.getScore(),
    []
  )
  const { data: radar, loading: radarLoading } = useFetch<{ dimensions: RadarDimension[] }>(
    () => profileAPI.getRadar(),
    []
  )
  const { data: learningNeeds, loading: needsLoading } = useFetch<LearningNeedsData>(
    () => profileAPI.getLearningNeeds(),
    []
  )
  const { data: fullProfile } = useFetch<{ activities: ActivityItem[] }>(
    () => profileAPI.getFullProfile(),
    []
  )

  // 等级颜色
  const levelColor = (level: string) => {
    if (level === '卓越') return 'from-violet-500 to-purple-500'
    if (level === '优秀') return 'from-emerald-500 to-teal-500'
    if (level === '良好') return 'from-brand-500 to-blue-500'
    if (level === '合格') return 'from-amber-500 to-orange-500'
    return 'from-slate-400 to-slate-500'
  }

  const activities = fullProfile?.activities ?? []

  // 活动图标
  const activityIcon = (type: string) => {
    if (type === 'visit') return <CalendarCheck className="w-4 h-4 text-brand-600" />
    if (type === 'course_completed') return <GraduationCap className="w-4 h-4 text-emerald-600" />
    if (type === 'exam_submitted') return <Award className="w-4 h-4 text-amber-600" />
    return <FileText className="w-4 h-4 text-slate-400" />
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-white">
          <Target className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            我的画像
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {user?.display_name || user?.username || 'User'} 的综合能力全息视图
          </p>
        </div>
      </div>

      {/* 综合能力分 + 三维分项 */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* 综合分大卡片 */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="lg:col-span-1 rounded-2xl p-6 bg-gradient-to-br from-brand-600 via-brand-500 to-violet-500 text-white relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.2),transparent_60%)]" />
          <div className="relative">
            <p className="text-sm text-white/80">综合能力分</p>
            {scoreLoading ? (
              <div className="mt-2"><Skeleton lines={2} /></div>
            ) : (
              <>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-5xl font-bold">
                    {score?.comprehensive_score ?? '-'}
                  </span>
                  <span className="text-sm text-white/70">/ 100</span>
                </div>
                <div className={`mt-3 inline-flex items-center gap-1 px-3 py-1 rounded-full bg-white/20 backdrop-blur-sm text-sm font-medium`}>
                  <Award className="w-3.5 h-3.5" />
                  {score?.level ?? '-'}
                </div>
                <p className="mt-4 text-xs text-white/70">
                  行为×0.4 + 能力×0.4 + 业绩×0.2
                </p>
              </>
            )}
          </div>
        </motion.div>

        {/* 三维分项 */}
        <div className="lg:col-span-3 grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            {
              name: '行为分',
              value: score?.behavior_score,
              icon: <CalendarCheck className="w-5 h-5" />,
              color: 'brand',
              details: score?.behavior_details,
              detailItems: [
                { label: '拜访完成率', value: `${score?.behavior_details?.visit_completion ?? 0}%` },
                { label: '覆盖新增', value: `${score?.behavior_details?.coverage_new ?? 0}%` },
                { label: '积分', value: score?.behavior_details?.total_points ?? 0 },
                { label: '反馈质量', value: `${score?.behavior_details?.feedback_quality ?? 0}%` },
              ],
            },
            {
              name: '能力分',
              value: score?.ability_score,
              icon: <GraduationCap className="w-5 h-5" />,
              color: 'emerald',
              details: score?.ability_details,
              detailItems: [
                { label: '课程完成率', value: `${score?.ability_details?.course_completion ?? 0}%` },
                { label: '考试平均分', value: score?.ability_details?.avg_exam ?? 0 },
                { label: '演练评分', value: score?.ability_details?.avg_practice ?? 0 },
                { label: '学分', value: score?.ability_details?.credits ?? 0 },
              ],
            },
            {
              name: '业绩分',
              value: score?.performance_score,
              icon: <TrendingUp className="w-5 h-5" />,
              color: 'amber',
              details: score?.performance_details,
              detailItems: [
                { label: '销售完成率', value: `${score?.performance_details?.sales_completion ?? 0}%` },
                { label: '增长率', value: `${score?.performance_details?.growth_rate ?? 0}%` },
                { label: '客户开发', value: `${score?.performance_details?.customer_dev ?? 0}%` },
                { label: '新增客户', value: score?.performance_details?.new_doctors ?? 0 },
              ],
            },
          ].map((dim, i) => (
            <motion.div
              key={dim.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="rounded-2xl p-5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`p-1.5 rounded-lg bg-${dim.color}-100 text-${dim.color}-600 dark:bg-${dim.color}-900/30 dark:text-${dim.color}-300`}>
                    {dim.icon}
                  </span>
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{dim.name}</span>
                </div>
                <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {dim.value ?? '-'}
                </span>
              </div>
              <div className="space-y-1.5">
                {dim.detailItems.map((item) => (
                  <div key={item.label} className="flex items-center justify-between text-xs">
                    <span className="text-slate-500 dark:text-slate-400">{item.label}</span>
                    <span className="font-medium text-slate-700 dark:text-slate-300">{item.value}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* 雷达图 + 能力诊断 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 雷达图 */}
        <div className="rounded-2xl p-5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-4">
            能力雷达图
          </h2>
          {radarLoading ? (
            <div className="h-72"><Skeleton lines={6} /></div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={radar?.dimensions ?? []}>
                <PolarGrid stroke="#cbd5e1" />
                <PolarAngleAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} />
                <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <Radar
                  name="能力"
                  dataKey="value"
                  stroke="#6366f1"
                  fill="#6366f1"
                  fillOpacity={0.5}
                />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 能力诊断 */}
        <div className="rounded-2xl p-5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-4">
            能力诊断
          </h2>
          {needsLoading ? (
            <div><Skeleton lines={5} /></div>
          ) : (
            <div className="space-y-4">
              {/* 薄弱点 */}
              <div>
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
                  薄弱维度
                </p>
                {learningNeeds?.weaknesses && learningNeeds.weaknesses.length > 0 ? (
                  <div className="space-y-2">
                    {learningNeeds.weaknesses.map((w, i) => (
                      <div key={i} className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                        <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                              {w.dimension}
                            </span>
                            <span className="text-sm font-bold text-amber-600">{w.value}</span>
                          </div>
                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            {w.suggestion}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 dark:text-slate-400 p-3 text-center bg-emerald-50 dark:bg-emerald-900/20 rounded-lg border border-emerald-200 dark:border-emerald-800">
                    各维度均达标，继续保持！
                  </p>
                )}
              </div>

              {/* 异议关键词 */}
              {learningNeeds?.objections && learningNeeds.objections.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
                    客户高频异议
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {learningNeeds.objections.map((o, i) => (
                      <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-700 text-xs text-slate-700 dark:text-slate-300">
                        {o.keyword}
                        <span className="text-slate-400">×{o.count}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 推荐课程 */}
      <div className="rounded-2xl p-5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            推荐课程
          </h2>
          <Link to="/training/courses" className="text-sm text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1">
            查看全部 <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        {needsLoading ? (
          <div><Skeleton lines={4} /></div>
        ) : learningNeeds?.recommendations && learningNeeds.recommendations.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {learningNeeds.recommendations.map((rec) => (
              <Link
                key={rec.id}
                to={`/training/courses`}
                className="block p-4 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                    <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      {rec.title}
                    </span>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                    rec.priority === 'high'
                      ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                  }`}>
                    {rec.priority === 'high' ? '高优先' : '中优先'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                  {rec.reason}
                </p>
                <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                  {rec.category && <span>{rec.category}</span>}
                  {rec.difficulty && <span>{rec.difficulty}</span>}
                  {rec.duration_minutes && <span>{rec.duration_minutes} 分钟</span>}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-6">
            暂无推荐课程
          </p>
        )}
      </div>

      {/* 近期活动 */}
      <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            近期活动（销售 + 培训）
          </h2>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-700">
          {activities.length === 0 ? (
            <p className="p-5 text-sm text-slate-500 dark:text-slate-400 text-center">暂无活动</p>
          ) : (
            activities.slice(0, 10).map((act, i) => (
              <div
                key={i}
                className="flex items-start gap-3 px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
              >
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-700 shrink-0">
                  {activityIcon(act.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                    {act.title}
                  </p>
                </div>
                {act.date && (
                  <span className="text-xs text-slate-400 shrink-0">{act.date}</span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
