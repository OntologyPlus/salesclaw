/**
 * 兼容别名：统一使用 Empty 作为空态组件。
 * 保留 EmptyState 导出名，避免历史 import 断裂。
 */
import type { ReactNode } from 'react'
import Empty from './Empty'

interface EmptyStateProps {
  title?: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div className={className}>
      <Empty description={description || title || '暂无数据'} icon={icon} />
      {action && <div className="flex justify-center -mt-8 pb-8">{action}</div>}
    </div>
  )
}

export default EmptyState
