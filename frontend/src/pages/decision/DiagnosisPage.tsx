import { useState, useEffect } from 'react'
import { Brain, Cpu, GitBranch, Clock, ShieldCheck, Zap, ChevronDown } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Button from '@/components/ui/Button'
import Select from '@/components/ui/Select'
import Empty from '@/components/ui/Empty'
import { decisionAPI } from '@/services/decision'
import type { DiagnosisEntity, ProvenanceInfo, ActionSuggestion } from '@/types'
import { SignalCard } from '@/components/decision/SignalCard'

// OAG 置信度档位 🟢/🟡/🔴 配色（对齐方案）
const bandMeta: Record<string, { dot: string; text: string }> = {
  GREEN: { dot: "#22C55E", text: "高置信" },
  YELLOW: { dot: "#EAB308", text: "中置信" },
  RED: { dot: "#EF4444", text: "低置信" },
}
const riskColor: Record<string, string> = {
  L1: "#22C55E",
  L2: "#EAB308",
  L3: "#FB923C",
  L4: "#EF4444",
}

const levelColor: Record<string, string> = {
  RED: "#EF4444",
  YELLOW: "#F59E0B",
  GREEN: "#22C55E",
}

function SourceBadge({ provenance }: { provenance: ProvenanceInfo | null }) {
  const isAi = provenance?.mode === "ai_orchestrated"
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold"
      style={{
        background: isAi ? "rgba(34,211,238,0.18)" : "rgba(148,163,184,0.18)",
        color: isAi ? "#22D3EE" : "#94A3B8",
      }}
    >
      {isAi ? <Cpu size={11} /> : <ShieldCheck size={11} />}
      {isAi ? `AI · ${provenance?.model_version ?? "orchestrated"}` : "规则降级"}
    </span>
  )
}

function ProvenanceBadge({ provenance }: { provenance: ProvenanceInfo | null }) {
  if (!provenance) return null
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-brand-500/15 px-2 py-0.5 text-[10px] font-medium text-brand-600 dark:text-brand-300">
      <GitBranch size={11} />
      血缘 run#{provenance.run_id ?? '-'}
    </span>
  )
}

function ReasoningTimeline({ chainId }: { chainId: number | null }) {
  const [open, setOpen] = useState(false)
  const [steps, setSteps] = useState<any[] | null>(null)
  const [loading, setLoading] = useState(false)

  async function toggle() {
    if (!open && chainId && !steps) {
      setLoading(true)
      try {
        const chain = await decisionAPI.getReasoningChain(chainId)
        setSteps(chain?.steps || [])
      } finally {
        setLoading(false)
      }
    }
    setOpen((v) => !v)
  }

  if (!chainId) return null

  return (
    <div className="mt-3 rounded-xl border border-cyan-400/15 bg-cyan-400/5">
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-cyan-200"
      >
        <span className="flex items-center gap-1.5">
          <Brain size={13} /> 推理链 #{chainId}
        </span>
        <ChevronDown
          size={14}
          className="transition-transform"
          style={{ transform: open ? "rotate(180deg)" : "none" }}
        />
      </button>
      {open && (
        <div className="border-t border-cyan-400/10 px-3 py-2">
          {loading && <div className="text-[11px] text-slate-400">加载推理链…</div>}
          {(steps || []).map((s: any, i: number) => (
            <div key={i} className="relative flex gap-3 pb-3 last:pb-0">
              <div className="mt-1 flex flex-col items-center">
                <span className="h-2 w-2 rounded-full bg-cyan-400" />
                {i < (steps!.length - 1) && (
                  <span className="mt-1 w-px flex-1 bg-cyan-400/30" />
                )}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-200">
                  <Zap size={11} className="text-cyan-300" /> {s.step || s.thought?.slice(0, 40) || `步骤 ${i + 1}`}
                </div>
                {s.tool && (
                  <div className="mt-0.5 text-[10px] text-indigo-300">工具：{s.tool}</div>
                )}
                {s.observation && (
                  <div className="mt-0.5 text-[10px] leading-relaxed text-slate-500 dark:text-slate-400">{s.observation}</div>
                )}
              </div>
            </div>
          ))}
          {!loading && (steps?.length ?? 0) === 0 && (
            <div className="text-[11px] text-slate-400">该推理链暂无步骤记录</div>
          )}
        </div>
      )}
    </div>
  )
}

