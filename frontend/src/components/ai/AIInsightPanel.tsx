import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles,
  Brain,
  AlertCircle,
  RefreshCw,
  ChevronDown,
  Lightbulb,
  Bot,
} from 'lucide-react'
import api from '@/services/api'
import type { ApiResponse } from '@/types'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'

// 洞察级别
type InsightLevel = 'info' | 'warning' | 'error' | 'success'

// 单条洞察
interface Insight {
  type?: string
  level: InsightLevel
  message: string
}

// 风险告警
interface RiskAlert {
  type?: string
  level?: string
  message: string
  [key: string]: unknown
}

// 洞察响应数据
interface InsightData {
  summary: string
  insights: Insight[]
  recommendations: string[]
  risk_alerts: RiskAlert[]
}

interface AIInsightPanelProps {
  domain: string
  title?: string
  className?: string
}

// level 样式映射：warning=amber, info=sky, error=rose, success=emerald
const levelStyles: Record<InsightLevel, { bg: string; text: string; border: string }> = {
  info: {
    bg: 'bg-sky-50 dark:bg-sky-900/20',
    text: 'text-sky-600 dark:text-sky-400',
    border: 'border-sky-200 dark:border-sky-800',
  },
  warning: {
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    text: 'text-amber-600 dark:text-amber-400',
    border: 'border-amber-200 dark:border-amber-800',
  },
  error: {
    bg: 'bg-rose-50 dark:bg-rose-900/20',
    text: 'text-rose-600 dark:text-rose-400',
    border: 'border-rose-200 dark:border-rose-800',
  },
  success: {
    bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    text: 'text-emerald-600 dark:text-emerald-400',
    border: 'border-emerald-200 dark:border-emerald-800',
  },
}

// 风险告警统一使用 rose
const riskStyle = {
  bg: 'bg-rose-50 dark:bg-rose-900/20',
  text: 'text-rose-600 dark:text-rose-400',
  border: 'border-rose-200 dark:border-rose-800',
}

// 归一化 level：未知值回退为 info
function normalizeLevel(level: string | undefined): InsightLevel {
  const valid: InsightLevel[] = ['info', 'warning', 'error', 'success']
  if (level && (valid as string[]).includes(level)) return level as InsightLevel
  return 'info'
}

// 将 recommendations 归一化为字符串数组：
// 后端 AI 原生的 recommendations 每项可能是对象 {action, priority, rationale, confidence, needs_human_review}，
// 也可能是纯字符串。统一抽取可读文案，避免把对象直接当 React child 渲染。
function normalizeRecommendations(raw: unknown): string[] {
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    if (typeof item === 'string') return item
    if (item && typeof item === 'object') {
      const obj = item as Record<string, unknown>
      const action = typeof obj.action === 'string' ? obj.action : ''
      const rationale = typeof obj.rationale === 'string' ? obj.rationale : ''
      const text = [action, rationale].filter(Boolean).join('：')
      return text || JSON.stringify(obj)
    }
    return String(item)
  })
}

// 获取 AI 洞察数据
async function fetchInsights(domain: string): Promise<InsightData> {
  const res = await api.post<ApiResponse<InsightData>>(`/${domain}/ai-insights`)
  const data = res.data.data
  return {
    summary: data?.summary ?? '',
    insights: Array.isArray(data?.insights) ? data.insights : [],
    recommendations: normalizeRecommendations(data?.recommendations),
    risk_alerts: Array.isArray(data?.risk_alerts) ? data.risk_alerts : [],
  }
}

// N+AI原生闭环：经编排器 insight 意图获取 AI 原生洞察
async function fetchAiInsights(domain: string): Promise<InsightData> {
  const res = await api.get<ApiResponse<InsightData>>(`/ai/insight/ai?domain=${encodeURIComponent(domain)}`)
  const data = res.data.data ?? res.data
  return {
    summary: data?.summary ?? '',
    insights: Array.isArray(data?.insights) ? data.insights : [],
    recommendations: normalizeRecommendations(data?.recommendations),
    risk_alerts: Array.isArray(data?.risk_alerts) ? data.risk_alerts : [],
  }
}

