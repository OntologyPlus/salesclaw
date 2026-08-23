import { useState } from "react"
import { TrendingUp, Award, AlertCircle, Brain, Cpu, GitBranch, Sparkles } from "lucide-react"
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts"
import { decisionAPI } from "../../services/decision"
import type { AttributionResult, AttributionFactor } from "../../types"

const CATEGORY_COLOR: Record<string, string> = {
  negative: "#EF4444",
  positive: "#22C55E",
}

export function AttributionPage() {
  const [ai, setAi] = useState<AttributionResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [rule] = useState<any>(null)

  async function runAiAttribution() {
    setBusy(true)
    try {
      const r = await decisionAPI.getAttributionAI("attribution")
      setAi(r)
    } finally {
      setBusy(false)
    }
  }

  const factors: AttributionFactor[] = ai?.factors || []
  const chartData = factors.map((f) => ({
    name: f.name,
    contribution: f.contribution,
    direction: f.direction || "negative",
    evidence: f.evidence || "",
  }))

  return (
    <div className="min-h-screen p-6 text-slate-900 dark:text-slate-100">
      <div className="mx-auto max-w-5xl">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold">
              <TrendingUp className="text-cyan-400" /> 归因分析
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              各维度对业绩下滑的贡献度与根因 · 经 Orchestrator 七步编排
            </p>
          </div>
          <button
            onClick={runAiAttribution}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-500/80 px-4 py-2 text-sm font-medium text-white transition hover:bg-cyan-400 disabled:opacity-50"
          >
            <Sparkles size={15} /> {busy ? "推理中…" : "运行 AI 归因"}
          </button>
        </header>

        {!ai && (
            <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <Brain className="mx-auto mb-3 w-12 text-slate-400" />
            点击「运行 AI 归因」启动编排器，生成因子贡献度与根因
          </div>
        )}

        {ai && (
          <>
            {/* AI 摘要 + 来源/血缘 */}
            <div className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center gap-3">
                <Award className="h-8 w-8 text-cyan-500 dark:text-cyan-300" />
                <div className="flex-1">
                  <p className="text-sm text-slate-500 dark:text-slate-400">AI 归因结论</p>
                  <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{ai.summary}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span
                  className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold"
                  style={{
                    background: ai.source === "ai" ? "rgba(34,211,238,0.18)" : "rgba(148,163,184,0.18)",
                    color: ai.source === "ai" ? "#22D3EE" : "#94A3B8",
                  }}
                >
                  {ai.source === "ai" ? <Cpu size={11} /> : <AlertCircle size={11} />}
                  {ai.source === "ai" ? `AI · ${ai.provenance?.model_version ?? "orchestrated"}` : "规则降级"}
                </span>
                {ai.provenance?.run_id != null && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-indigo-500/15 px-2 py-0.5 text-[10px] text-indigo-300">
                    <GitBranch size={11} /> 血缘 run#{ai.provenance.run_id}
                  </span>
                )}
                {ai.reasoning_chain_id != null && (
                  <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] text-cyan-300">
                    推理链 #{ai.reasoning_chain_id}
                  </span>
                )}
              </div>
            </div>

            {/* 因子贡献度柱状图 */}
            <div className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <h3 className="mb-4 font-semibold text-slate-900 dark:text-slate-100">因子贡献度</h3>
              <ResponsiveContainer width="100%" height={Math.max(220, factors.length * 46)}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 90, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis type="number" tick={{ fontSize: 12, fill: "#94a3b8" }} stroke="#334155" />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "#cbd5e1" }} stroke="#334155" width={90} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: "8px", color: "#fff" }}
                    formatter={(value: number, _name: string, props: any) =>
                      [`贡献 ${value}（${props?.payload?.direction === "negative" ? "负向" : "正向"}）`, props?.payload?.evidence || ""]
                    }
                  />
                  <Bar dataKey="contribution" radius={[0, 4, 4, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={CATEGORY_COLOR[entry.direction] || "#6366F1"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 flex items-center justify-center gap-4">
                <span className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                  <span className="h-3 w-3 rounded bg-[#EF4444]" /> 负向因子
                </span>
                <span className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                  <span className="h-3 w-3 rounded bg-[#22C55E]" /> 正向因子
                </span>
              </div>
            </div>

            {/* 根因高亮 */}
            <div className="rounded-2xl border border-rose-300/30 bg-rose-50 p-5 dark:border-rose-500/30 dark:bg-rose-500/10">
              <div className="mb-2 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-rose-500 dark:text-rose-300" />
                <h3 className="font-semibold text-slate-900 dark:text-slate-100">根因</h3>
              </div>
              <p className="text-sm leading-relaxed text-rose-100">{ai.root_cause}</p>
            </div>

            {/* L2 关系链推理：跨对象归因路径 */}
            {ai.chain && ai.chain.paths && ai.chain.paths.length > 0 && (
              <div className="rounded-2xl border border-indigo-500/30 bg-indigo-500/5 p-5 dark:border-indigo-500/40 dark:bg-indigo-500/10">
                <div className="mb-1 flex items-center gap-2">
                  <GitBranch className="h-4 w-4 text-indigo-400" />
                  <h3 className="font-semibold text-slate-900 dark:text-slate-100">关系链归因路径（L2 跨对象）</h3>
                </div>
                <p className="mb-4 text-xs text-slate-500 dark:text-slate-400">
                  沿 Ontology 关系网多跳传导 · 确定性规则 {ai.chain.ai_generated ? "（AI 润色）" : "（规则降级）"}
                </p>

                <div className="space-y-4">
                  {ai.chain.paths
                    .slice()
                    .sort((a, b) => b.arrived_prob - a.arrived_prob)
                    .map((path, i) => (
                      <div
                        key={i}
                        className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
                      >
                        <div className="mb-3 flex items-center justify-between">
                          <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                            路径 {i + 1} · {path.depth} 跳
                          </span>
                          <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[11px] font-semibold text-cyan-300">
                            到达概率 {(path.arrived_prob * 100).toFixed(1)}%
                          </span>
                        </div>

                        {/* 横向节点链 */}
                        <div className="flex flex-wrap items-center gap-1">
                          {path.nodes.map((node, ni) => (
                            <div key={ni} className="flex items-center gap-1">
                              <div
                                className={`rounded-lg px-2.5 py-1.5 text-xs font-medium ${
                                  ni === path.nodes.length - 1
                                    ? "bg-rose-500/20 text-rose-200 ring-1 ring-rose-400/40"
                                    : ni === 0
                                    ? "bg-indigo-500/20 text-indigo-200 ring-1 ring-indigo-400/40"
                                    : "bg-slate-700/40 text-slate-200"
                                }`}
                              >
                                {node}
                              </div>
                              {ni < path.links.length && (
                                <div className="flex flex-col items-center px-0.5">
                                  <span className="text-[10px] leading-none text-indigo-300/80">
                                    {path.links[ni]?.display_name || path.links[ni]?.name}
                                  </span>
                                  <span className="text-rose-400/70">→</span>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>

                        {/* 每跳贡献度 */}
                        <div className="mt-3">
                          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-700/50">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-cyan-400"
                              style={{ width: `${Math.min(100, path.contribution * 100)}%` }}
                            />
                          </div>
                          <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                            单跳传播权重 {(path.contribution * 100).toFixed(0)}%
                            {path.links[path.links.length - 1]?.relation
                              ? ` · ${path.links[path.links.length - 1].relation}`
                              : ""}
                          </p>
                        </div>
                      </div>
                    ))}
                </div>

                {/* 根因定位 */}
                {ai.chain.root_cause && (
                  <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3">
                    <p className="text-xs font-medium text-amber-200">
                      根因定位：{ai.chain.root_cause.display_name}
                      <span className="ml-1 text-amber-300/70">
                        （贡献度 {(ai.chain.root_cause.contribution * 100).toFixed(1)}%）
                      </span>
                    </p>
                    <p className="mt-0.5 text-[11px] text-amber-200/80">{ai.chain.root_cause.reason}</p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