export function DiagnosisPage() {
  const [diagnoses, setDiagnoses] = useState<DiagnosisEntity[]>([])
  const [loading, setLoading] = useState(true)
  const [domain, setDomain] = useState("coverage")

  async function load() {
    setLoading(true)
    try {
      const data = await decisionAPI.listDiagnoses(undefined, domain)
      setDiagnoses(data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [domain])

  function handleSignalCleared(diagnosisId: number, signalId: number) {
    setDiagnoses((prev) =>
      prev.map((d) =>
        d.id === diagnosisId
          ? { ...d, signals: d.signals.map((s) => (s.id === signalId ? { ...s, cleared: 1 } : s)) }
          : d,
      ),
    )
  }

  function handleDiagnosed(d: DiagnosisEntity) {
    setDiagnoses((prev) => [d, ...prev])
  }

  // OAG 诊断卡视图：合并来源/血缘/置信度档位/校验明细/可触发动作
  function DiagnosisCardView({
    d,
    onAction,
    onSignalCleared,
  }: {
    d: DiagnosisEntity
    onAction: () => void
    onSignalCleared: (diagnosisId: number, signalId: number) => void
  }) {
    const [showDetail, setShowDetail] = useState(false)
    const [busy, setBusy] = useState<string | null>(null)

    const band = d.confidence_band ? bandMeta[d.confidence_band] : null
    const vd = d.validation_detail
    const checks: { label: string; ok?: boolean | null }[] = [
      { label: "数值一致性", ok: vd?.numeric_ok },
      { label: "关系存在性", ok: vd?.relation_ok },
      { label: "时间逻辑", ok: vd?.temporal_ok },
      { label: "因果链完整", ok: vd?.causal_ok },
      { label: "业务规则合规", ok: vd?.business_rule_ok },
    ]
    const checkIcon = (ok?: boolean | null) =>
      ok === null || ok === undefined ? (
        <span className="text-slate-400">—</span>
      ) : ok ? (
        <span className="text-emerald-500">✓</span>
      ) : (
        <span className="text-rose-500">⚠</span>
      )

    async function runAction(act: ActionSuggestion) {
      setBusy(act.display_name)
      try {
        if (act.action === "confirm_diagnosis") {
          await decisionAPI.confirmDiagnosis(d.id)
        } else {
          await decisionAPI.advanceDiagnosis(d.id, "confirmed")
        }
        onAction()
      } finally {
        setBusy(null)
      }
    }

    return (
      <div
        className="rounded-2xl border border-slate-200 bg-white p-4 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800/60"
        style={{ boxShadow: `0 0 0 1px ${levelColor[d.level] ?? "#22D3EE"}22` }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span
                className="inline-flex h-2.5 w-2.5 rounded-full"
                style={{ background: levelColor[d.level] ?? "#22D3EE" }}
              />
              <span className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                {`代表 #${d.rep_id}`}
              </span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-700/50 dark:text-slate-300">
                {d.domain}
              </span>
            </div>
            <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
              {d.summary ?? ""}
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-slate-500 dark:text-slate-400">
              <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">
                状态：{d.status}
              </span>
              {d.created_at && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">
                  {d.created_at.slice(0, 10)}
                </span>
              )}
              {d.signals?.length > 0 && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-slate-800">
                  信号 {d.signals.length}
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
                {((d.confidence ?? 0) * 100).toFixed(0)}%
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
              {checks.map((c, i) => (
                <li
                  key={i}
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
          <SourceBadge provenance={d.provenance} />
          <ProvenanceBadge provenance={d.provenance} />
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/15 px-2 py-0.5 text-[10px] text-slate-300">
            <Clock size={11} /> {d.trace_id}
          </span>
        </div>

        <ReasoningTimeline chainId={d.reasoning_chain_id} />

        {/* OAG Layer 5 可触发动作按钮区 */}
        {d.action_suggestion && d.action_suggestion.length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
            <div className="mb-2 text-[11px] font-medium text-slate-500 dark:text-slate-400">
              可触发动作
            </div>
            <div className="flex flex-wrap gap-2">
              {d.action_suggestion.map((act) => (
                <button
                  key={act.action}
                  disabled={busy !== null}
                  onClick={() => runAction(act)}
                  title={act.description}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-2.5 py-1 text-[11px] font-medium text-brand-700 transition hover:bg-brand-100 disabled:opacity-50 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-300 dark:hover:bg-brand-500/20"
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

        {d.signals && d.signals.length > 0 && (
          <div className="mt-3">
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              异常信号（{d.signals.filter((s) => !s.cleared).length}/{d.signals.length} 未消除）
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {d.signals.map((s) => (
                <SignalCard
                  key={s.id}
                  signal={s}
                  onCleared={(id) => onSignalCleared(d.id, id)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="AI 诊断中枢"
        description="本体驱动 · 经 Orchestrator 七步编排 · 合规闸门（AI 仅生成草稿）"
        breadcrumbs={[{ label: '智能决策' }, { label: '统一诊断' }]}
        icon={<Brain className="w-5 h-5" />}
        actions={
          <div className="flex items-center gap-3">
            <div className="w-36">
              <Select
                aria-label="诊断领域"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                options={[
                  { label: '覆盖域', value: 'coverage' },
                  { label: '合规域', value: 'compliance' },
                  { label: '增长域', value: 'growth' },
                ]}
              />
            </div>
            <Button
              onClick={async () => {
                const r = await decisionAPI.aiDiagnose(domain)
                handleDiagnosed(r)
              }}
            >
              <Zap size={15} /> 运行 AI 诊断
            </Button>
          </div>
        }
      />

      {loading ? (
        <div className="text-slate-500 dark:text-slate-400">加载诊断…</div>
      ) : diagnoses.length === 0 ? (
        <Empty description="暂无诊断草稿，点击「运行 AI 诊断」启动编排器" />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {diagnoses.map((d) => (
            <DiagnosisCardView
              key={d.id}
              d={d}
              onAction={load}
              onSignalCleared={handleSignalCleared}
            />
          ))}
        </div>
      )}
    </div>
  )
}
