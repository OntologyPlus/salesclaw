import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts'
import { Activity, TrendingUp, ArrowRight } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import { ontologyApi } from '@/services/ontology'

const LAYER_LABEL: Record<string, string> = {
  object: '对象层',
  relation: '关系层',
  action: '动作层',
  permission: '权限层',
}

const LEVEL_COLOR: Record<number, string> = {
  1: '#ef4444',
  2: '#f59e0b',
  3: '#3b82f6',
  4: '#8b5cf6',
  5: '#10b981',
}

export default function MaturityPage() {
  const { data, loading } = useFetch(() => ontologyApi.getMaturity(), [])

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无本体成熟度数据" />

  const layers = data.layer_scores || {}
  const radarData = Object.entries(layers).map(([k, v]) => ({
    layer: LAYER_LABEL[k] || k,
    score: v as number,
  }))
  const color = LEVEL_COLOR[data.level] || '#3b82f6'

  return (
    <div>
      <PageHeader
        title="本体成熟度评估"
        description="参考活地图方法论（附录C 5 级模型）· 对象/关系/动作/权限四层自评"
        breadcrumbs={[{ label: '系统管理' }, { label: '本体图谱' }, { label: '成熟度' }]}
        icon={<Activity className="w-5 h-5" />}
      />

      {/* 总分 + 等级 */}
      <div className="mb-6 p-5 rounded-2xl text-white" style={{ background: `linear-gradient(135deg, ${color}, ${color}99)` }}>
        <div className="flex items-center gap-4">
          <TrendingUp className="w-8 h-8" />
          <div>
            <p className="text-white/80 text-sm">成熟度总分</p>
            <p className="text-3xl font-bold">{data.score}</p>
          </div>
          <div className="ml-6">
            <span className="inline-flex items-center px-3 py-1 rounded-full bg-white/20 text-sm font-semibold">
              L{data.level} · {data.level_name}
            </span>
            <p className="text-white/90 text-xs mt-1">{data.level_desc}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 四层雷达 */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">四层成熟度雷达</h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="layer" />
              <PolarRadiusAxis domain={[0, 100]} />
              <Radar dataKey="score" stroke={color} fill={color} fillOpacity={0.4} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* 升级路径 */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">升级路径</h3>
          {data.upgrade_path?.length ? (
            <ul className="space-y-2">
              {data.upgrade_path.map((p: string, i: number) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                  <ArrowRight className="w-4 h-4 mt-0.5 text-brand-500 shrink-0" />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">已具备良好成熟度基线。</p>
          )}
          {data.weak_layers?.length > 0 && (
            <p className="mt-3 text-xs text-amber-600">
              弱层：{data.weak_layers.map((w: string) => LAYER_LABEL[w] || w).join('、')}
            </p>
          )}
        </div>
      </div>

      {/* 20 题问卷明细 */}
      <div className="mt-6 p-5 rounded-2xl bg-white border border-slate-200">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">评估问卷明细（四层 × 5 题）</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(data.questionnaire || {}).map(([layer, qs]) => (
            <div key={layer}>
              <p className="text-xs font-medium text-slate-500 mb-1">
                {LAYER_LABEL[layer] || layer} · 得分 {layers[layer]}
              </p>
              <ul className="text-xs text-slate-600 list-disc pl-4 space-y-0.5">
                {(qs as string[]).map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
