import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle, X, Send, Loader2, Sparkles, Mic } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { chatSend } from '@/services/ai'
import { usePageAIContext } from '@/hooks/usePageAIContext'
import { useAIContextStore } from '@/hooks/useAIContextStack'

interface ChatMsg {
  id: string
  role: 'user' | 'ai'
  content: string
  pending?: boolean
}

/**
 * 全局 AI 快速问答浮动按钮
 *
 * 形态：右下角第二个圆形按钮（与 AISidebar 浮动按钮并排）
 * - 点击展开 mini 弹窗（不占满屏）
 * - 内含：上下文感知输入框 + 3 个动态建议 chip
 * - 始终可用：用户任何问题都能问
 *
 * 这是把"AI 入口"从 1 个（side bar 浮动）扩到 2 个的关键。
 */
export default function AIQuickAsk() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const location = useLocation()
  const { context } = usePageAIContext()
  const contextFragment = useAIContextStore((s) => s.asPromptFragment)
  const scrollRef = useRef<HTMLDivElement>(null)

  // 切换路由时清空历史（避免上下文污染）
  useEffect(() => {
    setMessages([])
  }, [location.pathname])

  // 新消息时滚到底
  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, open])

  // 动态建议（按当前页面生成）
  const suggestions = context
    ? context.actions.slice(0, 3).map(a => a.prompt)
    : [
        '我应该关注哪些指标？',
        '今天有什么需要处理的？',
        '分析一下我近期的表现',
      ]

  const send = async (text?: string) => {
    const content = (text ?? input).trim()
    if (!content || busy) return
    setInput('')

    const userMsg: ChatMsg = { id: `u-${Date.now()}`, role: 'user', content }
    setMessages(prev => [...prev, userMsg])

    const aiMsg: ChatMsg = { id: `a-${Date.now()}`, role: 'ai', content: '', pending: true }
    setMessages(prev => [...prev, aiMsg])
    setBusy(true)

    try {
      // 携带上下文：当前页 + 跨页栈
      const ctx = [
        context ? `【当前页面】${context.pageTitle} (${context.page})` : '',
        contextFragment() ? `【跨页上下文】${contextFragment()}` : '',
      ].filter(Boolean).join('\n')
      const fullPrompt = ctx ? `${content}\n\n${ctx}` : content
      const res = await chatSend(fullPrompt, context?.domain)
      setMessages(prev => prev.map(m => m.id === aiMsg.id ? { ...m, content: res.response, pending: false } : m))
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'AI 请求失败'
      setMessages(prev => prev.map(m => m.id === aiMsg.id ? { ...m, content: `请求失败：${msg}`, pending: false } : m))
    } finally {
      setBusy(false)
    }
  }

  // /ai 路由下隐藏（已有完整聊天面板）
  if (location.pathname.startsWith('/ai')) return null

  return (
    <>
      {/* 浮动按钮 */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-24 z-40 w-14 h-14 rounded-full bg-gradient-to-br from-violet-500 to-brand-500 hover:from-violet-600 hover:to-brand-600 text-white shadow-lg flex items-center justify-center transition-all hover:scale-105"
        title="AI 快速问答"
      >
        <MessageCircle className="w-6 h-6" />
        <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 ring-2 ring-white animate-pulse" />
      </button>

      {/* 弹窗 */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/30 z-[70]"
              onClick={() => setOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[80] w-[26rem] max-w-[calc(100vw-2rem)] h-[36rem] max-h-[calc(100vh-4rem)] rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col"
            >
              {/* 头 */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-gradient-to-r from-violet-50 to-brand-50 dark:from-violet-900/20 dark:to-brand-900/20 shrink-0">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-brand-500 text-white shrink-0">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">
                    AI 快速问答
                  </div>
                  <div className="text-[10px] text-slate-500 truncate">
                    {context ? `当前: ${context.pageTitle}` : '任何问题都能问'}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="p-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700"
                >
                  <X className="w-4 h-4 text-slate-500" />
                </button>
              </div>

              {/* 消息流 */}
              <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
                {messages.length === 0 && (
                  <div className="space-y-2">
                    <div className="text-center text-xs text-slate-400 py-3">
                      {context ? `${context.pageTitle} · 智能助手` : 'AI 随时待命'}
                    </div>
                    {suggestions.map((s, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => send(s)}
                        disabled={busy}
                        className="w-full text-left px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 hover:border-brand-300 text-xs text-slate-700 dark:text-slate-200 transition-colors disabled:opacity-50"
                      >
                        <span className="text-brand-500 mr-1">💡</span>
                        {s.length > 50 ? s.slice(0, 50) + '…' : s}
                      </button>
                    ))}
                  </div>
                )}

                {messages.map(m => (
                  <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] px-3 py-2 rounded-2xl text-xs leading-relaxed ${
                        m.role === 'user'
                          ? 'bg-brand-500 text-white rounded-tr-sm'
                          : 'bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-100 rounded-tl-sm'
                      }`}
                    >
                      {m.pending ? (
                        <div className="flex items-center gap-1.5">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          <span>思考中…</span>
                        </div>
                      ) : (
                        <div className="whitespace-pre-wrap break-words">{m.content}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* 输入区 */}
              <div className="border-t border-slate-200 dark:border-slate-800 p-3 shrink-0">
                <div className="flex items-end gap-2">
                  <textarea
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        send()
                      }
                    }}
                    placeholder="问 AI 任何问题…"
                    rows={1}
                    className="flex-1 resize-none px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  />
                  <button
                    type="button"
                    onClick={() => send()}
                    disabled={busy || !input.trim()}
                    className="shrink-0 flex items-center justify-center w-9 h-9 rounded-lg bg-brand-500 hover:bg-brand-600 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </button>
                </div>
                <div className="mt-1.5 text-[10px] text-slate-400 text-center">
                  Enter 发送 · Shift+Enter 换行 · 上下文自动附加
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
