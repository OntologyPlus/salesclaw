import { useState, useRef, useEffect, useMemo } from 'react'
import { Bot, Send, Sparkles, User, Zap, Brain, StopCircle } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import ProactiveSuggestions from '@/components/ai/ProactiveSuggestions'
import ReasoningChainView from '@/components/ai/ReasoningChainView'
import { useAIStream, type AIStreamEvent } from '@/hooks/useAIStream'

// 聊天消息
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  // 关联的推理链 ID（assistant 消息可能携带）
  reasoningChainId?: number
  // 意图与路由元信息（来自 SSE intent/routing 事件）
  intent?: string
  agent?: string
  // 流式状态标记
  streaming?: boolean
  // 安全阀拦截标记
  safetyBlocked?: boolean
  // 缓存命中标记
  cacheHit?: boolean
  // 匹配的 Skill 名称
  skillUsed?: string
  // Nemotron 思考链内容
  reasoningContent?: string
}

// 快捷建议
const quickSuggestions = [
  '推荐学习路径',
  '生成本周拜访计划',
  '分析客户反馈',
  '查看 KPI 概览',
]

// 生成简单 id
function genId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

// 从 SSE 事件中提取字段
function extractEventField<T>(evt: AIStreamEvent | undefined, field: string): T | undefined {
  if (!evt || !evt.data || typeof evt.data !== 'object') return undefined
  const obj = evt.data as Record<string, unknown>
  return obj[field] as T | undefined
}

