import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, ShieldAlert, ShieldX, Activity, Users, GraduationCap } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import { decisionAPI } from '@/services/decision'

const LIGHT_META: Record<string, { label: string; color: string; icon: any }> = {
  GREEN: { label: '健康', color: '#10b981', icon: ShieldCheck },
  YELLOW: { label: '关注', color: '#f59e0b', icon: Activity },
  RED: { label: '高危', color: '#ef4444', icon: ShieldAlert },
  BLACK: { label: '红线', color: '#111827', icon: ShieldX },
}

const DIM_COLOR: Record<string, string> = {
  合规: '#ef4444', 学术: '#8b5cf6', 拜访: '#3b82f6', 执行: '#f59e0b',
}

export default function LoopPage() {
  const navigate = useNavigate()
  const { data, loading } = useFetch(() => decisionAPI.getLoop('all'), [])

  if (loading) return <div className="p-6 text-slate-500 dark:text-slate-400">加载中...</div>
  if (!data) return <Empty description="暂无诊断闭环数据" />

  const light = LIGHT_META[data.light] || LIGHT_META.GREEN
  const Icon = light.icon
  const dims = data.dimension_distribution || {}
  const dimChart = Object.entries(dims).map(([k, v]) => ({ dim: k, count: v as number }))

  return (
    <div>
      <PageHeader
        title="诊断闭环"
        description="吸收决策闭环 + 诊断体系 · 诊断 → 个人/团队两级归因 → 培训建议"
        breadcrumbs={[{ label: '决策支持' }, { label: '诊断闭环' }]}
        icon={<Activity className="w-5 h-5" />}
      />

      {/* 灯色 + SLA */}
      <div className="mb-6 p-5 rounded-2xl text-white flex items-center gap-4" style={{ background: light.color }}>
        <Icon className="w-10 h-10" />
        <div>
          <p className="text-white/80 text-sm">当前诊断灯</p>
          <p className="text-2xl font-bold">{data.light} · {light.label}</p>
        </div>
        <div className="ml-auto text-right">
          <p className="text-white/80 text-xs">SLA</p>
          <p className="text-lg font-semibold">{data.sla}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 维度分布 */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">短板维度分布</h3>
          {dimChart.length ? (
            <ul className="space-y-2">
              {dimChart.map(d => (
                <li key={d.dim} className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ background: DIM_COLOR[d.dim] || '#64748b' }} />
                  <span className="text-sm text-slate-600 flex-1 dark:text-slate-300">{d.dim}</span>
                  <span className="text-sm font-semibold" style={{ color: DIM_COLOR[d.dim] || '#64748b' }}>{d.count}</span>
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate-500">无显著短板维度。</p>}
        </div>

        {/* 团队短板 */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3 flex items-center gap-1">
            <Users className="w-4 h-4" /> 团队短板上卷
          </h3>
          {data.team_summary?.team_weak_dimensions?.length ? (
            <div className="flex flex-wrap gap-2">
              {data.team_summary.team_weak_dimensions.map((d: string) => (
                <span key={d} className="px-2 py-1 rounded-full text-xs font-medium"
                  style={{ background: (DIM_COLOR[d] || '#64748b') + '20', color: DIM_COLOR[d] || '#64748b' }}>
                  {d}
                </span>
              ))}
            </div>
          ) : <p className="text-sm text-slate-500">团队表现健康。</p>}
          <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">成员数：{data.team_summary?.member_count ?? 0}</p>
        </div>

        {/* 闭环说明 */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3 flex items-center gap-1">
            <GraduationCap className="w-4 h-4" /> 闭环下游出口
          </h3>
          <ul className="text-xs text-slate-500 dark:text-slate-400 space-y-1 list-disc pl-4">
            <li>执行：培训课程/考试（经理确认后下发）</li>
            <li>验证：效果追踪 baseline/target/actual</li>
            <li>判定：闭环复核信号消除矩阵（参考2）</li>
          </ul>
          <p className="mt-2 text-xs text-amber-600">{data.downstream_hint}</p>
        </div>
      </div>

      {/* 个人短板榜 */}
      <div className="mt-6 p-5 rounded-2xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">代表短板榜（点击下钻）</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 dark:text-slate-500 border-b dark:border-slate-800">
                <th className="py-2">代表 ID</th>
                <th>短板维度</th>
                <th>短板分</th>
                <th>告警</th>
                <th>未执行建议</th>
              </tr>
            </thead>
            <tbody>
              {(data.rep_board || []).map((r: any) => (
                <tr key={r.rep_id} className="border-b dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer"
                  onClick={() => navigate(`/decision/loop/rep/${r.rep_id}`)}>
                  <td className="py-2 font-medium text-brand-600">{r.rep_id}</td>
                  <td>
                    <div className="flex gap-1 flex-wrap">
                      {r.weak_dimensions.map((d: string) => (
                        <span key={d} className="px-1.5 py-0.5 rounded text-xs"
                          style={{ background: (DIM_COLOR[d] || '#64748b') + '20', color: DIM_COLOR[d] || '#64748b' }}>{d}</span>
                      ))}
                    </div>
                  </td>
                  <td className="font-semibold">{r.weak_score}</td>
                  <td>{r.alert_count}</td>
                  <td>{r.pending_recommendations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
