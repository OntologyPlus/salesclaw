import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowRight } from 'lucide-react'
import { navIconMap } from './navIcons'
import type { NavItem } from '@/config/navConfig'
import SectionCard from '@/components/layout/SectionCard'

interface DomainNavGridProps {
  title?: string
  items: NavItem[]
  className?: string
}

/** 域总览能力矩阵：展示本域全量能力，强化产品广度感知 */
export default function DomainNavGrid({
  title,
  items,
  className = '',
}: DomainNavGridProps) {
  const { t } = useTranslation()
  if (!items.length) return null
  const heading = title ?? t('common.capabilityMatrix')

  return (
    <SectionCard
      title={
        <span className="inline-flex items-baseline gap-2">
          {heading}
          <span className="text-xs font-normal text-slate-400">{items.length}</span>
        </span>
      }
      className={className}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4">
        {items.map((item) => {
          const Icon = item.icon ?? navIconMap[item.path]
          const label = t(item.labelKey, { defaultValue: item.label })
          const isPrimary = (item.tier ?? 'primary') === 'primary'
          return (
            <Link
              key={item.path}
              to={item.path}
              className="group flex items-start gap-3 rounded-xl border border-slate-200 dark:border-surface-border-subtle-dark bg-white dark:bg-surface-card-dark px-3.5 py-3 hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-sm transition-all"
            >
              {Icon && (
                <div
                  className={`flex items-center justify-center w-9 h-9 rounded-lg shrink-0 ${
                    isPrimary
                      ? 'bg-brand-50 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400'
                      : 'bg-slate-100 text-slate-600 dark:bg-surface-raised-dark dark:text-slate-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate group-hover:text-brand-600">
                    {label}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600 group-hover:text-brand-500 shrink-0" />
                </div>
                <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                  {isPrimary ? t('common.coreCapability') : t('common.extendedCapability')}
                </p>
              </div>
            </Link>
          )
        })}
      </div>
    </SectionCard>
  )
}
