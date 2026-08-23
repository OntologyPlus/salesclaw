import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Sparkles, RefreshCw, AlertCircle } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Skeleton from '@/components/ui/Skeleton'
import SectionCard from '@/components/layout/SectionCard'
import { trainingEffectAPI } from '@/services/trainingEffect'
import { useToast } from '@/hooks/useToast'

/**
 * 培训效果归因 — 单次执行报告
 *
 * 设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §11.2
 */
export default function ExecutionDetailPage() {
  const params = useParams<{ executionId?: string; id?: string }>()
  const execId = Number(params.executionId ?? params.id ?? 0)
  const toast = useToast()
  const [exec, setExec] = useState<any | null>(null)
  const [lag, setLag] = useState<any | null>(null)
  const [ai, setAi] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const [aiLoading, setAiLoading] = useState(false)

  useEffect(() => {
    if (!execId) return
    void (async () => {
      try {
        const [e, l] = await Promise.all([
          trainingEffectAPI.getExecution(execId),
          trainingEffectAPI.lagCurve(execId),
        ])
        setExec(e?.execution_id ? e : e)
        setLag(l)
      } finally {
        setLoading(false)
      }
    })()
  }, [execId])

  const triggerAI = async () => {
    setAiLoading(true)
    try {
      const r = await trainingEffectAPI.evaluate(execId)
      setAi(r)
      if (r?.reasoning_chain_id) {
        toast(`已生成归因报告（reasoning_chain_id=${r.reasoning_chain_id}）`, 'success')
      }
    } catch (e: any) {
      toast(`AI 归因失败：${e?.message ?? e}`, 'error')
    } finally {
      setAiLoading(false)
    }
  }

  if (loading) return <Skeleton lines={6} />

  if (!exec || exec.error) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
      <AlertCircle size={16} className="shrink-0" />
      未找到执行 #{execId}，或您无权查看
    </div>
    )
  }

  const verdictMap: Record<string, { variant: any; cn: string }> = {
    achieved: { variant: 'success', cn: '已达成' },
    partial_achieved: { variant: 'warning', cn: '部分达成' },
    not_achieved: { variant: 'error', cn: '未达成' },
  }
  const verdict = ai?.verdict ? verdictMap[ai.verdict] : null

  return (
    <div className="space-y-6">
      <Link
        to="/training/effect"
        className="inline-flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
      >
        <ArrowLeft size={14} /> 返回总览
      </Link>

      <PageHeader
        title={`归因报告 #${exec.execution_id} — ${exec.title || '-'}`}
        description={`user_id=${exec.user_id} • status=${exec.status} • effectiveness_score=${exec.effectiveness_score ?? '-'}`}
        actions={
          <Button onClick={triggerAI} disabled={aiLoading}>
            <Sparkles size={14} className="mr-1" />
            {aiLoading ? '评估中...' : ai ? '重新 AI 归因' : '触发 AI 归因'}
          </Button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SectionCard title="baseline / target / actual 三组指标">
          <div className="grid grid-cols-3 gap-4 text-xs">
            <MetricsGroup label="baseline（培训前）" data={exec.baseline_metrics || {}} tone="slate" />
            <MetricsGroup label="target（培训宣称）" data={exec.target_metrics || {}} tone="blue" />
            <MetricsGroup label="actual（现状）" data={exec.actual_metrics || {}} tone="emerald" />
          </div>
          <div className="mt-4 px-5 text-xs text-slate-400 dark:text-slate-500">
            * 三组指标对应 TRAINING_EFFECT_METRICS 约定的 5 维画像 + 4 个行为 KPI（9 项）。
          </div>
        </SectionCard>

        <SectionCard title="方法 A — 滞后期效果曲线">
          {!lag || lag.error ? (
            <p className="px-5 py-4 text-sm text-slate-400 dark:text-slate-500">暂无快照数据</p>
          ) : (
            <LagCurveMini lag={lag} />
          )}
          <div className="mt-3 px-5 text-xs text-slate-400 dark:text-slate-500">
            * t0 baseline 为能力 + KPI 同期快照，t0+30/90/180 为滞后窗口重抓。
          </div>
        </SectionCard>
      </div>

      <SectionCard title="方法 C — AI 归因（经编排器 evaluate 意图）">
        {!ai ? (
          <div className="py-6 text-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">尚未生成 AI 归因报告</p>
            <Button className="mt-3" onClick={triggerAI}>
              <Sparkles size={14} className="mr-1" /> 立即生成
            </Button>
          </div>
        ) : (
          <div className="space-y-3 p-5 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant={verdict?.variant || 'default'}>{verdict?.cn || ai.verdict}</Badge>
              {ai.achievement_rate != null && (
                <span className="text-slate-500 dark:text-slate-400">achievement_rate = {(ai.achievement_rate * 100).toFixed(0)}%</span>
              )}
              {ai.confidence != null && (
                <span className="text-slate-500 dark:text-slate-400">confidence = {(ai.confidence * 100).toFixed(0)}%</span>
              )}
              <span className="text-slate-400 dark:text-slate-500">
                source = {ai.source} {ai.trace_id && `• trace=${ai.trace_id.slice(0, 12)}…`}
              </span>
            </div>
            {ai.summary && <p className="leading-relaxed text-slate-700 dark:text-slate-200">{ai.summary}</p>}
            {ai.reasons?.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-slate-600 dark:text-slate-300">
                {ai.reasons.map((r: any, idx: number) => (
                  <li key={idx}>
                    <b className="text-slate-800 dark:text-slate-200">{r.factor}</b> · {r.status} · 贡献度 {(r.contribution * 100).toFixed(0)}% · {r.detail}
                  </li>
                ))}
              </ul>
            )}
            {ai.reasoning_chain_id && (
              <div className="text-xs text-slate-400 dark:text-slate-500">
                reasoning_chain_id = <code>{ai.reasoning_chain_id}</code>
                {ai.provenance?.model_version && (
                  <span> • model = {ai.provenance.model_version}</span>
                )}
              </div>
            )}
          </div>
        )}
      </SectionCard>
    </div>
  )
}

