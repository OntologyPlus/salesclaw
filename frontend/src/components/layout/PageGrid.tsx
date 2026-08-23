// F-重构：统计卡片栅格——统一各总览页顶部 stat 栅格与加载骨架
import type { ReactNode } from 'react'
import Skeleton from '@/components/ui/Skeleton'

interface PageGridProps {
  children: ReactNode
  /** 加载时渲染的骨架数量 */
  loading?: boolean
  skeletonCount?: number
  className?: string
}

export default function PageGrid({
  children,
  loading,
  skeletonCount = 4,
  className = '',
}: PageGridProps) {
  if (loading) {
    return (
      <div className={`grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 ${className}`}>
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <div
            key={i}
            className="p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark"
          >
            <Skeleton lines={2} />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 ${className}`}>
      {children}
    </div>
  )
}
