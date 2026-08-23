import { useState, useRef, useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, Send, Loader2, Bot, ChevronDown, ChevronUp } from 'lucide-react'
import PageAIContextBar from './PageAIContextBar'
import ProactiveSuggestions from './ProactiveSuggestions'
import type { Suggestion } from './ProactiveSuggestions'
import { chatSend } from '@/services/ai'
import api from '@/services/api'

/**
 * 业务页 AI 增强布局
 *
 * 统一包装任意业务页：左侧主内容 + 右侧 AI 智能栏。
 * 右侧栏分层：顶部 = AI 洞察摘要；中部 = 上下文建议；底部 = 快捷 AI 提问
 */
interface AIEnhancedPageProps {
  children: ReactNode
  header?: ReactNode
  showSidebar?: boolean
  onSuggestionAction?: (suggestion: Suggestion) => void
}

import type { ReactNode } from 'react'

// Mini-chat 消息
interface MiniMsg {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
}

// Mini-chat 子组件
function MiniChat({ domain }: { domain: string }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<MiniMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const handleSend = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return
    const uid = Math.random().toString(36).slice(2)
    const aid = Math.random().toString(36).slice(2)
    setMessages(prev => [...prev, { id: uid, role: 'user', content: trimmed }])
    setMessages(prev => [...prev, { id: aid, role: 'assistant', content: '', loading: true }])
    setLoading(true)
    setInput('')
    try {
      const res = await chatSend(trimmed, domain)
      setMessages(prev => prev.map(m => m.id === aid ? { ...m, content: res.response || '（AI 未返回）', loading: false } : m))
    } catch (e) {
      setMessages(prev => prev.map(m => m.id === aid ? { ...m, content: `错误：${e instanceof Error ? e.message : '请求失败'}`, loading: false } : m))
    } finally {
      setLoading(false)
    }
  }, [loading, domain])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])

  return (
    <div className="border-t border-slate-200 dark:border-slate-800 shrink-0">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs font-medium text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors"
      >
        <Sparkles className="w-3 h-3" />
        <span>快捷问 AI</span>
        {open ? <ChevronDown className="w-3 h-3 ml-auto" /> : <ChevronUp className="w-3 h-3 ml-auto" />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 space-y-2">
              {/* 消息 */}
              {messages.length > 0 && (
                <div ref={scrollRef} className="max-h-40 overflow-y-auto space-y-2 mb-2">
                  {messages.map(msg => (
                    <div key={msg.id} className={`flex gap-1.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[10px] ${
                        msg.role === 'user' ? 'bg-brand-600 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-500'
                      }`}>
                        {msg.role === 'user' ? 'U' : <Bot className="w-2.5 h-2.5" />}
                      </div>
                      <div className={`max-w-[85%] px-2 py-1 rounded-lg text-xs ${
                        msg.role === 'user'
                          ? 'bg-brand-600 text-white'
                          : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200'
                      }`}>
                        {msg.loading ? (
                          <Loader2 className="w-3 h-3 animate-spin text-slate-400" />
                        ) : (
                          <span className="whitespace-pre-wrap break-words">{msg.content}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 输入 */}
              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSend(input) } }}
                  placeholder="问关于本页的问题..."
                  disabled={loading}
                  className="flex-1 h-7 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-2 text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-brand-500 focus:outline-none disabled:opacity-50"
                />
                <button
                  onClick={() => handleSend(input)}
                  disabled={!input.trim() || loading}
                  className="w-7 h-7 rounded-lg bg-brand-600 text-white flex items-center justify-center hover:bg-brand-700 disabled:opacity-40 transition-colors"
                >
                  <Send className="w-3 h-3" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function AIEnhancedPage({
  children,
  header,
  showSidebar = true,
  onSuggestionAction,
}: AIEnhancedPageProps) {
  const location = useLocation()
  const pathSegments = location.pathname.split('/').filter(Boolean)
  const domain = pathSegments[0] || 'portal'

  // AI 洞察摘要
  const [summary, setSummary] = useState<string | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(true)

  useEffect(() => {
    const insightDomain = domain === 'portal' ? 'decision' : domain
    setSummaryLoading(true)
    setSummary(null)
    api.post<{ data?: { summary?: string } }>(`/${insightDomain}/ai-insights`)
      .then(res => {
        setSummary(res.data?.data?.summary || null)
      })
      .catch(() => setSummary(null))
      .finally(() => setSummaryLoading(false))
  }, [domain])

  return (
    <div className="flex gap-4 h-full">
      {/* 主内容区 */}
      <div className="flex-1 min-w-0 flex flex-col">
        <PageAIContextBar />
        {header}
        <div className="flex-1 min-h-0">
          {children}
        </div>
      </div>

      {/* 右侧 AI 智能栏 */}
      {showSidebar && (
        <aside className="w-80 shrink-0 hidden xl:flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
          {/* 顶部：AI 洞察摘要 */}
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 shrink-0">
            <div className="flex items-center gap-2 mb-1">
              <div className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </div>
              <span className="text-xs font-medium text-brand-700 dark:text-brand-300">AI 洞察</span>
            </div>
            {summaryLoading ? (
              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>AI 分析中...</span>
              </div>
            ) : summary ? (
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">{summary}</p>
            ) : (
              <p className="text-xs text-slate-400">暂无洞察</p>
            )}
          </div>

          {/* 中部：上下文建议 */}
          <div className="flex-1 overflow-auto p-3 min-h-0">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-3.5 h-3.5 text-brand-500" />
              <h3 className="text-xs font-medium text-slate-700 dark:text-slate-200">主动建议</h3>
              <span className="ml-auto text-[10px] text-slate-400">60s 刷新</span>
            </div>
            <ProactiveSuggestions
              domain={domain}
              maxItems={5}
              embedded
              onAction={onSuggestionAction}
            />
          </div>

          {/* 底部：快捷 AI 提问 */}
          <MiniChat domain={domain} />
        </aside>
      )}
    </div>
  )
}
