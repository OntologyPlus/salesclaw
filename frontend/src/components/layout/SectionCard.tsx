// F-重构：区块卡片——统一各总览页"卡片外框 + 标题 + 查看全部"的重复结构
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

interface SectionCardProps {
  title: ReactNode
  icon?: ReactNode
  /** 查看全部链接；传入则右上角显示 */
  viewAllTo?: string
  viewAllLabel?: string
  /** 自定义右侧操作区（优先级高于 viewAllTo） */
  action?: ReactNode
  className?: string
  children: ReactNode
}

export default function SectionCard({
  title,
  icon,
  viewAllTo,
  viewAllLabel = '查看全部',
  action,
  className = '',
  children,
}: SectionCardProps) {
  return (
    <section
      className={`rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden ${className}`}
    >
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
          {icon && <span className="text-brand-600 dark:text-brand-400">{icon}</span>}
          {title}
        </h2>
        {action ??
          (viewAllTo && (
            <Link
              to={viewAllTo}
              className="flex items-center gap-1 text-sm text-brand-600 dark:text-brand-400 hover:underline"
            >
              {viewAllLabel} <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ))}
      </div>
      {children}
    </section>
  )
}
