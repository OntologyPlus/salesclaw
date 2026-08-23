import { useState } from 'react'
import { Lightbulb, Play, RotateCcw } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import { decisionAPI } from '@/services/decision'

interface SimResult {
  scenario: { visit_change: number; training_change: number }
  current: { comprehensive_score: number; behavior_score: number; ability_score: number; performance_score: number }
  simulated: { comprehensive_score: number; behavior_score: number; ability_score: number; performance_score: number }
  delta: { comprehensive_score: number; behavior_score: number; ability_score: number; performance_score: number }
  ai_summary: string
}

export default function SimulationPage() {
  const [visitChange, setVisitChange] = useState(20)
  const [trainingChange, setTrainingChange] = useState(10)
  const [result, setResult] = useState<SimResult | null>(null)
  const [loading, setLoading] = useState(false)

  const runSimulation = async () => {
    setLoading(true)
    try {
      const data = await decisionAPI.simulate(visitChange / 100, trainingChange / 100)
      setResult(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setResult(null)
    setVisitChange(20)
    setTrainingChange(10)
  }

  const chartData = result ? [
    { name: '行为分', current: result.current.behavior_score, simulated: result.simulated.behavior_score },
    { name: '能力分', current: result.current.ability_score, simulated: result.simulated.ability_score },
    { name: '业绩分', current: result.current.performance_score, simulated: result.simulated.performance_score },
    { name: '综合分', current: result.current.comprehensive_score, simulated: result.simulated.comprehensive_score },
  ] : []

  return (
    <div>
      <PageHeader
        title="模拟推演"
        description="What-if 场景模拟：调整拜访与培训投入，预测综合能力分变化"
        breadcrumbs={[{ label: '决策支持', path: '/decision' }, { label: '模拟推演' }]}
        icon={<Lightbulb className="w-5 h-5" />}
      />

      {/* 参数设置 */}
      <div className="mb-6 p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
        <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-4">场景参数</h3>
        <div className="space-y-5">
          {/* 拜访频次 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">拜访频次变化</label>
              <span className={`text-sm font-semibold ${visitChange > 0 ? 'text-emerald-600' : visitChange < 0 ? 'text-rose-600' : 'text-slate-500'}`}>
                {visitChange > 0 ? '+' : ''}{visitChange}%
              </span>
            </div>
            <input
              type="range"
              min={-50}
              max={100}
              step={5}
              value={visitChange}
              onChange={(e) => setVisitChange(Number(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>-50%</span>
              <span>0%</span>
              <span>+100%</span>
            </div>
          </div>

          {/* 培训投入 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">培训投入变化</label>
              <span className={`text-sm font-semibold ${trainingChange > 0 ? 'text-emerald-600' : trainingChange < 0 ? 'text-rose-600' : 'text-slate-500'}`}>
                {trainingChange > 0 ? '+' : ''}{trainingChange}%
              </span>
            </div>
            <input
              type="range"
              min={-50}
              max={100}
              step={5}
              value={trainingChange}
              onChange={(e) => setTrainingChange(Number(e.target.value))}
              className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-violet-600"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>-50%</span>
              <span>0%</span>
              <span>+100%</span>
            </div>
          </div>

          {/* 按钮 */}
          <div className="flex gap-3">
            <button
              onClick={runSimulation}
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-brand-600 text-white font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              <Play className="w-4 h-4" />
              {loading ? '模拟中...' : '运行模拟'}
            </button>
            <button
              onClick={reset}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              重置
            </button>
          </div>
        </div>
      </div>

      {/* 模拟结果 */}
      {result ? (
        <>
          {/* AI 摘要 */}
          <div className={`mb-6 p-5 rounded-2xl text-white ${result.delta.comprehensive_score > 0 ? 'bg-gradient-to-r from-emerald-600 to-teal-500' : result.delta.comprehensive_score < 0 ? 'bg-gradient-to-r from-rose-600 to-orange-500' : 'bg-gradient-to-r from-slate-600 to-slate-500'}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-white/80 text-sm">预期综合分变化</p>
                <p className="text-3xl font-bold mt-1">
                  {result.delta.comprehensive_score > 0 ? '+' : ''}{result.delta.comprehensive_score} 分
                </p>
                <p className="text-white/90 text-sm mt-2">{result.ai_summary}</p>
              </div>
              <div className="text-right">
                <p className="text-white/80 text-sm">当前 → 模拟</p>
                <p className="text-xl font-semibold">
                  {result.current.comprehensive_score} → {result.simulated.comprehensive_score}
                </p>
              </div>
            </div>
          </div>

          {/* 对比柱状图 */}
          <div className="mb-6 p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-4">分数对比</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar dataKey="current" name="当前" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="simulated" name="模拟后" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 详细变化 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ScoreDeltaCard label="行为分" current={result.current.behavior_score} delta={result.delta.behavior_score} />
            <ScoreDeltaCard label="能力分" current={result.current.ability_score} delta={result.delta.ability_score} />
            <ScoreDeltaCard label="业绩分" current={result.current.performance_score} delta={result.delta.performance_score} />
            <ScoreDeltaCard label="综合分" current={result.current.comprehensive_score} delta={result.delta.comprehensive_score} />
          </div>
        </>
      ) : (
        <Empty description="调整参数后点击「运行模拟」查看预期结果" />
      )}
    </div>
  )
}

function ScoreDeltaCard({ label, current, delta }: { label: string; current: number; delta: number }) {
  const isPositive = delta > 0
  const isNegative = delta < 0
  return (
    <div className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-1">{label}</p>
      <p className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{current}</p>
      <p className={`text-sm mt-1 ${isPositive ? 'text-emerald-600' : isNegative ? 'text-rose-600' : 'text-slate-400'}`}>
        {isPositive ? '+' : ''}{delta}
      </p>
    </div>
  )
}
