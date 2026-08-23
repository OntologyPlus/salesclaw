import { useState } from 'react'
import { TrendingUp, TrendingDown, Sparkles, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { chatSend } from '@/services/ai'

// F8：配色从 8 色收敛到 4 色（brand/emerald/amber/rose）
type Color = 'brand' | 'emerald' | 'amber' | 'rose'

interface StatCardProps {
  title: string
  value: string | number
  icon: ReactNode
  // F8：接受 4 色或旧色名（向后兼容，旧色名自动映射）
  color?: Color | (string & {})
  trend?: number
  sparkline?: number[]
  /** AI 一句话解读（显示在数值下方） */
  aiInsight?: string
  /** AI 标记为异常（左边框呼吸动画） */
  aiAlert?: boolean
}

const colorMap: Record<Color, string> = {
  brand: 'bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400',
  emerald: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400',
  amber: 'bg-amber-100 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400',
  rose: 'bg-rose-100 text-rose-600 dark:bg-rose-900/20 dark:text-rose-400',
}

// F8：向后兼容映射（旧颜色名 → 新 4 色之一）
const legacyColorMap: Record<string, Color> = {
  blue: 'brand',
  cyan: 'brand',
  pink: 'rose',
  violet: 'rose',
}

function resolveColor(color?: Color | string): Color {
  if (!color) return 'brand'
  if (color in colorMap) return color as Color
  return legacyColorMap[color] || 'brand'
}

// 统计卡片，支持趋势、迷你折线、AI 微解读、AI 异常警报
export default function StatCard({ title, value, icon, color, trend, aiInsight, aiAlert }: StatCardProps) {
  const resolvedColor = resolveColor(color)
  const [expanded, setExpanded] = useState(false)
  const [detailContent, setDetailContent] = useState<string | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const handleAskAI = async () => {
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (detailContent || detailLoading) return
    setDetailLoading(true)
    try {
      const prompt = `请简洁分析这个指标：\n指标：${title}\n当前值：${value}\n${trend !== undefined ? `趋势：${trend > 0 ? '+' : ''}${trend}%` : ''}\n用 2-3 句话说明：1) 这个值代表什么 2) 趋势是否正常 3) 有什么建议`
      const res = await chatSend(prompt)
      setDetailContent(res.response || '（AI 未返回）')
    } catch (e) {
      setDetailContent(e instanceof Error ? `失败：${e.message}` : '失败')
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <div
      className={`relative p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark transition-all hover:shadow-md ${
        aiAlert
          ? 'ai-alert-border border-l-[3px] border-amber-400 dark:border-amber-500'
          : 'border-slate-200 dark:border-[rgba(120,100,75,0.15)]'
      }`}
    >
      {/* AI 异常标记 */}
      {aiAlert && (
        <div className="absolute top-2 right-2">
          <span className="flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
          </span>
        </div>
      )}

      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-500 dark:text-slate-400">{title}</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
        </div>
        <div className={`flex items-center justify-center w-10 h-10 rounded-xl ${colorMap[resolvedColor]} shrink-0`}>
          {icon}
        </div>
      </div>

      {typeof trend === 'number' && (
        <div className="mt-3 flex items-center gap-1 text-xs">
          {trend >= 0 ? (
            <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
          ) : (
            <TrendingDown className="w-3.5 h-3.5 text-rose-500" />
          )}
          <span className={trend >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}>
            {Math.abs(trend)}%
          </span>
          <span className="text-slate-400">较上周</span>
        </div>
      )}

      {/* AI 微解读 */}
      {aiInsight && (
        <div className="mt-2 flex items-start gap-1.5 text-xs text-slate-500 dark:text-slate-400">
          <Sparkles className="w-3 h-3 text-brand-500 shrink-0 mt-0.5" />
          <span className="line-clamp-2 leading-relaxed">{aiInsight}</span>
        </div>
      )}

      {/* AI 深度分析展开区 */}
      {(aiInsight || aiAlert) && (
        <div className="mt-2">
          <button
            type="button"
            onClick={handleAskAI}
            className="flex items-center gap-1 text-xs text-brand-600 dark:text-brand-400 hover:text-brand-700 dark:hover:text-brand-300 transition-colors"
          >
            <Sparkles className="w-3 h-3" />
            <span>{expanded ? '收起分析' : 'AI 深度分析'}</span>
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          {expanded && (
            <div className="mt-2 p-2.5 rounded-lg bg-slate-50 dark:bg-surface-raised-dark text-xs text-slate-600 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
              {detailLoading ? (
                <div className="flex items-center gap-1.5 text-slate-400">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>AI 正在分析...</span>
                </div>
              ) : (
                detailContent
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