// AI 洞察面板组件
export default function AIInsightPanel({
  domain,
  title = 'AI 洞察',
  className = '',
}: AIInsightPanelProps) {
  const [aiMode, setAiMode] = useState(false)
  const [data, setData] = useState<InsightData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [expanded, setExpanded] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = aiMode ? await fetchAiInsights(domain) : await fetchInsights(domain)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setLoading(false)
    }
  }, [domain, aiMode])

  // 刷新（不触发整体 loading，仅旋转图标）
  const handleRefresh = useCallback(async () => {
    if (refreshing) return
    setRefreshing(true)
    setError(null)
    try {
      const result = aiMode ? await fetchAiInsights(domain) : await fetchInsights(domain)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setRefreshing(false)
    }
  }, [domain, refreshing, aiMode])

  useEffect(() => {
    load()
  }, [load])

  const isEmpty =
    !data ||
    (!data.summary &&
      data.insights.length === 0 &&
      data.recommendations.length === 0 &&
      data.risk_alerts.length === 0)

  return (
    <div
      className={`rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 ${className}`}
    >
      {/* 头部：标题 + 刷新 + 展开/收起 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-700">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 flex-1 min-w-0 text-left"
        >
          <Sparkles className="w-4 h-4 text-brand-500 shrink-0" />
          <span className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
            {title}
          </span>
          <ChevronDown
            className={`w-4 h-4 text-slate-400 transition-transform shrink-0 ${expanded ? 'rotate-180' : ''}`}
          />
        </button>
        <button
          type="button"
          onClick={() => setAiMode((v) => !v)}
          className={`p-1.5 rounded-lg transition-colors shrink-0 ${
            aiMode
              ? 'bg-brand-500/15 text-brand-600 dark:text-brand-300'
              : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700'
          }`}
          title="经 AI 编排器生成洞察"
        >
          <Bot className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          title="刷新"
          className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* 内容区 */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 py-3 space-y-3">
              {/* 加载中 */}
              {loading && <Skeleton lines={4} />}

              {/* 错误 */}
              {!loading && error && (
                <div className="flex items-center gap-2 text-sm text-rose-500">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error.message}</span>
                </div>
              )}

              {/* 空状态 */}
              {!loading && !error && isEmpty && (
                <Empty description="暂无 AI 洞察" />
              )}

              {/* 数据展示 */}
              {!loading && !error && !isEmpty && data && (
                <>
                  {/* 摘要 */}
                  {data.summary && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800">
                      <Brain className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
                      <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                        {data.summary}
                      </p>
                    </div>
                  )}

                  {/* 风险告警（置顶） */}
                  {data.risk_alerts.length > 0 && (
                    <div className="space-y-2">
                      {data.risk_alerts.map((alert, idx) => (
                        <div
                          key={`risk-${idx}`}
                          className={`flex items-start gap-2 p-2.5 rounded-lg border ${riskStyle.bg} ${riskStyle.border}`}
                        >
                          <AlertCircle className={`w-4 h-4 shrink-0 mt-0.5 ${riskStyle.text}`} />
                          <div className="flex-1 min-w-0">
                            <span className={`text-xs font-medium ${riskStyle.text}`}>
                              风险告警
                            </span>
                            <p className="text-sm text-slate-700 dark:text-slate-200 mt-0.5">
                              {alert.message}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 洞察列表 */}
                  {data.insights.length > 0 && (
                    <div className="space-y-2">
                      {data.insights.map((insight, idx) => {
                        const lv = normalizeLevel(insight.level)
                        const style = levelStyles[lv]
                        return (
                          <div
                            key={`insight-${idx}`}
                            className={`flex items-start gap-2 p-2.5 rounded-lg border ${style.bg} ${style.border}`}
                          >
                            <Sparkles className={`w-4 h-4 shrink-0 mt-0.5 ${style.text}`} />
                            <div className="flex-1 min-w-0">
                              {insight.type && (
                                <span className={`text-xs font-medium ${style.text}`}>
                                  {insight.type}
                                </span>
                              )}
                              <p className="text-sm text-slate-700 dark:text-slate-200 mt-0.5">
                                {insight.message}
                              </p>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {/* 建议列表 */}
                  {data.recommendations.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">
                        <Lightbulb className="w-3.5 h-3.5" />
                        <span>建议</span>
                      </div>
                      {data.recommendations.map((rec, idx) => (
                        <div
                          key={`rec-${idx}`}
                          className="flex items-start gap-2 pl-2 text-sm text-slate-600 dark:text-slate-300"
                        >
                          <span className="text-slate-400 shrink-0">{idx + 1}.</span>
                          <span className="leading-relaxed">{rec}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
