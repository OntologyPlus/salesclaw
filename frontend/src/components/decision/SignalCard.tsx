import { useState } from "react"
import { AlertTriangle, CheckCircle2, Trash2 } from "lucide-react"
import { decisionAPI } from "../../services/decision"
import type { SignalEntity } from "../../types"

const severityColor: Record<string, string> = {
  high: "#EF4444",
  medium: "#F59E0B",
  low: "#22C55E",
}

export function SignalCard({ signal, onCleared }: { signal: SignalEntity; onCleared: (id: number) => void }) {
  const [busy, setBusy] = useState(false)
  const color = severityColor[signal.severity] || "#94A3B8"

  async function handleClear() {
    setBusy(true)
    try {
      await decisionAPI.clearSignal(signal.id)
      onCleared(signal.id)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="rounded-xl border border-slate-200 bg-white p-3 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800/60"
      style={{ borderLeft: `3px solid ${signal.cleared ? "#22C55E" : color}` } as React.CSSProperties}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {signal.cleared ? (
            <CheckCircle2 size={16} className="text-green-400" />
          ) : (
            <AlertTriangle size={16} style={{ color }} />
          )}
          <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{signal.name}</span>
        </div>
        <span
          className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase"
          style={{ background: `${color}22`, color }}
        >
          {signal.severity}
        </span>
      </div>
      <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{signal.category}</div>
      {signal.clear_condition && (
        <div className="mt-2 text-[11px] leading-relaxed text-slate-500">
          消除条件：{signal.clear_condition}
        </div>
      )}
      {!signal.cleared && (
        <button
          onClick={handleClear}
          disabled={busy}
          className="mt-2 inline-flex items-center gap-1 rounded-lg bg-cyan-50 px-2.5 py-1 text-[11px] font-medium text-cyan-700 transition hover:bg-cyan-100 disabled:opacity-50 dark:bg-cyan-500/15 dark:text-cyan-200 dark:hover:bg-cyan-500/25"
        >
          <Trash2 size={12} /> {busy ? "消除中…" : "消除信号"}
        </button>
      )}
    </div>
  )
}
