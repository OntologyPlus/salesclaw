import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { BookOpen, TrendingUp, Target, Users, Layers, Link2 } from "lucide-react"
import { decisionAPI } from "../../services/decision"
import type { ParadigmEntity } from "../../types"

const DOMAIN_COLOR: Record<string, string> = {
  compliance: "#EF4444",
  academic: "#8B5CF6",
  visit: "#3B82F6",
  growth: "#F59E0B",
  coverage: "#0EA5E9",
}

export function ParadigmPage() {
  const [paradigms, setParadigms] = useState<ParadigmEntity[]>([])
  const [loading, setLoading] = useState(true)
  const [domain, setDomain] = useState("")

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    decisionAPI.getLibraryParadigms(domain || undefined).then((d) => {
      if (cancelled) return
      setParadigms(d || [])
      setLoading(false)
    }).catch(() => {
      if (!cancelled) setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [domain])

  const total =
    paradigms.reduce((s, p) => s + (p.evidence_execution_ids?.length || 0), 0)

  return (
    <div className="min-h-screen p-6 text-slate-900 dark:text-slate-100">
      <div className="mx-auto max-w-6xl">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold">
              <Layers className="text-indigo-400" /> 通用范式库
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              从已闭环有效执行沉淀的通用解题范式（本体 Paradigm 实体）· 可跨代表复用
            </p>
          </div>
          <select
            value={domain}
            onChange={(e) => {
              setDomain(e.target.value)
              setLoading(true)
              decisionAPI.getLibraryParadigms(e.target.value || undefined).then((d) => {
                setParadigms(d || [])
                setLoading(false)
              })
            }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          >
            <option value="">全部领域</option>
            <option value="coverage">覆盖域</option>
            <option value="compliance">合规域</option>
            <option value="growth">增长域</option>
          </select>
        </header>

        {/* 概览统计 */}
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <p className="text-sm text-slate-500 dark:text-slate-400">范式总数</p>
            <p className="text-3xl font-bold text-indigo-600 dark:text-indigo-300">{paradigms.length}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <p className="text-sm text-slate-500 dark:text-slate-400">来源执行数</p>
            <p className="text-3xl font-bold text-cyan-600 dark:text-cyan-300">{total}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <p className="text-sm text-slate-500 dark:text-slate-400">平均有效性</p>
            <p className="text-3xl font-bold text-green-300">
              {paradigms.length
                ? Math.round(
                    paradigms.reduce((s, p) => s + (p.effectiveness_score || 0), 0) /
                      paradigms.length,
                  )
                : 0}
            </p>
          </div>
        </div>

        {loading ? (
          <div className="text-slate-500 dark:text-slate-400">加载范式…</div>
        ) : paradigms.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <BookOpen className="mx-auto mb-3 w-12 text-slate-400" />
            暂无范式沉淀 · 当执行记录成功闭环且有效性 ≥ 70 时自动沉淀
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {paradigms.map((p) => {
              const color = DOMAIN_COLOR[p.domain] || "#94A3B8"
              return (
                <div
                  key={p.id}
                  className="rounded-2xl border border-slate-200 bg-white p-5 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800/60"
                  style={{ boxShadow: `0 0 0 1px ${color}22` }}
                >
                  <div className="flex items-start gap-4">
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                      style={{ background: `${color}22` }}
                    >
                      <Target className="h-5 w-5" style={{ color }} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex items-center gap-2">
                        <span
                          className="rounded px-2 py-0.5 text-xs font-medium"
                          style={{ background: `${color}22`, color }}
                        >
                          {p.domain}
                        </span>
                        <span className="text-xs text-slate-500 dark:text-slate-400">{p.problem_type}</span>
                      </div>
                      <h3 className="mb-1 text-base font-semibold text-slate-900 dark:text-slate-100">{p.title}</h3>
                      <p className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">{p.effective_method}</p>
                      <div className="mt-2 flex items-center gap-4 text-[11px] text-slate-500">
                        <span className="flex items-center gap-1">
                          <Users size={11} /> 复用 {p.usage_count}
                        </span>
                        <span className="flex items-center gap-1">
                          <BookOpen size={11} /> 证据执行 {p.evidence_execution_ids?.length || 0}
                        </span>
                        {p.reasoning_chain_id && (
                          <Link
                            to={`/decision/reasoning-chain/${p.reasoning_chain_id}`}
                            className="flex items-center gap-1 text-indigo-400 hover:underline"
                          >
                            <Link2 size={11} /> 来源推理链
                          </Link>
                        )}
                      </div>
                    </div>
                    <div className="shrink-0 text-center">
                      <div
                        className="flex h-16 w-16 items-center justify-center rounded-full text-lg font-bold text-white"
                        style={{
                          background:
                            (p.effectiveness_score || 0) >= 90 ? "#10B981"
                            : (p.effectiveness_score || 0) >= 80 ? "#34D399"
                            : "#F59E0B",
                        }}
                      >
                        {p.effectiveness_score || 0}
                      </div>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">有效性</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* 沉淀机制说明 */}
        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h3 className="mb-3 flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
            <TrendingUp className="h-4 w-4 text-slate-400" /> 范式沉淀机制
          </h3>
          <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-3">
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
              <p className="mb-1 font-semibold text-slate-700 dark:text-slate-200">自动提取</p>
              <p className="text-slate-500 dark:text-slate-400">执行成功闭环且有效性 ≥ 70 时，自动沉淀为范式实体。</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
              <p className="mb-1 font-semibold text-slate-700 dark:text-slate-200">相似合并</p>
              <p className="text-slate-500 dark:text-slate-400">同领域 + 同问题类型自动合并并累加复用次数。</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
              <p className="mb-1 font-semibold text-slate-700 dark:text-slate-200">跨域复用</p>
              <p className="text-slate-500 dark:text-slate-400">范式记录证据执行来源，供同类问题精准匹配推荐。</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
