// F-重构：列表区块——统一各总览页"加载骨架/空态/行渲染"的重复模式
import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'

interface ListSectionProps<T> {
  items?: T[]
  loading?: boolean
  /** 空态文案 */
  emptyText?: string
  /** 每行渲染（含 hover 高亮与左侧进入动画） */
  renderRow: (item: T, index: number) => ReactNode
  /** 行容器额外 className（用于整行可点击） */
  rowClassName?: string
  skeletonRows?: number
}

export default function ListSection<T>({
  items,
  loading,
  emptyText = '暂无数据',
  renderRow,
  rowClassName = '',
  skeletonRows = 3,
}: ListSectionProps<T>) {
  if (loading) {
    return (
      <div className="divide-y divide-slate-200 dark:divide-surface-border-subtle-dark">
        {Array.from({ length: skeletonRows }).map((_, i) => (
          <div key={i} className="px-5 py-4">
            <Skeleton lines={2} />
          </div>
        ))}
      </div>
    )
  }

  if (!items || items.length === 0) {
    return (
      <div className="px-5 py-10">
        <Empty description={emptyText} />
      </div>
    )
  }

  return (
    <div className="divide-y divide-slate-200 dark:divide-surface-border-subtle-dark">
      {items.map((item, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2, delay: Math.min(i * 0.04, 0.3) }}
          className={`px-5 py-3.5 hover:bg-slate-50 dark:hover:bg-surface-raised-dark transition-colors ${rowClassName}`}
        >
          {renderRow(item, i)}
        </motion.div>
      ))}
    </div>
  )
}
