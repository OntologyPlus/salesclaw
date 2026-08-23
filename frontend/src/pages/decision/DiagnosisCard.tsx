import { useState } from "react"
import type { DiagnosisEntity } from "../../types"
import { SourceBadge } from "../../components/decision/SourceBadge"
import { ProvenanceBadge } from "../../components/decision/ProvenanceBadge"
import { ReasoningTimeline } from "../../components/decision/ReasoningTimeline"
import { decisionAPI as decision } from "../../services/decision"

const levelColor: Record<string, string> = {
  RED: "#EF4444",
  YELLOW: "#F59E0B",
  GREEN: "#22C55E",
}

// OAG 置信度档位 🟢/🟡/🔴 配色（对齐方案）
const bandMeta: Record<string, { dot: string; text: string }> = {
  GREEN: { dot: "#22C55E", text: "高置信" },
  YELLOW: { dot: "#EAB308", text: "中置信" },
  RED: { dot: "#EF4444", text: "低置信" },
}

const statusText: Record<string, string> = {
  pending: "待处理",
  confirmed: "已确认",
  in_progress: "处理中",
  resolved: "已解决",
  closed: "已关闭",
  draft: "草稿",
}

const riskColor: Record<string, string> = {
  L1: "#22C55E",
  L2: "#EAB308",
  L3: "#FB923C",
  L4: "#EF4444",
}

