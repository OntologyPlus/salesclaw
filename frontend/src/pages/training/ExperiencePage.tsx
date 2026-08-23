import { useState } from 'react'
import { Trophy, TrendingUp, Award, Crown, Medal, AlertCircle, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Badge from '@/components/ui/Badge'
import Input from '@/components/ui/Input'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import { experienceAPI } from '@/services/experience'

interface MyPoints {
  total_points: number
  month_points: number
  month_rank?: number
  level?: string
}

interface HistoryItem {
  id: number
  source: string
  points: number
  reason?: string
  created_at?: string
  scenario_title?: string
  score?: number
}

interface LeaderboardItem {
  user_id: number
  user_name: string
  total_points: number
  rank: number
}

export default function ExperiencePage() {
  // 我的积分
  const { data: myData, loading: myLoading, error: myError } = useFetch<MyPoints>(
    () => experienceAPI.myPoints(),
    []
  )

  // 历史记录
  const { data: historyData, loading: historyLoading } = useFetch<{ items: HistoryItem[]; total: number }>(
    () => experienceAPI.myHistory({ page: 1, page_size: 20 }),
    []
  )

  // 月度排行榜
  const today = new Date()
  const defaultMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
  const [yearMonth, setYearMonth] = useState(defaultMonth)
  const { data: leaderboardData, loading: leaderboardLoading, error: leaderboardError } = useFetch<{ items: LeaderboardItem[]; year_month: string }>(
    () => experienceAPI.leaderboard({ year_month: yearMonth }),
    [yearMonth]
  )

  const myRank = myData?.month_rank
  const history = historyData?.items ?? []
  const leaderboard = leaderboardData?.items ?? []

  const sourceMap: Record<string, { label: string; variant: 'default' | 'info' | 'success' | 'warning' }> = {
    train: { label: '训战', variant: 'success' },
    practice: { label: '对练', variant: 'info' },
    exam: { label: '考试', variant: 'warning' },
    ppt: { label: 'PPT 演讲', variant: 'info' },
    course: { label: '课程', variant: 'default' },
  }

  return (
    <div>
      <PageHeader
        title="经验值与排行榜"
        description="训战成绩累积经验值，月度 Top20 荣誉榜"
        breadcrumbs={[{ label: '智能培训' }, { label: '经验值' }]}
        icon={<Trophy className="w-5 h-5" />}
        gradient
      />

      {myError && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{myError.message}</span>
        </div>
      )}

      {/* 我的积分卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {myLoading ? (
          <div className="col-span-4"><Skeleton lines={2} /></div>
        ) : (
          <>
            <StatCard title="累计经验值" value={myData?.total_points ?? 0} icon={<Sparkles className="w-5 h-5" />} color="brand" />
            <StatCard title="本月经验值" value={myData?.month_points ?? 0} icon={<TrendingUp className="w-5 h-5" />} color="emerald" />
            <StatCard title="本月排名" value={myRank ? `#${myRank}` : '—'} icon={<Award className="w-5 h-5" />} color="amber" />
            <StatCard title="当前等级" value={myData?.level ?? '—'} icon={<Crown className="w-5 h-5" />} color="violet" />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：经验值历史 */}
        <div className="lg:col-span-2">
          <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">经验值记录</h2>
            </div>
            {historyLoading ? (
              <div className="p-5"><Skeleton lines={6} /></div>
            ) : history.length === 0 ? (
              <Empty description="暂无经验值记录，完成训战即可累积" />
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-700 max-h-[600px] overflow-y-auto">
                {history.map((h, i) => {
                  const src = sourceMap[h.source] ?? { label: h.source, variant: 'default' as const }
                  return (
                    <motion.div
                      key={h.id ?? i}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.03 }}
                      className="px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                            <Badge variant={src.variant}>{src.label}</Badge>
                            <span className="text-sm text-slate-700 dark:text-slate-300 truncate">
                              {h.scenario_title ?? h.reason ?? '经验值累积'}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-slate-400">
                            {h.score != null && <span>得分 {h.score}</span>}
                            {h.created_at && <span>{new Date(h.created_at).toLocaleString('zh-CN')}</span>}
                          </div>
                        </div>
                        <div className={`text-sm font-bold ${h.points >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                          {h.points >= 0 ? '+' : ''}{h.points}
                        </div>
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* 右侧：月度 Top20 排行榜 */}
        <div className="lg:col-span-1">
          <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">月度 Top20</h2>
                <Trophy className="w-4 h-4 text-amber-500" />
              </div>
              <input
                type="month"
                value={yearMonth}
                onChange={(e) => setYearMonth(e.target.value)}
                max={defaultMonth}
                className="w-full px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 dark:text-slate-100"
              />
            </div>
            {leaderboardLoading ? (
              <div className="p-5"><Skeleton lines={8} /></div>
            ) : leaderboardError ? (
              <div className="p-5 text-sm text-rose-500">加载失败：{leaderboardError.message}</div>
            ) : leaderboard.length === 0 ? (
              <Empty description="本月暂无排行数据" />
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-700 max-h-[600px] overflow-y-auto">
                {leaderboard.map((item, i) => {
                  const rank = item.rank ?? i + 1
                  const rankColors = ['text-amber-500', 'text-slate-400', 'text-orange-700']
                  const rankIcon = rank <= 3 ? <Crown className={`w-4 h-4 ${rankColors[rank - 1]}`} /> : null
                  return (
                    <motion.div
                      key={item.user_id ?? i}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.02 }}
                      className={`px-5 py-2.5 flex items-center gap-3 ${rank <= 3 ? 'bg-gradient-to-r from-amber-50/50 to-transparent dark:from-amber-900/10' : ''}`}
                    >
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                        rank === 1 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' :
                        rank === 2 ? 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300' :
                        rank === 3 ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300' :
                        'bg-slate-50 text-slate-400 dark:bg-slate-900/30'
                      }`}>
                        {rankIcon ?? rank}
                      </div>
                      <span className="flex-1 text-sm text-slate-700 dark:text-slate-300 truncate">{item.user_name ?? `用户 ${item.user_id}`}</span>
                      <span className="text-sm font-semibold text-brand-600 dark:text-brand-400">{item.total_points}</span>
                    </motion.div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
