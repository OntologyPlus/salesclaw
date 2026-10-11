import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  BarChart3, Download, Building2, MessageSquare, Users, Activity, Target,
  CheckCircle2, AlertCircle, ChevronLeft, TrendingUp,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Select from '@/components/ui/Select'
import Tabs from '@/components/ui/Tabs'
import Empty from '@/components/ui/Empty'
import api from '@/services/api'
import { activityAPI } from '@/services/activity'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import type { PageRes } from '@/types/page'

// 活动概要
interface ActivityItem extends Record<string, unknown> {
  id: number
  title?: string
}

// 活动列表响应

// KPI 概要
interface KpiSummary {
  scenario_count?: number
  total_learners?: number
  practice_count?: number
  train_count?: number
  practice_users?: number
  passed_count?: number
  participation_rate?: number
  pass_rate?: number
  pass_score?: number
}

// 部门聚合行
interface DeptRow extends Record<string, unknown> {
  department?: string
  zone_id?: number
  total_sessions?: number
  passed_sessions?: number
  unique_users?: number
  pass_rate?: number
  avg_duration?: number
}

// 场景聚合行
interface ScenarioRow extends Record<string, unknown> {
  scenario_id?: number
  scenario_title?: string
  total_sessions?: number
  unique_users?: number
  valid_users?: number
  pass_rate_by_user?: number
  pass_rate_by_session?: number
}

// 学员聚合行
interface LearnerRow extends Record<string, unknown> {
  user_id?: number
  user_name?: string
  latest_score?: number
  best_score?: number
  is_passed?: boolean
  passed_count?: number
  total_count?: number
}

const dimensionTabs = [
  { key: 'department', label: '按部门' },
  { key: 'scenario', label: '按场景' },
  { key: 'learner', label: '按学员' },
]

