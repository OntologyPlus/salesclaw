import type { ProvenanceInfo } from "../../types"

export function ProvenanceBadge({ provenance }: { provenance: ProvenanceInfo | null }) {
  if (!provenance?.model_version) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-700/50 dark:text-slate-300">
        模型 - 
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-[10px] text-violet-600 dark:bg-violet-500/15 dark:text-violet-200">
      {provenance.model_version}
      {provenance.run_id ? ` · #${provenance.run_id}` : ""}
    </span>
  )
}

export default ProvenanceBadge
