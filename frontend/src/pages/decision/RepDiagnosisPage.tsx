import { useParams, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { ArrowLeft, GraduationCap, Target, Zap } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import { decisionAPI } from '@/services/decision'
import { DiagnosisCard } from './DiagnosisCard'
import type { DiagnosisEntity } from '@/types'

const DIM_COLOR: Record<string, string> = {
  合规: '#ef4444', 学术: '#8b5cf6', 拜访: '#3b82f6', 执行: '#f59e0b',
}

// OAG 置信度档位（由短板分派生：短板越低 → 画像越可信 → 档位越高）
function bandOf(weakScore: number) {
  if (weakScore >= 70) return { dot: '#EF4444', text: '低置信', band: 'RED' }
  if (weakScore >= 40) return { dot: '#EAB308', text: '中置信', band: 'YELLOW' }
  return { dot: '#22C55E', text: '高置信', band: 'GREEN' }
}

export default function RepDiagnosisPage() {
  const { repId } = useParams<{ repId: string }>()
  const navigate = useNavigate()
  const id = Number(repId)
  const { data, loading } = useFetch(() => decisionAPI.getLoopRep(id), [id])
  const [busyDim, setBusyDim] = useState<string | null>(null)
  // 代表维度复用统一诊断卡：拉取该代表诊断（含误判排除标记），动作后刷新
  const [diagRefresh, setDiagRefresh] = useState(0)
  const { data: diagData } = useFetch(
    () => decisionAPI.listDiagnoses(undefined, undefined, id),
    [id, diagRefresh],
  )
  const repDiagnoses: DiagnosisEntity[] = diagData || []

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无该代表诊断数据" />

  const band = bandOf(data.weak_score ?? 0)

  async function triggerAction(t: any) {
    setBusyDim(t.dimension)
    try {
      await decisionAPI.confirmLoop(id, t.dimension, {
        reason: t.reason,
        downstream: t.downstream,
        baseline_metrics: t.baseline_metrics,
        target_metrics: t.target_metrics,
      })
    } finally {
      setBusyDim(null)
    }
  }

  return (
    <div>
      <PageHeader
        title={`代表 ${data.rep_id} 诊断归因`}
        description="个人级短板画像 + 培训建议（含验证基线）"
        breadcrumbs={[{ label: '决策支持' }, { label: '诊断闭环' }, { label: `代表 ${data.rep_id}` }]}
        icon={<GraduationCap className="w-5 h-5" />}
        actions={
          <button onClick={() => navigate('/decision/loop')}
            className="inline-flex items-center gap-1 text-sm text-brand-600">
            <ArrowLeft className="w-4 h-4" /> 返回闭环
          </button>
        }
      />

      <div className="mb-4 flex items-center gap-4 text-sm">
        <span className="text-slate-500">短板维度：</span>
        <div className="flex gap-2 flex-wrap">
          {data.weak_dimensions.map((d: string) => (
            <span key={d} className="px-2 py-1 rounded-full text-xs font-medium"
              style={{ background: (DIM_COLOR[d] || '#64748b') + '20', color: DIM_COLOR[d] || '#64748b' }}>{d}</span>
          ))}
        </div>
        {/* OAG 置信度档位角标 */}
        <span className="ml-2 inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium dark:bg-slate-800">
          <span className="inline-flex h-2.5 w-2.5 rounded-full" style={{ background: band.dot }} />
          {band.text}
        </span>
        <span className="ml-2 text-slate-400">告警 {data.alert_count} · 未执行建议 {data.pending_recommendations} · 短板分 {data.weak_score}</span>
      </div>

      {/* 代表维度统一诊断（复用 DiagnosisCard，含误判排除闸标记） */}
      <section className="mb-6">
        <div className="mb-2 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">统一诊断</h3>
          <span className="text-[11px] text-slate-400">含误判排除闸：命中结构性因素（如 VBP 集采/新品导入）的红灯会被降级并标注</span>
        </div>
        {repDiagnoses.length === 0 ? (
          <p className="text-xs text-slate-400">该代表暂无统一诊断记录（可先在「统一诊断」页对该代表执行 AI 诊断）</p>
        ) : (
          <div className="space-y-4">
            {repDiagnoses.map((d) => (
              <DiagnosisCard
                key={d.id}
                diagnosis={d}
                onAction={() => setDiagRefresh((n) => n + 1)}
              />
            ))}
          </div>
        )}
      </section>

      {/* 培训建议卡 */}
      <div className="space-y-4">
        {(data.trainings || []).map((t: any, i: number) => (
          <div key={i} className="p-5 rounded-2xl bg-white border border-slate-200">
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-1 rounded-full text-xs font-semibold"
                  style={{ background: (DIM_COLOR[t.dimension] || '#64748b') + '20', color: DIM_COLOR[t.dimension] || '#64748b' }}>
                  {t.dimension}
                </span>
                <span className="text-sm text-slate-600">{t.reason}</span>
              </div>
              {/* OAG 动作闭环：落地下游动作 */}
              <button
                disabled={busyDim !== null}
                onClick={() => triggerAction(t)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-50 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300 dark:hover:bg-indigo-500/20"
              >
                <Zap className="w-3.5 h-3.5" />
                {busyDim === t.dimension ? '落地下游…' : '可触发动作'}
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1 flex items-center gap-1">
                  <GraduationCap className="w-3 h-3" /> 推荐课程
                </p>
                {t.recommended_courses?.length ? (
                  <ul className="text-xs text-slate-600 space-y-1">
                    {t.recommended_courses.map((c: any) => (
                      <li key={c.id} className="flex items-center justify-between border-b pb-1">
                        <span>{c.title}</span>
                        <span className="text-amber-600">★ {c.avg_rating ?? '-'}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-xs text-slate-400">暂无匹配课程</p>}
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1 flex items-center gap-1">
                  <Target className="w-3 h-3" /> 验证基线（供下游效果追踪）
                </p>
                <pre className="text-xs text-slate-500 bg-slate-50 rounded p-2 overflow-auto">
{JSON.stringify({ baseline: t.baseline_metrics, target: t.target_metrics }, null, 2)}
                </pre>
              </div>
            </div>
            <p className="mt-2 text-xs text-amber-600">{t.downstream}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
