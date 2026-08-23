import type { ProvenanceInfo } from "../../types"

export function SourceBadge({ provenance }: { provenance: ProvenanceInfo | null }) {
  if (!provenance) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-700/50 dark:text-slate-300">
        来源未知
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-cyan-50 px-2 py-0.5 text-[10px] text-cyan-600 dark:bg-cyan-500/15 dark:text-cyan-200">
      {provenance.agent ?? "AI"} · {provenance.mode ?? "auto"}
    </span>
  )
}

export default SourceBadge
