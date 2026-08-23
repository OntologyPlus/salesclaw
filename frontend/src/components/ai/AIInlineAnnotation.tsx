import { Sparkles, AlertTriangle, CheckCircle, Info } from 'lucide-react'

type AnnotationLevel = 'info' | 'warning' | 'success' | 'error'

interface AIInlineAnnotationProps {
  /** 洞察内容 */
  message: string
  /** 级别 */
  level?: AnnotationLevel
  /** 可选标题 */
  label?: string
  /** 自定义 className */
  className?: string
}

const levelConfig: Record<AnnotationLevel, { icon: typeof Sparkles; border: string; bg: string; text: string; dot: string }> = {
  info: {
    icon: Info,
    border: 'border-l-sky-400',
    bg: 'bg-sky-50/50 dark:bg-sky-900/10',
    text: 'text-sky-700 dark:text-sky-300',
    dot: 'bg-sky-400',
  },
  warning: {
    icon: AlertTriangle,
    border: 'border-l-amber-400',
    bg: 'bg-amber-50/50 dark:bg-amber-900/10',
    text: 'text-amber-700 dark:text-amber-300',
    dot: 'bg-amber-400',
  },
  success: {
    icon: CheckCircle,
    border: 'border-l-emerald-400',
    bg: 'bg-emerald-50/50 dark:bg-emerald-900/10',
    text: 'text-emerald-700 dark:text-emerald-300',
    dot: 'bg-emerald-400',
  },
  error: {
    icon: AlertTriangle,
    border: 'border-l-rose-400',
    bg: 'bg-rose-50/50 dark:bg-rose-900/10',
    text: 'text-rose-700 dark:text-rose-300',
    dot: 'bg-rose-400',
  },
}

/**
 * AI 内联标注条
 *
 * 形态：左侧竖线 + AI 图标 + 一句话洞察，紧凑不占空间。
 * 可嵌入任意列表/表格/卡片区块旁。
 */
export default function AIInlineAnnotation({
  message,
  level = 'info',
  label,
  className = '',
}: AIInlineAnnotationProps) {
  const config = levelConfig[level]
  const Icon = config.icon

  return (
    <div className={`flex items-start gap-2 px-3 py-2 rounded-r-lg border-l-[3px] ${config.border} ${config.bg} ${className}`}>
      <Sparkles className={`w-3.5 h-3.5 shrink-0 mt-0.5 ${config.text}`} />
      <div className="flex-1 min-w-0">
        {label && (
          <span className={`text-[10px] font-semibold uppercase tracking-wide ${config.text}`}>
            {label}
          </span>
        )}
        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          {message}
        </p>
      </div>
    </div>
  )
}