export default function AIAssistantPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | undefined>(undefined)
  const scrollRef = useRef<HTMLDivElement>(null)
  // 当前正在流式生成的 assistant 消息 ID
  const streamingMsgIdRef = useRef<string | null>(null)

  const { streamMessage, isStreaming, events, currentResponse, currentReasoning, reset } = useAIStream()

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, currentResponse, isStreaming])

  // 处理 SSE 事件流：累积到当前 streaming 消息
  useEffect(() => {
    if (!streamingMsgIdRef.current) return
    const msgId = streamingMsgIdRef.current

    // 找到最新的事件（按事件类型处理）
    // 这里采用遍历方式，确保事件按顺序应用
    const latestIntentEvt = events.find((e) => e.type === 'intent')
    const latestRoutingEvt = events.find((e) => e.type === 'routing')
    const latestDoneEvt = events.find((e) => e.type === 'done')
    const errorEvt = events.find((e) => e.type === 'error')

    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId) return m
        return {
          ...m,
          content: currentResponse,
          reasoningContent: currentReasoning || m.reasoningContent,
          skillUsed: extractEventField<string>(latestDoneEvt, 'skill_used') ?? m.skillUsed,
          intent: extractEventField<string>(latestIntentEvt, 'intent') ?? m.intent,
          agent: extractEventField<string>(latestRoutingEvt, 'agent') ?? m.agent,
          cacheHit: extractEventField<boolean>(latestDoneEvt, 'cache_hit') ?? m.cacheHit,
          streaming: !latestDoneEvt && !errorEvt,
          safetyBlocked: false,
        }
      })
    )

    // done 事件：记录推理链 ID 与 session_id
    if (latestDoneEvt) {
      const chainId = extractEventField<number>(latestDoneEvt, 'reasoning_chain_id')
      const sid = extractEventField<string>(latestDoneEvt, 'session_id')
      if (sid && !sessionId) setSessionId(sid)
      if (chainId) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId ? { ...m, reasoningChainId: chainId, streaming: false } : m
          )
        )
      }
      streamingMsgIdRef.current = null
    }

    // error 事件
    if (errorEvt) {
      const errMsg = extractEventField<string>(errorEvt, 'message') ?? '流式请求失败'
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? { ...m, content: m.content || `抱歉，发生错误：${errMsg}`, streaming: false }
            : m
        )
      )
      streamingMsgIdRef.current = null
    }
  }, [events, currentResponse, sessionId])

  // 发送消息（流式）
  const handleSend = async (text?: string) => {
    const content = (text ?? input).trim()
    if (!content || isStreaming) return

    const userMsg: ChatMessage = { id: genId(), role: 'user', content }
    const assistantMsg: ChatMessage = {
      id: genId(),
      role: 'assistant',
      content: '',
      streaming: true,
    }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')
    streamingMsgIdRef.current = assistantMsg.id

    try {
      await streamMessage(content, undefined, sessionId)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '请求失败'
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? { ...m, content: m.content || `抱歉，发生错误：${msg}`, streaming: false }
            : m
        )
      )
    }
  }

  // 中断流式
  const handleAbort = () => {
    reset()
    if (streamingMsgIdRef.current) {
      const msgId = streamingMsgIdRef.current
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? { ...m, streaming: false, content: m.content || '（已中断）' }
            : m
        )
      )
      streamingMsgIdRef.current = null
    }
  }

  // 按回车发送
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  // 当前正在流式的消息（用于显示 typing 指示器）
  const streamingMessage = useMemo(
    () => messages.find((m) => m.streaming),
    [messages]
  )

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)]">
      <PageHeader
        title="AI 助手"
        description="七步状态机 · SSE 流式 · 推理链可视化 · 主动建议"
        breadcrumbs={[{ label: 'AI 助手' }]}
        icon={<Bot className="w-5 h-5" />}
        gradient
      />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-0">
        {/* 左侧：聊天区域（占 2/3） */}
        <div className="lg:col-span-2 flex flex-col rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
          {/* 消息列表 */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-slate-400">
                <Bot className="w-12 h-12 mb-3 text-brand-400" />
                <p className="text-sm">你好，我是 AI 助手，有什么可以帮你的吗？</p>
                <p className="text-xs mt-1 text-slate-400">
                  支持流式输出 · 推理链可视化 · 安全护栏
                </p>
              </div>
            ) : (
              messages.map((m) => (
                <div key={m.id} className="space-y-2">
                  <div
                    className={`flex items-start gap-3 ${
                      m.role === 'user' ? 'flex-row-reverse' : ''
                    }`}
                  >
                    <div
                      className={`flex items-center justify-center w-8 h-8 rounded-full shrink-0 ${
                        m.role === 'user'
                          ? 'bg-brand-600 text-white'
                          : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {m.role === 'user' ? (
                        <User className="w-4 h-4" />
                      ) : (
                        <Bot className="w-4 h-4" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      {/* 元信息标签：意图 + Agent + 缓存 */}
                      {m.role === 'assistant' && (m.intent || m.agent || m.cacheHit) && (
                        <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                          {m.intent && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-300">
                              <Zap className="w-2.5 h-2.5" />
                              意图：{m.intent}
                            </span>
                          )}
                          {m.agent && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-300">
                              <Brain className="w-2.5 h-2.5" />
                              {m.agent}
                            </span>
                          )}
                          {m.skillUsed && (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-300">
                              <Sparkles className="w-2.5 h-2.5" />
                              Skill: {m.skillUsed}
                            </span>
                          )}
                          {m.cacheHit && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-300">
                              缓存命中
                            </span>
                          )}
                        </div>
                      )}
                      <div
                        className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm whitespace-pre-wrap break-words ${
                          m.role === 'user'
                            ? 'bg-brand-600 text-white rounded-tr-sm'
                            : 'bg-slate-100 text-slate-800 dark:bg-slate-700 dark:text-slate-100 rounded-tl-sm'
                        }`}
                      >
                        {m.content || (m.streaming && '...')}
                        {m.streaming && !m.content && (
                          <span className="inline-flex gap-1 ml-1">
                            <span
                              className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
                              style={{ animationDelay: '0ms' }}
                            />
                            <span
                              className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
                              style={{ animationDelay: '150ms' }}
                            />
                            <span
                              className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
                              style={{ animationDelay: '300ms' }}
                            />
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  {/* 推理链可视化（仅 assistant 消息且有 chainId） */}
                  {m.role === 'assistant' && m.reasoningChainId && !m.streaming && (
                    <div className="ml-11">
                      <ReasoningChainView chainId={m.reasoningChainId} />
                    </div>
                  )}
                  {/* 思考链折叠面板（Nemotron reasoning_content） */}
                  {m.role === 'assistant' && m.reasoningContent && !m.streaming && (
                    <div className="ml-11 mb-2">
                      <details className="group">
                        <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 flex items-center gap-1">
                          <Brain className="w-3 h-3" />
                          思考过程
                        </summary>
                        <div className="mt-1 p-3 rounded-lg bg-slate-50 dark:bg-slate-700/40 text-xs text-slate-600 dark:text-slate-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
                          {m.reasoningContent}
                        </div>
                      </details>
                    </div>
                  )}
                </div>
              ))
            )}
            {streamingMessage && !streamingMessage.content && (
              <div className="flex items-start gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-full shrink-0 bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="px-4 py-2.5 rounded-2xl bg-slate-100 dark:bg-slate-700 text-slate-500 text-sm">
                  <span className="inline-flex gap-1">
                    <span
                      className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
                      style={{ animationDelay: '0ms' }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
                      style={{ animationDelay: '150ms' }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
                      style={{ animationDelay: '300ms' }}
                    />
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* 快捷建议 */}
          <div className="px-5 py-2 border-t border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                <Sparkles className="w-3.5 h-3.5" />
                快捷：
              </span>
              {quickSuggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  disabled={isStreaming}
                  className="px-2.5 py-1 rounded-full text-xs bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300 hover:bg-brand-100 hover:text-brand-700 dark:hover:bg-brand-900/40 dark:hover:text-brand-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* 输入框 */}
          <div className="p-4 border-t border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入你的问题..."
                disabled={isStreaming}
                className="flex-1 h-10 rounded-xl border border-slate-300 bg-white px-4 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100 dark:placeholder-slate-500 disabled:opacity-50"
              />
              {isStreaming ? (
                <button
                  onClick={handleAbort}
                  className="flex items-center justify-center h-10 px-4 rounded-xl bg-rose-600 text-white text-sm font-medium hover:bg-rose-700 transition-colors"
                >
                  <StopCircle className="w-4 h-4 mr-1.5" />
                  中断
                </button>
              ) : (
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim()}
                  className="flex items-center justify-center h-10 px-4 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4 mr-1.5" />
                  发送
                </button>
              )}
            </div>
          </div>
        </div>

        {/* 右侧：主动建议面板（占 1/3） */}
        <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand-500" />
              <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200">
                主动建议
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              基于你的画像与近期行为，每 60 秒自动刷新
            </p>
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <ProactiveSuggestions maxItems={10} />
          </div>
        </div>
      </div>
    </div>
  )
}
