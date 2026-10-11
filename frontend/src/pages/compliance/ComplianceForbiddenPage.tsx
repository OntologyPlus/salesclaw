import { useState } from 'react'
import { Ban, Wrench } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Badge from '@/components/ui/Badge'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import { complianceAPI } from '@/services/compliance'

interface ForbiddenBehavior {
  id: number
  subject: string
  behavior: string
  legal_basis: string | null
  severity: string
}

interface ForbiddenTool {
  id: number
  tool_name: string
  category: string
  risk_description: string | null
}

const subjects = ['企业', '医药代表', '医疗卫生人员', '药品']
const sevVariant: Record<string, 'default' | 'warning' | 'error'> = {
  low: 'default',
  medium: 'warning',
  high: 'error',
  critical: 'error',
}

export default function ComplianceForbiddenPage() {
  const [tab, setTab] = useState('企业')
  const { data: behaviors } = useFetch<ForbiddenBehavior[]>(
    () => complianceAPI.listForbiddenBehaviors(tab),
    [tab]
  )
  const { data: tools } = useFetch<ForbiddenTool[]>(
    () => complianceAPI.listForbiddenTools(),
    []
  )

  return (
    <div>
      <PageHeader
        title="禁止行为清单"
        description="医药代表从业禁止行为及禁止工具（第 11、12、24、25 条）"
        breadcrumbs={[{ label: '合规专项' }, { label: '禁止行为' }]}
        icon={<Ban className="w-5 h-5" />}
        gradient
      />

      <div className="flex items-center gap-2 mb-4">
        {subjects.map((s) => (
          <button
            key={s}
            onClick={() => setTab(s)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              tab === s
                ? 'bg-brand-50 text-brand-700 font-medium dark:bg-brand-900/30 dark:text-brand-300'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">禁止行为（{tab}）</h2>
        </div>
        {!behaviors?.length ? (
          <Empty description="暂无记录" />
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-700">
            {behaviors.map((b) => (
              <li key={b.id} className="flex items-start gap-3 px-5 py-3">
                <Ban className="w-4 h-4 text-rose-500 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm text-slate-800 dark:text-slate-100">{b.behavior}</p>
                  {b.legal_basis && (
                    <p className="text-xs text-slate-400 mt-0.5">依据：{b.legal_basis}</p>
                  )}
                </div>
                <Badge variant={sevVariant[b.severity] ?? 'default'}>{b.severity}</Badge>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-4 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark flex items-center gap-2">
          <Wrench className="w-4 h-4 text-amber-500" />
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">禁止工具</h2>
        </div>
        {!tools?.length ? (
          <Empty description="暂无记录" />
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-700">
            {tools.map((t) => (
              <li key={t.id} className="flex items-start gap-3 px-5 py-3">
                <Wrench className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm text-slate-800 dark:text-slate-100">{t.tool_name}</p>
                  {t.risk_description && (
                    <p className="text-xs text-slate-400 mt-0.5">{t.risk_description}</p>
                  )}
                </div>
                <Badge variant="default">{t.category}</Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
