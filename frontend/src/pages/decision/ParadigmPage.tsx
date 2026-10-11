import { Link } from 'react-router-dom'
import { BookOpen, TrendingUp, Target, Users, Layers, Link2 } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import SectionCard from '@/components/layout/SectionCard'
import Empty from '@/components/ui/Empty'
import ErrorState from '@/components/ui/ErrorState'
import Select from '@/components/ui/Select'
import { useFetch } from '@/hooks/useFetch'
import { decisionAPI } from '@/services/decision'
import type { ParadigmEntity } from '@/types'
import { useState } from 'react'

const DOMAIN_TINT: Record<string, string> = {
  compliance: 'bg-rose-100 text-rose-600 dark:bg-rose-900/20 dark:text-rose-400',
  academic: 'bg-violet-100 text-violet-600 dark:bg-violet-900/20 dark:text-violet-400',
  visit: 'bg-sky-100 text-sky-600 dark:bg-sky-900/20 dark:text-sky-400',
  growth: 'bg-amber-100 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400',
  coverage: 'bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400',
}

export function ParadigmPage() {
  const [domain, setDomain] = useState('')
  const { data, loading, error, refetch } = useFetch<ParadigmEntity[]>(
    () => decisionAPI.getLibraryParadigms(domain || undefined),
    [domain],
  )

  const paradigms = data ?? []
  const totalEvidence = paradigms.reduce((s, p) => s + (p.evidence_execution_ids?.length || 0), 0)
  const avgScore = paradigms.length
    ? Math.round(paradigms.reduce((s, p) => s + (p.effectiveness_score || 0), 0) / paradigms.length)
    : 0

  return (
    <div>
      <PageHeader
        title="通用范式库"
        description="从已闭环有效执行沉淀的通用解题范式（本体 Paradigm 实体）· 可跨代表复用"
        breadcrumbs={[{ label: '智能决策' }, { label: '范式库' }]}
        icon={<Layers className="w-5 h-5" />}
        actions={
          <div className="w-44">
            <Select
              aria-label="领域筛选"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              options={[
                { label: '全部领域', value: '' },
                { label: '覆盖域', value: 'coverage' },
                { label: '合规域', value: 'compliance' },
                { label: '增长域', value: 'growth' },
              ]}
            />
          </div>
        }
      />

      {error && <ErrorState message={error.message} onRetry={refetch} className="mb-4" />}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard title="范式总数" value={paradigms.length} icon={<Layers className="w-5 h-5" />} color="brand" />
        <StatCard title="来源执行数" value={totalEvidence} icon={<BookOpen className="w-5 h-5" />} color="emerald" />
        <StatCard title="平均有效性" value={avgScore} icon={<TrendingUp className="w-5 h-5" />} color="amber" />
      </div>

      {loading ? (
        <div className="text-sm text-slate-500 dark:text-slate-400">加载范式…</div>
      ) : paradigms.length === 0 ? (
        <SectionCard title="范式列表">
          <Empty description="暂无范式沉淀 · 当执行记录成功闭环且有效性 ≥ 70 时自动沉淀" />
        </SectionCard>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 mb-6">
          {paradigms.map((p) => {
            const tint = DOMAIN_TINT[p.domain] || 'bg-slate-100 text-slate-600 dark:bg-surface-raised-dark dark:text-slate-300'
            const score = p.effectiveness_score || 0
            return (
              <div
                key={p.id}
                className="rounded-2xl border border-slate-200 dark:border-surface-border-subtle-dark bg-white dark:bg-surface-card-dark p-5 transition hover:shadow-md"
              >
                <div className="flex items-start gap-4">
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${tint}`}>
                    <Target className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${tint}`}>{p.domain}</span>
                      <span className="text-xs text-slate-500 dark:text-slate-400">{p.problem_type}</span>
                    </div>
                    <h3 className="mb-1 text-base font-semibold text-slate-900 dark:text-slate-100">{p.title}</h3>
                    <p className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">{p.effective_method}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-4 text-[11px] text-slate-500">
                      <span className="flex items-center gap-1">
                        <Users size={11} /> 复用 {p.usage_count}
                      </span>
                      <span className="flex items-center gap-1">
                        <BookOpen size={11} /> 证据执行 {p.evidence_execution_ids?.length || 0}
                      </span>
                      {p.reasoning_chain_id && (
                        <Link
                          to={`/decision/reasoning-chain/${p.reasoning_chain_id}`}
                          className="flex items-center gap-1 text-brand-600 dark:text-brand-400 hover:underline"
                        >
                          <Link2 size={11} /> 来源推理链
                        </Link>
                      )}
                    </div>
                  </div>
                  <div className="shrink-0 text-center">
                    <div
                      className={`flex h-14 w-14 items-center justify-center rounded-full text-lg font-bold text-white ${
                        score >= 90 ? 'bg-emerald-500' : score >= 80 ? 'bg-brand-500' : 'bg-amber-500'
                      }`}
                    >
                      {score}
                    </div>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">有效性</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <SectionCard title="范式沉淀机制" icon={<TrendingUp className="w-4 h-4" />}>
        <div className="grid grid-cols-1 gap-4 p-5 text-sm md:grid-cols-3">
          <div className="rounded-xl bg-slate-50 p-3 dark:bg-surface-raised-dark">
            <p className="mb-1 font-semibold text-slate-700 dark:text-slate-200">自动提取</p>
            <p className="text-slate-500 dark:text-slate-400">执行成功闭环且有效性 ≥ 70 时，自动沉淀为范式实体。</p>
          </div>
          <div className="rounded-xl bg-slate-50 p-3 dark:bg-surface-raised-dark">
            <p className="mb-1 font-semibold text-slate-700 dark:text-slate-200">相似合并</p>
            <p className="text-slate-500 dark:text-slate-400">同领域 + 同问题类型自动合并并累加复用次数。</p>
          </div>
          <div className="rounded-xl bg-slate-50 p-3 dark:bg-surface-raised-dark">
            <p className="mb-1 font-semibold text-slate-700 dark:text-slate-200">跨域复用</p>
            <p className="text-slate-500 dark:text-slate-400">范式记录证据执行来源，供同类问题精准匹配推荐。</p>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}

export default ParadigmPage