export default function ActivityDataPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  // 活动列表（用于选择）
  const { data: activityListData } = useFetch<PageRes<ActivityItem>>(
    () => activityAPI.list({ page: 1, page_size: 100 }),
    []
  )
  const activityOptions = useMemo(() => [
    { label: '请选择活动', value: '' },
    ...(activityListData?.items ?? []).map((a) => ({ label: a.title ?? `活动${a.id}`, value: String(a.id) })),
  ], [activityListData])

  const activeId = id ? Number(id) : null

  const [keyword, setKeyword] = useState('')
  const [dimension, setDimension] = useState('department')
  const [exporting, setExporting] = useState(false)

  // KPI
  const { data: kpi, loading: kpiLoading, error: kpiError } = useFetch<KpiSummary>(
    () => activeId ? activityAPI.analyticsSummary(activeId) : Promise.resolve({} as KpiSummary),
    [activeId]
  )

  // 维度数据
  const { data: dimData, loading: dimLoading, error: dimError, refetch } = useFetch<any[]>(
    () => {
      if (!activeId) return Promise.resolve([])
      if (dimension === 'department') return activityAPI.analyticsDepartment(activeId, keyword || undefined)
      if (dimension === 'scenario') return activityAPI.analyticsScenario(activeId, keyword || undefined)
      return activityAPI.analyticsLearner(activeId, keyword || undefined)
    },
    [activeId, dimension, keyword]
  )

  // 切换维度重置关键字
  useEffect(() => {
    setKeyword('')
  }, [dimension])

  const rows: any[] = Array.isArray(dimData) ? dimData : []

  const handleDownload = async (dim: string) => {
    if (!activeId) {
      toast('请先选择活动', 'warning')
      return
    }
    setExporting(true)
    try {
      const url = activityAPI.analyticsExportUrl(activeId, dim)
      const res = await api.get(url, { responseType: 'blob' })
      const blob = res.data as Blob
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `activity_${activeId}_${dim}.csv`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(link.href)
      toast('导出成功', 'success')
    } catch (e) {
      toast(`导出失败：${(e as Error).message}`, 'error')
    } finally {
      setExporting(false)
    }
  }

  // 各维度列定义
  const deptColumns: Column<DeptRow>[] = [
    { key: 'department', title: '部门', render: (r) => <span className="font-medium text-slate-900 dark:text-slate-100">{r.department ?? '-'}</span> },
    { key: 'total_sessions', title: '总人次', render: (r) => <span>{r.total_sessions ?? 0}</span> },
    { key: 'passed_sessions', title: '达标人次', render: (r) => <span className="text-emerald-600">{r.passed_sessions ?? 0}</span> },
    { key: 'unique_users', title: '参与人数', render: (r) => <span>{r.unique_users ?? 0}</span> },
    { key: 'pass_rate', title: '通过率', render: (r) => <Badge variant={(r.pass_rate ?? 0) >= 60 ? 'success' : 'warning'}>{r.pass_rate ?? 0}%</Badge> },
    { key: 'avg_duration', title: '平均耗时(分)', render: (r) => <span>{r.avg_duration ?? 0}</span> },
  ]
  const scenarioColumns: Column<ScenarioRow>[] = [
    { key: 'scenario_id', title: '场景ID', render: (r) => <span>{r.scenario_id ?? '-'}</span> },
    { key: 'scenario_title', title: '场景名称', render: (r) => <span className="font-medium text-slate-900 dark:text-slate-100">{r.scenario_title ?? '-'}</span> },
    { key: 'total_sessions', title: '参与人次', render: (r) => <span>{r.total_sessions ?? 0}</span> },
    { key: 'unique_users', title: '参与人数', render: (r) => <span>{r.unique_users ?? 0}</span> },
    { key: 'valid_users', title: '达标人数', render: (r) => <span className="text-emerald-600">{r.valid_users ?? 0}</span> },
    { key: 'pass_rate_by_user', title: '通过率(人数)', render: (r) => <Badge variant={(r.pass_rate_by_user ?? 0) >= 60 ? 'success' : 'warning'}>{r.pass_rate_by_user ?? 0}%</Badge> },
  ]
  const learnerColumns: Column<LearnerRow>[] = [
    { key: 'user_id', title: '学员ID', render: (r) => <span>{r.user_id ?? '-'}</span> },
    { key: 'user_name', title: '学员姓名', render: (r) => <span className="font-medium text-slate-900 dark:text-slate-100">{r.user_name ?? '-'}</span> },
    { key: 'latest_score', title: '最新成绩', render: (r) => <span>{r.latest_score ?? '-'}</span> },
    { key: 'best_score', title: '最佳成绩', render: (r) => <span className="text-amber-500">{r.best_score ?? '-'}</span> },
    { key: 'total_count', title: '总次数', render: (r) => <span>{r.total_count ?? 0}</span> },
    { key: 'passed_count', title: '达标次数', render: (r) => <span className="text-emerald-600">{r.passed_count ?? 0}</span> },
    { key: 'is_passed', title: '是否达标', render: (r) => <Badge variant={r.is_passed ? 'success' : 'warning'}>{r.is_passed ? '达标' : '未达标'}</Badge> },
  ]

  const columns = dimension === 'department' ? deptColumns : dimension === 'scenario' ? scenarioColumns : learnerColumns

  const dimIcon = dimension === 'department' ? <Building2 className="w-4 h-4" />
    : dimension === 'scenario' ? <MessageSquare className="w-4 h-4" />
    : <Users className="w-4 h-4" />

  return (
    <div>
      <PageHeader
        title="活动数据看板"
        description="活动训练数据 KPI 概览与多维度分析"
        breadcrumbs={[
          { label: '智能培训', path: '/training/activities' },
          { label: '培训活动', path: '/training/activities' },
          { label: '数据看板' },
        ]}
        icon={<BarChart3 className="w-5 h-5" />}
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate('/training/activities')}>
              <ChevronLeft className="w-4 h-4" />
              返回列表
            </Button>
            <Button
              variant="secondary"
              loading={exporting}
              onClick={() => handleDownload(dimension)}
              disabled={!activeId}
            >
              <Download className="w-4 h-4" />
              导出当前维度
            </Button>
          </>
        }
      />

      {/* 顶部筛选 */}
      <div className="mb-4 flex items-center gap-3 flex-wrap">
        <div className="w-72">
          <Select
            options={activityOptions}
            value={activeId ? String(activeId) : ''}
            onChange={(e) => {
              const v = e.target.value
              navigate(v ? `/training/activities/${v}/data` : '/training/activities', { replace: false })
            }}
          />
        </div>
        {activeId && (
          <span className="text-xs text-slate-400">
            达标分：{kpi?.pass_score ?? 60}
          </span>
        )}
      </div>

      {!activeId ? (
        <Empty description="请先选择一个活动查看数据看板" icon={<BarChart3 className="w-12 h-12" />} />
      ) : (
        <>
          {/* KPI 卡片 */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
            {kpiError ? (
              <div className="col-span-full flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>KPI 加载失败：{kpiError.message}</span>
              </div>
            ) : (
              <>
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                  <StatCard title="练习参与" value={kpiLoading ? '-' : (kpi?.practice_count ?? 0)} icon={<Activity className="w-5 h-5" />} color="blue" />
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
                  <StatCard title="训战参与" value={kpiLoading ? '-' : (kpi?.train_count ?? 0)} icon={<TrendingUp className="w-5 h-5" />} color="violet" />
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
                  <StatCard title="应参与人数" value={kpiLoading ? '-' : (kpi?.total_learners ?? 0)} icon={<Users className="w-5 h-5" />} color="cyan" />
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
                  <StatCard title="参与率" value={kpiLoading ? '-' : `${kpi?.participation_rate ?? 0}%`} icon={<Target className="w-5 h-5" />} color="amber" />
                </motion.div>
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
                  <StatCard title="通过率" value={kpiLoading ? '-' : `${kpi?.pass_rate ?? 0}%`} icon={<CheckCircle2 className="w-5 h-5" />} color="emerald" />
                </motion.div>
              </>
            )}
          </div>

          {/* 维度切换 */}
          <div className="mb-4">
            <Tabs tabs={dimensionTabs} activeKey={dimension} onChange={setDimension} />
          </div>

          {/* 关键字过滤 */}
          <div className="mb-4 flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 text-sm text-slate-500">
              {dimIcon}
              {dimension === 'department' ? '部门名称' : dimension === 'scenario' ? '场景名称' : '学员姓名'}
            </div>
            <div className="flex-1 min-w-[200px] max-w-xs">
              <input
                className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100"
                placeholder={`搜索${dimension === 'department' ? '部门' : dimension === 'scenario' ? '场景' : '学员'}`}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
              />
            </div>
            <Button variant="ghost" size="sm" onClick={refetch}>
              <Download className="w-3.5 h-3.5" />
              刷新
            </Button>
          </div>

          {dimError && (
            <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>加载失败：{dimError.message}</span>
            </div>
          )}

          <DataTable
            columns={columns as Column<any>[]}
            data={rows}
            loading={dimLoading}
            rowKey={dimension === 'scenario' ? 'scenario_id' : dimension === 'learner' ? 'user_id' : 'zone_id'}
          />
        </>
      )}
    </div>
  )
}
