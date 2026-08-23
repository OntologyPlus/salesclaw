/**
 * Skeleton 加载占位组件
 *
 * 兼容两种用法：
 * 1. 旧 API：<Skeleton lines={3} /> —— 渲染 N 行骨架（表格/列表等场景）
 * 2. 新 API（F17）：<Skeleton className="h-3 w-24" /> —— 单块骨架（聊天气泡等场景）
 *
 * F17 新增 MessageSkeleton：消息加载占位（头像 + 3 行文本）
 */
interface SkeletonProps {
  /** 渲染的行数（旧 API，默认 1） */
  lines?: number
  /** 自定义 className（新 API，与 lines 互斥；传 className 时忽略 lines） */
  className?: string
}

export function Skeleton({ lines, className }: SkeletonProps) {
  // 新 API：传 className 时，渲染单块骨架
  if (className) {
    return (
      <div
        className={`animate-shimmer bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 dark:from-slate-700 dark:via-slate-600 dark:to-slate-700 bg-[length:200%_100%] rounded ${className}`}
      />
    )
  }
  // 旧 API：传 lines 时，渲染 N 行骨架
  const count = lines && lines > 0 ? lines : 1
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="animate-shimmer h-3 rounded bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 dark:from-slate-700 dark:via-slate-600 dark:to-slate-700 bg-[length:200%_100%]"
          style={{ width: i === count - 1 ? '60%' : '100%' }}
        />
      ))}
    </div>
  )
}

export function MessageSkeleton() {
  return (
    <div className="flex items-start gap-3 animate-fade-in">
      <Skeleton className="w-8 h-8 rounded-full shrink-0" />
      <div className="flex-1 space-y-2 py-1">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </div>
  )
}

export default Skeleton
