// F-重构：统一页内 AI 区块——收敛各总览页散落的 AI 洞察渲染
// 兼容后端 /.../ai-insights 通用结构 { summary, insights[], risk_alerts[] }
// 保留"页内呈现"形式（用户决策：不新增全局入口）
import { Sparkles } from 'lucide-react'
import SectionCard from '@/components/layout/SectionCard'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import AIInlineAnnotation from './AIInlineAnnotation'
import type { AiInsightPayload } from '@/types/page'

interface AIInsightBlockProps {
  payload?: AiInsightPayload
  loading?: boolean
  /** i18n key 或文案，默认「AI 洞察」 */
  title?: string
  viewAllTo?: string
  /** 自定义内容（如旧 AIInsightPanel）；传入时优先渲染，忽略 payload */
  children?: React.ReactNode
}

const LEVEL_MAP: Record<string, 'info' | 'warning' | 'success' | 'error'> = {
  info: 'info',
  warning: 'warning',
  success: 'success',
  error: 'error',
}

export default function AIInsightBlock({
  payload,
  loading,
  title = 'AI 洞察',
  viewAllTo,
  children,
}: AIInsightBlockProps) {
  const hasContent =
    payload &&
    (payload.summary ||
      (payload.insights && payload.insights.length > 0) ||
      (payload.risk_alerts && payload.risk_alerts.length > 0))

  return (
    <SectionCard
      title={
        <span className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-brand-500" /> {title}
        </span>
      }
      icon={null}
      viewAllTo={viewAllTo}
    >
      {loading ? (
        <div className="p-5 space-y-3">
          <Skeleton lines={2} />
          <Skeleton lines={1} />
        </div>
      ) : children ? (
        <div className="p-4">{children}</div>
      ) : !hasContent ? (
        <div className="px-5 py-10">
          <Empty description="暂无 AI 洞察" />
        </div>
      ) : (
        <div className="p-4 space-y-2">
          {payload!.summary && (
            <p className="px-3 py-2 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              {payload!.summary}
            </p>
          )}
          {payload!.insights?.map((it, i) => (
            <AIInlineAnnotation
              key={i}
              message={it.message}
              level={LEVEL_MAP[it.level ?? 'info'] ?? 'info'}
            />
          ))}
          {payload!.risk_alerts?.map((it, i) => (
            <AIInlineAnnotation key={`r${i}`} message={it.message} level="warning" />
          ))}
        </div>
      )}
    </SectionCard>
  )
}
