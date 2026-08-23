import type { ReactNode } from 'react'
import { Inbox } from 'lucide-react'

interface EmptyProps {
  description?: string
  icon?: ReactNode
}

// 空状态组件
export default function Empty({ description = '暂无数据', icon }: EmptyProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="mb-3 text-slate-300 dark:text-slate-600">
        {icon || <Inbox className="w-12 h-12" />}
      </div>
      <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
    </div>
  )
}
