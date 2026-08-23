import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, X, Loader2, Wand2, ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { usePageAIContext, type PageAIAction } from '@/hooks/usePageAIContext'
import { useAIContextStore } from '@/hooks/useAIContextStack'
import { chatSend } from '@/services/ai'
import api from '@/services/api'
import { useToast } from '@/hooks/useToast'

// 实时洞察气泡
interface Insight {
  level: 'info' | 'warning' | 'success'
  message: string
}

/**
 * 页面 AI 上下文栏（升级版）
 *
 * 视觉锚点：每进一个业务页，PageHeader 上方都有一条"AI 在场"状态条。
 * - 左侧：AI 状态脉冲点 + 当前页可用的 AI 操作 chip
 * - 中部：实时洞察 marquee（多条洞察轮播）
 * - 右侧：快捷跳转到该页对应的 ChatPage
 *
 * 高度 ~44px，视觉权重适中，不抢主内容。
 */
export default function PageAIContextBar() {
  const { context } = usePageAIContext()
  const [insights, setInsights] = useState<Insight[]>([])
  const [loading, setLoading] = useState(false)
  const [busyActionId, setBusyActionId] = useState<string | null>(null)
  const [cardOpen, setCardOpen] = useState(false)
  const [cardResult, setCardResult] = useState<{ action: PageAIAction; content: string } | null>(null)
  const navigate = useNavigate()
  const toast = useToast()
  const abortRef = useRef(false)
  const pushContext = useAIContextStore((s) => s.push)

  // 进入页面时 push 到跨页 AI 上下文栈
  useEffect(() => {
    if (context) {
      pushContext({ page: context.page, pageTitle: context.pageTitle })
    }
  }, [context?.page, pushContext])

  // 拉取本页洞察（一次/页进入）
  useEffect(() => {
    if (!context) return
    // 后端 ai-insights 已支持的域（白名单，避免 404）
    // 注意：后端没有 /portal/ai-insights 端点，portal 复用 decision
    const SUPPORTED_DOMAINS = new Set([
      'sales', 'training', 'decision', 'collab', 'knowledge', 'crm',
      'cfm', 'tools', 'platform', 'mdm',
    ])
    // 优先用 page 路径第一段（后端路由约定），portal 复用 decision 内容
    const rawDomain = context.page.split('/')[1] || context.domain
    const insightDomain =
      rawDomain === 'portal' ? 'decision' :
      SUPPORTED_DOMAINS.has(rawDomain) ? rawDomain :
      SUPPORTED_DOMAINS.has(context.domain) ? context.domain : 'decision'
    abortRef.current = false
    setLoading(true)
    setInsights([])
    api.post<{ data?: { summary?: string; insights?: Insight[]; risk_alerts?: Insight[] } }>(`/${insightDomain}/ai-insights`)
      .then(res => {
        if (abortRef.current) return
        const d = res.data?.data
        const allInsights: Insight[] = [
          ...(d?.risk_alerts ?? []).map(r => ({ level: (r.level || 'warning') as Insight['level'], message: r.message })),
          ...(d?.insights ?? []).map(r => ({ level: (r.level || 'info') as Insight['level'], message: r.message })),
        ]
        if (d?.summary && allInsights.length === 0) {
          allInsights.push({ level: 'info', message: d.summary })
        }
        setInsights(allInsights.length > 0 ? allInsights : [{ level: 'info', message: 'AI 已就绪，等待分析数据...' }])
      })
      .catch(() => {
        if (!abortRef.current) setInsights([{ level: 'info', message: 'AI 正在学习你的数据...' }])
      })
      .finally(() => {
        if (!abortRef.current) setLoading(false)
      })
    return () => { abortRef.current = true }
  }, [context?.page, context?.domain])

  if (!context) return null

  const handleAction = async (action: PageAIAction) => {
    setBusyActionId(action.id)
    try {
      const res = await chatSend(action.prompt, context.domain)
      setCardResult({ action, content: res.response || '（无返回）' })
      setCardOpen(true)
    } catch (e) {
      toast('AI 响应失败，请稍后再试', 'error')
    } finally {
      setBusyActionId(null)
    }
  }

  const chatPageMap: Record<string, string> = {
    '/sales/visit-plans': '/sales/visit-plan',
    '/training/courses': '/training/scene-create',
    '/decision/alert-disposition': '/decision/alert-disposition',
  }
  const chatPageHref = chatPageMap[context.page]

  // 构建 marquee 内容（重复一次实现无缝滚动）
  const marqueeInsights = insights.length > 0 ? [...insights, ...insights] : []

  return (
    <>
      {/* 状态条 */}
      <div className="relative flex items-center gap-3 px-4 h-11 rounded-xl bg-gradient-to-r from-brand-50/80 via-white to-brand-50/80 dark:from-brand-900/20 dark:via-slate-800 dark:to-brand-900/20 border border-brand-200/50 dark:border-brand-800/30 mb-3 overflow-hidden">
        {/* AI 分析中进度条 */}
        {loading && (
          <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-100 dark:bg-brand-900/30 overflow-hidden">
            <div className="h-full w-1/3 bg-gradient-to-r from-transparent via-brand-500 to-transparent ai-progress-shimmer" />
          </div>
        )}

        {/* 左：AI 状态脉冲 + 操作 chip */}
        <div className="flex items-center gap-2 shrink-0">
          {/* AI 脉冲点 */}
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
          <span className="text-xs font-medium text-brand-700 dark:text-brand-300">AI 在场</span>
          <span className="text-slate-300 dark:text-slate-600">|</span>

          {/* AI 操作 chip */}
          {context.actions.slice(0, 3).map((a) => {
            const Icon = a.icon
            const busy = busyActionId === a.id
            return (
              <button
                key={a.id}
                onClick={() => handleAction(a)}
                disabled={busy}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium text-slate-700 dark:text-slate-200 bg-white/80 dark:bg-slate-700/60 hover:bg-white dark:hover:bg-slate-700 hover:shadow-sm border border-slate-200/60 dark:border-slate-600/40 transition-all shrink-0 disabled:opacity-50"
                title={a.prompt}
              >
                {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Icon className="w-3 h-3 text-brand-500" />}
                <span>{a.label.replace(/^AI /, '')}</span>
              </button>
            )
          })}
        </div>

        {/* 中：洞察 marquee */}
        <div className="flex-1 min-w-0 overflow-hidden relative">
          {loading && insights.length === 0 ? (
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>AI 正在分析本页数据...</span>
            </div>
          ) : (
            <div className="flex ai-marquee whitespace-nowrap">
              {marqueeInsights.map((insight, idx) => (
                <span key={idx} className="inline-flex items-center gap-1.5 mx-4 text-xs">
                  <span className={`shrink-0 w-1.5 h-1.5 rounded-full ${
                    insight.level === 'warning' ? 'bg-amber-500' :
                    insight.level === 'success' ? 'bg-emerald-500' : 'bg-sky-500'
                  }`} />
                  <span className="text-slate-600 dark:text-slate-300">{insight.message}</span>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 右：高级入口 */}
        {chatPageHref && (
          <button
            onClick={() => navigate(chatPageHref)}
            className="flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-900/30 hover:bg-brand-100 dark:hover:bg-brand-900/50 shrink-0 transition-colors"
          >
            <Wand2 className="w-3 h-3" />
            <span>高级工作流</span>
            <ChevronRight className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* AI 响应卡片 */}
      <AnimatePresence>
        {cardOpen && cardResult && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/30 z-[70]"
              onClick={() => setCardOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.97 }}
              className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[80] w-[32rem] max-w-[calc(100vw-2rem)] max-h-[80vh] rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col"
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-brand-500" />
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-100">
                    {cardResult.action.label}
                  </span>
                </div>
                <button onClick={() => setCardOpen(false)} className="p-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700">
                  <X className="w-4 h-4 text-slate-500" />
                </button>
              </div>
              <div className="flex-1 overflow-auto p-4 text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
                {cardResult.content}
              </div>
              <div className="px-4 py-2 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 text-xs text-slate-500 flex items-center justify-between">
                <span>来自 {context.pageTitle} 上下文</span>
                <span>已应用 AI · 30s 内可调整</span>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}

