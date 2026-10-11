import { useState } from 'react'
import { motion } from 'framer-motion'
import { Award, Activity, Zap, TrendingUp, AlertCircle } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import StatCard from '@/components/data/StatCard'
import DataTable, { type Column } from '@/components/data/DataTable'
import Tabs from '@/components/ui/Tabs'
import Badge from '@/components/ui/Badge'
import Skeleton from '@/components/ui/Skeleton'
import { useFetch } from '@/hooks/useFetch'
import { salesAPI } from '@/services/sales'
import type { PageRes } from '@/types/page'

// 积分汇总（后端字段：behavior_points / instruction_points / total_points）
interface ScoringSummary {
  behavior_points?: number
  instruction_points?: number
  total_points?: number
  behavior_record_count?: number
  instruction_record_count?: number
}

// 积分规则（后端返回数组，字段：points / action_code）
interface ScoringRule {
  id?: number | string
  name?: string
  action_code?: string
  points?: number
  description?: string
  is_active?: number
}

// 积分记录（后端字段：occurred_at / points / record_id）
interface ScoreRecord extends Record<string, unknown> {
  id: number | string
  occurred_at?: string
  rule_name?: string
  rule_id?: number
  record_id?: number
  points?: number
}

// 分页响应

export default function ScoringPage() {
  const [tab, setTab] = useState('behavior')
  const [page, setPage] = useState(1)
  const pageSize = 10

  // 汇总
  const { data: summary, loading: sumLoading } = useFetch<ScoringSummary>(
    () => salesAPI.getScoringSummary(),
    []
  )
  // 规则（后端返回数组，当前仅有行为积分规则）
  const { data: rules, loading: rulesLoading } = useFetch<ScoringRule[]>(
    () => salesAPI.getScoringRules(),
    []
  )
  // 记录
  const { data: recordsRes, loading: recLoading, error } = useFetch<PageRes<ScoreRecord>>(
    () => salesAPI.getScoringRecords({ page, page_size: pageSize }),
    [page]
  )

  // 当前仅有行为积分规则，指令积分规则待后端补充
  const currentRules = tab === 'behavior' ? (rules ?? []) : []

  const records = recordsRes?.items ?? []
  const total = recordsRes?.total ?? 0

  const stats = [
    { title: '行为积分', value: summary?.behavior_points ?? '-', icon: <Activity className="w-5 h-5" />, color: 'brand' as const, trend: 12 },
    { title: '指令积分', value: summary?.instruction_points ?? '-', icon: <Zap className="w-5 h-5" />, color: 'amber' as const, trend: 8 },
    { title: '总积分', value: summary?.total_points ?? '-', icon: <Award className="w-5 h-5" />, color: 'emerald' as const, trend: 10 },
  ]

  const recordColumns: Column<ScoreRecord>[] = [
    { key: 'occurred_at', title: '时间', render: (r) => <span className="text-slate-500">{r.occurred_at ?? '-'}</span> },
    { key: 'rule_name', title: '规则', render: (r) => <span className="font-medium text-slate-900 dark:text-slate-100">{r.rule_name ?? '-'}</span> },
    {
      key: 'points', title: '积分',
      render: (r) => {
        const v = r.points ?? 0
        return <Badge variant={v >= 0 ? 'success' : 'error'}>{v >= 0 ? '+' : ''}{v}</Badge>
      },
    },
    { key: 'record_id', title: '关联记录', render: (r) => <span className="text-slate-500">#{r.record_id ?? '-'}</span> },
  ]

  const ruleTabs = [
    { key: 'behavior', label: '行为积分' },
    { key: 'directive', label: '指令积分' },
  ]

  return (
    <div>
      <PageHeader
        title="积分管理"
        description="销售积分、排名与激励规则管理"
        breadcrumbs={[{ label: '销售执行' }, { label: '积分管理' }]}
        icon={<Award className="w-5 h-5" />}
        actions={<AIActionButton label="AI积分建议" prompt="分析我的积分情况，推荐可冲刺的积分项" variant="ghost" size="sm" />}
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {stats.map((stat, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            {sumLoading ? (
              <div className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                <Skeleton lines={2} />
              </div>
            ) : (
              <StatCard {...stat} />
            )}
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* 积分规则 */}
        <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="px-5 pt-4">
            <Tabs tabs={ruleTabs} activeKey={tab} onChange={setTab} />
          </div>
          <div className="p-5">
            {rulesLoading ? (
              <Skeleton lines={4} />
            ) : currentRules.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-500">暂无规则</p>
            ) : (
              <div className="space-y-2">
                {currentRules.map((rule, i) => (
                  <motion.div
                    key={rule.id ?? i}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="flex items-center justify-between gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{rule.name ?? '-'}</p>
                      {rule.description && (
                        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{rule.description}</p>
                      )}
                    </div>
                    <Badge variant="info">{rule.points ?? 0} 分</Badge>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 积分趋势卡片 */}
        <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">积分概览</h2>
            <TrendingUp className="w-4 h-4 text-slate-400" />
          </div>
          <div className="p-5 space-y-4">
            <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20">
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">行为记录数</p>
                <p className="mt-1 text-2xl font-semibold text-brand-600 dark:text-brand-400">
                  {summary?.behavior_record_count ?? 0}
                </p>
              </div>
              <Award className="w-8 h-8 text-brand-500" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-500 dark:text-slate-400">行为积分</p>
                <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{summary?.behavior_points ?? '-'}</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                <p className="text-xs text-slate-500 dark:text-slate-400">指令积分</p>
                <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{summary?.instruction_points ?? '-'}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 积分记录 */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}
      <DataTable<ScoreRecord>
        columns={recordColumns}
        data={records}
        loading={recLoading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
      />
    </div>
  )
}