function MetricsGroup({ label, data, tone }: { label: string; data: Record<string, any>; tone: string }) {
  const toneCls = {
    slate: 'bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700',
    blue: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
    emerald: 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800',
  }[tone as string] || 'bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700'

  return (
    <div className={`border ${toneCls} rounded-lg p-2`}>
      <div className="mb-1 text-xs font-medium text-slate-700 dark:text-slate-200">{label}</div>
      <ul className="space-y-0.5">
        {Object.entries(data).slice(0, 9).map(([k, v]) => (
          <li key={k} className="flex justify-between text-[11px]">
            <span className="text-slate-500 dark:text-slate-400">{k}</span>
            <span className="font-medium text-slate-800 dark:text-slate-200">{(v as number)?.toFixed?.(2) ?? v}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function LagCurveMini({ lag }: { lag: any }) {
  if (!lag?.series || lag.series.length < 2) return null
  const points = lag.series as Array<{ t: number; label: string; snapshot: any }>
  // 找 1 个最能体现差异的指标（用 product_knowledge 或 visit_skill 兜底）
  const metric = Object.keys(lag.diffs || {}).find(k => k === 'visit_skill')
    || Object.keys(lag.diffs || {})[0]
  if (!metric) return null

  const series = (lag.diffs?.[metric] || []) as Array<{ t: number; delta: number }>
  const maxAbs = Math.max(1, ...series.map(s => Math.abs(s.delta)))

  return (
    <div className="px-5 py-4">
      <div className="mb-2 text-xs text-slate-500 dark:text-slate-400">
        指标：<span className="font-medium">{metric}</span> · 4 个时间点
      </div>
      <div className="grid grid-cols-4 gap-2">
        {points.map((p) => {
          const s = series.find(x => x.t === p.t)
          const delta = s?.delta ?? 0
          const heightPct = Math.min(100, Math.abs(delta) / maxAbs * 100)
          const isUp = delta >= 0
          return (
            <div key={p.t} className="text-center">
              <div className="flex h-24 items-end justify-center">
                <div
                  className={`w-8 rounded ${isUp ? 'bg-emerald-400 dark:bg-emerald-500' : 'bg-rose-300 dark:bg-rose-500'}`}
                  style={{ height: `${Math.max(8, heightPct)}%` }}
                  title={`${p.label}: delta=${delta.toFixed(2)}`}
                />
              </div>
              <div className="mt-1 text-[10px] text-slate-500 dark:text-slate-400">{p.label}</div>
              <div className={`text-[11px] font-medium ${isUp ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                {delta >= 0 ? '+' : ''}{delta.toFixed(1)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
