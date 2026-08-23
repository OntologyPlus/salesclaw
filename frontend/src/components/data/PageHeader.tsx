import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import type { Breadcrumb } from '@/types'

interface PageHeaderProps {
  title: string
  description?: string
  breadcrumbs?: Breadcrumb[]
  icon?: ReactNode
  gradient?: boolean
  actions?: ReactNode
}

// 页面顶部标题区，统一风格
// F2：gradient prop 保留向后兼容，但不再渲染渐变背景（去 demo 感）
export default function PageHeader({ title, description, breadcrumbs, icon, gradient = false, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 relative overflow-hidden rounded-2xl p-6 bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark">
      <div className="relative">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav className="flex items-center gap-1 mb-2 text-xs text-slate-500 dark:text-slate-400">
            {breadcrumbs.map((bc, i) => (
              <span key={i} className="flex items-center gap-1">
                {bc.path ? (
                  <Link to={bc.path} className="hover:underline">{bc.label}</Link>
                ) : (
                  <span>{bc.label}</span>
                )}
                {i < breadcrumbs.length - 1 && <ChevronRight className="w-3 h-3" />}
              </span>
            ))}
          </nav>
        )}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {icon && (
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400">
                {icon}
              </div>
            )}
            <div>
              <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{title}</h1>
              {description && (
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>
              )}
            </div>
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </div>
      </div>
    </div>
  )
}
