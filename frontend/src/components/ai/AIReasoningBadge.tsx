import { useState, useRef, useEffect, useCallback } from 'react'
import { Brain, Zap } from 'lucide-react'

interface AIReasoningBadgeProps {
  confidence?: number // 0-1
  agentUsed?: string
  intent?: string
  reasoningChainId?: number
  compact?: boolean
}

// 置信度档位样式：>=0.8 emerald, >=0.6 amber, <0.6 rose
function confidenceStyle(conf: number | undefined): {
  text: string
  bg: string
  border: string
  dot: string
} {
  if (conf === undefined) {
    return {
      text: 'text-slate-500 dark:text-slate-400',
      bg: 'bg-slate-50 dark:bg-slate-700/40',
      border: 'border-slate-200 dark:border-slate-600',
      dot: 'bg-slate-400',
    }
  }
  if (conf >= 0.8) {
    return {
      text: 'text-emerald-600 dark:text-emerald-400',
      bg: 'bg-emerald-50 dark:bg-emerald-900/20',
      border: 'border-emerald-200 dark:border-emerald-800',
      dot: 'bg-emerald-500',
    }
  }
  if (conf >= 0.6) {
    return {
      text: 'text-amber-600 dark:text-amber-400',
      bg: 'bg-amber-50 dark:bg-amber-900/20',
      border: 'border-amber-200 dark:border-amber-800',
      dot: 'bg-amber-500',
    }
  }
  return {
    text: 'text-rose-600 dark:text-rose-400',
    bg: 'bg-rose-50 dark:bg-rose-900/20',
    border: 'border-rose-200 dark:border-rose-800',
    dot: 'bg-rose-500',
  }
}

// 置信度归一化为百分比（兼容 0-1 与 0-100）
function toPercent(conf: number): number {
  if (Number.isNaN(conf)) return 0
  return conf <= 1 ? conf * 100 : conf
}

// 推理链徽标：紧凑展示置信度、Agent、意图，点击展开更多元信息
export default function AIReasoningBadge({
  confidence,
  agentUsed,
  intent,
  reasoningChainId,
  compact = false,
}: AIReasoningBadgeProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭
  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  const style = confidenceStyle(confidence)
  const pct = confidence !== undefined ? toPercent(confidence) : null

  const toggle = useCallback(() => setOpen((v) => !v), [])

  const hasMetadata = Boolean(agentUsed || intent || reasoningChainId)

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        onClick={hasMetadata ? toggle : undefined}
        disabled={!hasMetadata}
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border ${style.bg} ${style.text} ${style.border} ${
          hasMetadata ? 'cursor-pointer hover:opacity-80' : 'cursor-default'
        } transition-opacity`}
      >
        <Brain className="w-3 h-3" />
        {pct !== null && <span>{pct.toFixed(0)}%</span>}
        {!compact && agentUsed && <span className="truncate max-w-[120px]">{agentUsed}</span>}
        {!compact && intent && (
          <>
            <span className="opacity-40">·</span>
            <span className="truncate max-w-[100px]">{intent}</span>
          </>
        )}
      </button>

      {/* 展开弹出层（fixed 定位，避免 PageHeader overflow-hidden 裁切） */}
      {open && hasMetadata && (
        <div className="fixed z-[60] mt-1 w-56 max-w-[calc(100vw-2rem)] rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xl overflow-hidden"
          style={{ top: 'auto', left: 'auto', right: 16, bottom: 80 }}
        >
          <div className="px-3 py-2 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40">
            <div className="flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
              <Zap className="w-3 h-3 text-brand-500" />
              <span>推理元信息</span>
            </div>
          </div>
          <div className="p-3 space-y-2 text-xs">
            {/* 置信度 */}
            {pct !== null && (
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">置信度</span>
                <span className={`font-medium ${style.text}`}>{pct.toFixed(1)}%</span>
              </div>
            )}
            {/* Agent */}
            {agentUsed && (
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Agent</span>
                <span className="font-medium text-slate-700 dark:text-slate-200 truncate max-w-[120px]">
                  {agentUsed}
                </span>
              </div>
            )}
            {/* 意图 */}
            {intent && (
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">意图</span>
                <span className="font-medium text-slate-700 dark:text-slate-200 truncate max-w-[120px]">
                  {intent}
                </span>
              </div>
            )}
            {/* 推理链 ID */}
            {reasoningChainId !== undefined && (
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">推理链</span>
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  #{reasoningChainId}
                </span>
              </div>
            )}
            {/* 置信度条 */}
            {pct !== null && (
              <div className="pt-1">
                <div className="h-1.5 w-full rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${style.dot}`}
                    style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