export function DiagnosisCard({
  diagnosis,
  onAction,
}: {
  diagnosis: DiagnosisEntity
  onAction?: () => void
}) {
  const [showDetail, setShowDetail] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const band = diagnosis.confidence_band
    ? bandMeta[diagnosis.confidence_band]
    : null
  const vd = diagnosis.validation_detail
  // 误判排除闸：命中排除信号时展示（红/黄灯受结构性因素驱动，非代表不力）
  const excluded = diagnosis.excluded === 1 && diagnosis.excluded_reason

  const checks: { key: string; label: string; ok?: boolean | null }[] = [
    { key: "numeric", label: "数值一致性", ok: vd?.numeric_ok },
    { key: "relation", label: "关系存在性", ok: vd?.relation_ok },
    { key: "temporal", label: "时间逻辑", ok: vd?.temporal_ok },
    { key: "causal", label: "因果链完整", ok: vd?.causal_ok },
    { key: "business", label: "业务规则合规", ok: vd?.business_rule_ok },
  ]

  function checkIcon(ok?: boolean | null) {
    if (ok === null || ok === undefined)
      return <span className="text-slate-400">—</span>
    return ok ? (
      <span className="text-emerald-500">✓</span>
    ) : (
      <span className="text-rose-500">⚠</span>
    )
  }

  async function runAction(action: string, display: string) {
    setBusy(display)
    try {
      if (action === "confirm_diagnosis") {
        await decision.confirmDiagnosis(diagnosis.id)
      } else {
        await decision.advanceDiagnosis(diagnosis.id, "confirmed")
      }
      onAction?.()
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="w-full rounded-2xl border border-slate-200 bg-white p-4 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800/60">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="inline-flex h-2.5 w-2.5 rounded-full"
              style={{ background: levelColor[diagnosis.level] ?? "#22D3EE" }}
            />
            <span className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
              {`代表 #${diagnosis.rep_id}`}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-700/50 dark:text-slate-300">
              {diagnosis.domain}
            </span>
            {/* 误判排除闸角标：命中结构性排除因素时，红灯降级且免误报 */}
            {excluded && (
              <span
                title={`误判排除：${diagnosis.excluded_reason?.label ?? ""}（原 ${diagnosis.excluded_reason?.original_level} → ${diagnosis.level}）`}
                className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
              >
                🛡 误判排除
              </span>
            )}
          </div>
          <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
            {diagnosis.summary ?? ""}
          </div>

          {/* 误判排除闸说明条：命中结构性因素，避免一线误判为"躺平" */}
          {excluded && (
            <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
              <div className="font-semibold">
                🛡 误判排除 · {diagnosis.excluded_reason?.label}
              </div>
              <div className="mt-0.5 text-amber-700/90 dark:text-amber-200/80">
                {diagnosis.excluded_reason?.desc}
                {diagnosis.excluded_reason?.original_level && (
                  <span className="ml-1 text-[10px] text-amber-500/80">
                    （原 {diagnosis.excluded_reason.original_level} → 已降级为 {diagnosis.level}）
                  </span>
                )}
              </div>
            </div>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-500 dark:text-slate-400">
            <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">
              状态：{statusText[diagnosis.status] ?? diagnosis.status}
            </span>
            {diagnosis.created_at && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">
                {diagnosis.created_at.slice(0, 10)}
              </span>
            )}
            {diagnosis.signals?.length > 0 && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">
                信号 {diagnosis.signals.length}
              </span>
            )}
          </div>
        </div>

        {/* OAG 置信度档位角标 🟢/🟡/🔴 */}
        {band && (
          <div className="flex shrink-0 flex-col items-end gap-1">
            <div className="flex items-center gap-1.5 rounded-full bg-slate-100 px-2 py-1 dark:bg-slate-800">
              <span
                className="inline-flex h-2.5 w-2.5 rounded-full"
                style={{ background: band.dot }}
              />
              <span className="text-[11px] font-medium text-slate-600 dark:text-slate-300">
                {band.text}
              </span>
            </div>
            <span className="text-[11px] tabular-nums text-slate-400">
              {(diagnosis.confidence * 100).toFixed(0)}%
            </span>
            {vd && (
              <button
                onClick={() => setShowDetail((s) => !s)}
                className="text-[10px] text-indigo-400 hover:text-indigo-300"
              >
                {showDetail ? "收起校验" : "校验明细"}
              </button>
            )}
          </div>
        )}
      </div>

      {/* OAG Layer 4 校验明细展开区 */}
      {showDetail && vd && (
        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3 dark:border-slate-700 dark:bg-slate-800/40">
          <div className="mb-1.5 text-[11px] font-medium text-slate-500 dark:text-slate-400">
            生成校验明细（OAG Layer 4）
          </div>
          <ul className="space-y-1">
            {checks.map((c) => (
              <li
                key={c.key}
                className="flex items-center justify-between text-[11px]"
              >
                <span className="text-slate-600 dark:text-slate-300">{c.label}</span>
                <span className="flex items-center gap-1.5 font-medium">
                  {checkIcon(c.ok)}
                  <span
                    className={
                      c.ok === false
                        ? "text-rose-500"
                        : c.ok === true
                          ? "text-emerald-500"
                          : "text-slate-400"
                    }
                  >
                    {c.ok === false ? "异常" : c.ok === true ? "通过" : "不适用"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SourceBadge provenance={diagnosis.provenance} />
        <ProvenanceBadge provenance={diagnosis.provenance} />
      </div>

      {/* OAG Layer 5 可触发动作按钮区 */}
      {diagnosis.action_suggestion && diagnosis.action_suggestion.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
          <div className="mb-2 text-[11px] font-medium text-slate-500 dark:text-slate-400">
            可触发动作
          </div>
          <div className="flex flex-wrap gap-2">
            {diagnosis.action_suggestion.map((act) => (
              <button
                key={act.action}
                disabled={busy !== null}
                onClick={() => runAction(act.action, act.display_name)}
                title={act.description}
                className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-50 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300 dark:hover:bg-indigo-500/20"
              >
                {act.risk_level && (
                  <span
                    className="inline-flex h-1.5 w-1.5 rounded-full"
                    style={{ background: riskColor[act.risk_level] ?? "#94A3B8" }}
                  />
                )}
                {act.display_name}
                {busy === act.display_name && (
                  <span className="animate-pulse text-[10px]">…</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {diagnosis.reasoning_chain_id && (
        <ReasoningTimeline chainId={diagnosis.reasoning_chain_id} compact />
      )}
    </div>
  )
}

export default DiagnosisCard
