import { useFetch } from "../../hooks/useFetch"
import { decisionAPI } from "../../services/decision"

interface ReasoningStep {
  step: string
  detail?: string
  role?: string
}

interface ReasoningChain {
  id: number
  title?: string
  steps?: ReasoningStep[]
  model_version?: string
}

export function ReasoningTimeline({
  chainId,
  compact = false,
}: {
  chainId: number | null
  compact?: boolean
}) {
  const { data, loading } = useFetch<ReasoningChain | null>(
    () => (chainId ? decisionAPI.getReasoningChain(chainId) : Promise.resolve(null)),
    [chainId],
  )

  if (!chainId) return null
  if (loading) {
    return <div className="mt-3 text-[11px] text-slate-500 dark:text-slate-400">加载推理链…</div>
  }
  const steps = data?.steps ?? []
  if (steps.length === 0) {
    return <div className="mt-3 text-[11px] text-slate-500 dark:text-slate-400">该推理链暂无步骤记录</div>
  }

  return (
    <div className={`mt-3 ${compact ? "" : "border-t border-slate-200 pt-3 dark:border-slate-800"}`}>
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        推理链 #{chainId}
      </div>
      <ol className="space-y-1.5">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-2 text-[11px] text-slate-600 dark:text-slate-300">
            <span className="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-cyan-500/15 text-[9px] text-cyan-600 dark:bg-cyan-500/20 dark:text-cyan-200">
              {i + 1}
            </span>
            <span>
              <span className="font-medium text-slate-900 dark:text-slate-100">{s.step}</span>
              {s.detail ? <span className="text-slate-500 dark:text-slate-400">：{s.detail}</span> : null}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default ReasoningTimeline
