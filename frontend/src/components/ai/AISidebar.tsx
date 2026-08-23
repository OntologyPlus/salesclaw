import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, User, Send, X, Loader2, AlertCircle, History, ArrowRight } from 'lucide-react'
import { useAIStream } from '@/hooks/useAIStream'
import { useAIContextStore } from '@/hooks/useAIContextStack'
import ReasoningChainView from '@/components/ai/ReasoningChainView'

interface AISidebarProps {
  open: boolean
  onClose: () => void
  contextPrompt?: string
}

// 聊天消息
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  pending?: boolean
  error?: string
  agentUsed?: string
  intent?: string
  reasoningChainId?: number
  reasoning?: string
}

// 生成简单唯一 ID
function genId(): string {
  return Math.random().toString(36).slice(2, 11)
}

// 从事件数据中提取元信息
function extractMetadata(events: { type: string; data: unknown }[]): {
  agentUsed?: string
  intent?: string
  reasoningChainId?: number
  errorMsg?: string
} {
  let agentUsed: string | undefined
  let intent: string | undefined
  let reasoningChainId: number | undefined
  let errorMsg: string | undefined

  for (const evt of events) {
    const d =
      evt.data && typeof evt.data === 'object'
        ? (evt.data as Record<string, unknown>)
        : null
    if (evt.type === 'intent' && d) {
      if (typeof d.agent === 'string') agentUsed = d.agent
      if (typeof d.intent === 'string') intent = d.intent
    }
    if (d) {
      if (typeof d.reasoning_chain_id === 'number') reasoningChainId = d.reasoning_chain_id
      else if (typeof d.chain_id === 'number' && reasoningChainId === undefined)
        reasoningChainId = d.chain_id
    }
    if (evt.type === 'error' && d) {
      errorMsg = typeof d.message === 'string' ? d.message : 'AI 请求失败'
    }
  }
  return { agentUsed, intent, reasoningChainId, errorMsg }
}

