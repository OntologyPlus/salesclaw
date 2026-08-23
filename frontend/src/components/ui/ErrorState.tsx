import { AlertCircle, RefreshCw } from 'lucide-react'

// 本地 cn 工具（简单字符串拼接，避免引入新依赖）
function cn(...classes: Array<string | undefined | false | null>): string {
  return classes.filter(Boolean).join(' ')
}

interface ErrorStateProps {
  title?: string
  message?: string
  errorCode?: string | number
  onRetry?: () => void
  className?: string
}

export function ErrorState({
  title = '加载失败',
  message = '发生未知错误，请稍后重试',
  errorCode,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center text-center py-12 px-6', className)}>
      <div className="mb-4 p-3 rounded-2xl bg-rose-50 dark:bg-rose-900/20 text-rose-500">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</h3>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 max-w-sm">{message}</p>
      {errorCode && (
        <code className="mt-2 px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] text-slate-500 font-mono">
          错误码：{errorCode}
        </code>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-5 inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-brand-600 text-white text-xs font-medium hover:bg-brand-700 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          重试
        </button>
      )}
    </div>
  )
}

export default ErrorState