// AI 侧边栏：右侧滑出面板，复用 useAIStream 实现流式聊天
export default function AISidebar({ open, onClose, contextPrompt }: AISidebarProps) {
  const { streamMessage, isStreaming, events, currentResponse, currentReasoning, reset } =
    useAIStream()

  // 跨页 AI 上下文栈
  const contextStack = useAIContextStore((s) => s.stack)
  const popContext = useAIContextStore((s) => s.pop)
  const clearContext = useAIContextStore((s) => s.clear)
  const contextFragment = useAIContextStore((s) => s.asPromptFragment)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const streamingIdRef = useRef<string | null>(null)
  const initialSentRef = useRef(false)

  // 发送消息
  const handleSend = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming) return

      const userMsg: ChatMessage = { id: genId(), role: 'user', content: trimmed }
      const aiId = genId()
      const aiMsg: ChatMessage = {
        id: aiId,
        role: 'assistant',
        content: '',
        pending: true,
      }
      streamingIdRef.current = aiId

      setMessages((prev) => [...prev, userMsg, aiMsg])

      try {
        await streamMessage(trimmed)
      } catch {
        // 错误由 events 处理
      }
    },
    [isStreaming, streamMessage]
  )

  // 同步流式响应到最新 assistant 消息
  useEffect(() => {
    const id = streamingIdRef.current
    if (!id) return
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id
          ? {
              ...m,
              content: currentResponse,
              reasoning: currentReasoning,
              pending: isStreaming,
            }
          : m
      )
    )
    // 流式结束时清理 ref
    if (!isStreaming) {
      streamingIdRef.current = null
    }
  }, [currentResponse, currentReasoning, isStreaming])

  // 从 events 提取元信息（agent / intent / reasoningChainId / error）
  useEffect(() => {
    if (events.length === 0) return
    const id = streamingIdRef.current
    if (!id) return
    const { agentUsed, intent, reasoningChainId, errorMsg } = extractMetadata(events)
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id
          ? {
              ...m,
              agentUsed: agentUsed ?? m.agentUsed,
              intent: intent ?? m.intent,
              reasoningChainId: reasoningChainId ?? m.reasoningChainId,
              error: errorMsg ?? m.error,
            }
          : m
      )
    )
  }, [events])

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // 打开时自动发送 contextPrompt（仅一次）
  useEffect(() => {
    if (open && contextPrompt && !initialSentRef.current && !isStreaming) {
      initialSentRef.current = true
      void handleSend(contextPrompt)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, contextPrompt])

  // 关闭时重置状态
  useEffect(() => {
    if (!open) {
      initialSentRef.current = false
      reset()
      setMessages([])
      setInput('')
    }
  }, [open, reset])

  // 提交输入
  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (!input.trim() || isStreaming) return
      handleSend(input)
      setInput('')
    },
    [input, isStreaming, handleSend]
  )

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* 遮罩层 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-slate-900/30"
          />

          {/* 侧边栏面板 */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.25, ease: [0.19, 1, 0.22, 1] }}
            className="fixed top-0 right-0 bottom-0 z-50 w-[400px] max-w-[calc(100vw-2rem)] flex flex-col bg-white dark:bg-slate-900 shadow-2xl border-l border-slate-200 dark:border-slate-800"
          >
            {/* 顶部：标题 + 关闭按钮 */}
            <div className="flex items-center gap-2 px-4 h-14 border-b border-slate-200 dark:border-slate-800 shrink-0">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-500 text-white shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <span className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-200">
                AI 助手
              </span>
              <button
                type="button"
                onClick={onClose}
                title="关闭"
                className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* 跨页 AI 上下文栈（轻记忆） */}
            {contextStack.length > 0 && (
              <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-800 bg-gradient-to-r from-brand-50/50 to-violet-50/50 dark:from-brand-900/10 dark:to-violet-900/10 shrink-0">
                <div className="flex items-center gap-1.5 mb-1">
                  <History className="w-3 h-3 text-slate-400" />
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase tracking-wide">当前上下文</span>
                  <button
                    type="button"
                    onClick={clearContext}
                    className="ml-auto text-[10px] text-slate-400 hover:text-rose-500"
                  >
                    清除
                  </button>
                </div>
                <div className="flex items-center gap-1 overflow-x-auto">
                  {contextStack.map((item, idx) => (
                    <div key={item.id} className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={() => popContext(item.id)}
                        className="px-1.5 py-0.5 text-[10px] rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:border-brand-300"
                        title={`移除 ${item.pageTitle}`}
                      >
                        {item.pageTitle}
                      </button>
                      {idx < contextStack.length - 1 && (
                        <ArrowRight className="w-3 h-3 text-slate-300 shrink-0" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 中部：消息列表 */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-100 to-violet-100 dark:from-brand-900/30 dark:to-violet-900/30 mb-3">
                    <Bot className="w-8 h-8 text-brand-500" />
                  </div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                    AI 助手已就绪
                  </p>
                  <p className="mt-1 text-xs text-slate-400">输入你的问题，让我来帮你</p>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                  >
                    {/* 头像 */}
                    <div
                      className={`flex items-center justify-center w-8 h-8 rounded-lg shrink-0 ${
                        msg.role === 'user'
                          ? 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                          : 'bg-gradient-to-br from-brand-500 to-violet-500 text-white'
                      }`}
                    >
                      {msg.role === 'user' ? (
                        <User className="w-4 h-4" />
                      ) : (
                        <Bot className="w-4 h-4" />
                      )}
                    </div>

                    {/* 消息内容 */}
                    <div
                      className={`flex-1 min-w-0 ${
                        msg.role === 'user' ? 'flex flex-col items-end' : ''
                      }`}
                    >
                      <div
                        className={`inline-block px-3 py-2 rounded-2xl text-sm ${
                          msg.role === 'user'
                            ? 'bg-brand-600 text-white rounded-tr-sm'
                            : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-tl-sm'
                        }`}
                      >
                        {msg.pending && !msg.content ? (
                          <span className="flex items-center gap-1.5 text-slate-400">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" /> 思考中...
                          </span>
                        ) : msg.error ? (
                          <span className="flex items-center gap-1.5 text-rose-500">
                            <AlertCircle className="w-3.5 h-3.5" /> {msg.error}
                          </span>
                        ) : (
                          <span className="whitespace-pre-wrap break-words">{msg.content}</span>
                        )}
                      </div>

                      {/* Agent / Intent 标签 */}
                      {msg.role === 'assistant' && (msg.agentUsed || msg.intent) && !msg.pending && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {msg.agentUsed && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-xs font-medium bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
                              agent: {msg.agentUsed}
                            </span>
                          )}
                          {msg.intent && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-xs font-medium bg-violet-100 text-violet-700 dark:bg-violet-900/20 dark:text-violet-400">
                              {msg.intent}
                            </span>
                          )}
                        </div>
                      )}

                      {/* 推理链展示 */}
                      {msg.role === 'assistant' &&
                        !msg.pending &&
                        !msg.error &&
                        msg.reasoningChainId !== undefined && (
                          <div className="mt-2">
                            <ReasoningChainView
                              chainId={msg.reasoningChainId}
                              className="!border-slate-200 dark:!border-slate-700"
                            />
                          </div>
                        )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* 底部：输入框 + 发送按钮 */}
            <form
              onSubmit={handleSubmit}
              className="p-3 border-t border-slate-200 dark:border-slate-800 shrink-0"
            >
              <div className="flex items-end gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSubmit(e)
                    }
                  }}
                  rows={1}
                  placeholder="输入消息，Enter 发送..."
                  className="flex-1 max-h-32 resize-none rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isStreaming}
                  className="flex items-center justify-center w-10 h-10 rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
