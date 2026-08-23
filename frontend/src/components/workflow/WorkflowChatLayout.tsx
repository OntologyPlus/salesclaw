/**
 * 通用工作流对话布局组件（三栏向导式 UI）
 *
 * 设计原则：
 * 1. 左侧步骤树（Step1-StepN + G1-GN 门禁可视化）
 * 2. 中间对话区（AI 引导 + 用户输入）
 * 3. 右侧草稿回显（自定义字段渲染器）
 *
 * 通用化设计：
 * - 通过 props 接收 steps / gates / quickStarters / draftFieldRenderer
 * - 适用于任何 is_workflow=true 的 Skill（visit-planner / what-if-simulator / exam-generator 等）
 * - 复用 useAIStream Hook + DraftState 类型
 */
import { useState, useRef, useEffect, useMemo } from 'react'
import {
  Bot, Send, Sparkles, User, Zap, Brain, StopCircle,
  CheckCircle2, Circle, Lock, AlertCircle, ClipboardList, History,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import { useAIStream, type DraftState } from '@/hooks/useAIStream'
import MessageContent from './MessageContent'
import MessageActions from './MessageActions'
import ChatSessionsSidebar from './ChatSessionsSidebar'
import { useChatSessions } from '@/hooks/useChatSessions'
import { Skeleton } from '@/components/ui/Skeleton'
import { useToast } from '@/hooks/useToast'

// 步骤定义（与后端 SKILL.md frontmatter 的 steps 对齐）
export interface StepDef {
  name: string
  label: string
  description: string
  gates: string[]
  icon: React.ReactNode
}

// 门禁定义
export interface GateDef {
  id: string
  label: string
}

// 草稿回显项（由调用方通过 draftFieldRenderer 提供）
export interface DraftFieldItem {
  label: string
  value: string
  icon: React.ReactNode
}

export interface WorkflowChatLayoutProps {
  pageTitle: string
  pageDescription: string
  breadcrumbs: { label: string }[]
  steps: StepDef[]
  gates: GateDef[]
  quickStarters: string[]
  emptyStateTitle: string
  emptyStateSubtitle: string
  inputPlaceholder: (isWorkflowDone: boolean) => string
  doneMessage: string
  draftFieldRenderer: (draftState: DraftState | null) => DraftFieldItem[]
  // 最终门禁 ID（用于判断工作流是否完成，如 'G8' / 'G7'）
  finalGateId: string
  // F14：会话持久化 key（不传则不持久化）；如 'scene-create' / 'visit-plan'
  pageKey?: string
}

// 单条聊天消息
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  agent?: string
  skillUsed?: string
  toolsUsed?: string[]
  streaming?: boolean
  reasoning?: string
  draftSnapshot?: DraftState | null
}

function genId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

// 安全提取对象字段（避免 unknown 类型报错）
function safeGet<T = unknown>(obj: unknown, key: string): T | undefined {
  if (!obj || typeof obj !== 'object') return undefined
  const o = obj as Record<string, unknown>
  return o[key] as T | undefined
}

// 安全把未知值转为数组
function safeArr<T = unknown>(v: unknown): T[] {
  if (Array.isArray(v)) return v as T[]
  return []
}

export default function WorkflowChatLayout({
  pageTitle,
  pageDescription,
  breadcrumbs,
  steps,
  gates,
  quickStarters,
  emptyStateTitle,
  emptyStateSubtitle,
  inputPlaceholder,
  doneMessage,
  draftFieldRenderer,
  finalGateId,
  pageKey,
}: WorkflowChatLayoutProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string | undefined>(undefined)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const streamingMsgIdRef = useRef<string | null>(null)
  const toolsAccumRef = useRef<string[]>([])

  // F14：会话持久化（pageKey 为空时仍调用 hook 但不启用保存）
  const { sessions, currentId, save, load, remove, createNew } = useChatSessions(pageKey || '__no_persist__')
  const hasPersistence = Boolean(pageKey)

  // F18：错误提示 Toast
  const toast = useToast()

  const {
    streamMessage,
    isStreaming,
    events,
    currentResponse,
    currentReasoning,
    currentSkill,
    draftState,
    reset,
  } = useAIStream()

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, currentResponse, isStreaming])

  // F14：messages 变化时防抖保存到 localStorage（仅 pageKey 启用时）
  useEffect(() => {
    if (!hasPersistence) return
    // 不保存流式中的消息（等流式结束再保存）
    if (isStreaming) return
    if (messages.length === 0) return
    save(messages, draftState, sessionId)
  }, [messages, draftState, sessionId, hasPersistence, isStreaming, save])

  // F14：加载历史会话
  const handleLoadSession = (id: string) => {
    const data = load(id)
    if (!data) return
    setMessages(data.messages)
    setSessionId(data.sessionId)
    // 注意：draftState 由 useAIStream 管理，无法直接 set；这里依赖后续 SSE 事件刷新
    // 若需恢复 draftState，可考虑提升 draftState 到本组件 state（v6.0 改造）
  }

  // F14：新建会话
  const handleNewSession = () => {
    createNew()
    setMessages([])
    setSessionId(undefined)
    reset()
  }

  // 处理 SSE 事件流：累积到当前 streaming 消息
  useEffect(() => {
    if (!streamingMsgIdRef.current) return
    const msgId = streamingMsgIdRef.current

    const latestIntentEvt = events.find((e) => e.type === 'intent')
    const latestRoutingEvt = events.find((e) => e.type === 'routing')
    const latestDoneEvt = events.find((e) => e.type === 'done')
    const errorEvt = events.find((e) => e.type === 'error')

    // 累积工具调用
    for (const e of events) {
      if (e.type === 'tools_used') {
        const items = (e.data as { items?: { name?: string }[] } | undefined)?.items
        if (Array.isArray(items)) {
          for (const it of items) {
            const n = it?.name
            if (n && !toolsAccumRef.current.includes(n)) {
              toolsAccumRef.current.push(n)
            }
          }
        }
      }
    }

    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId) return m
        return {
          ...m,
          content: currentResponse,
          reasoning: currentReasoning || m.reasoning,
          skillUsed: currentSkill ?? m.skillUsed,
          intent:
            (latestIntentEvt?.data as { intent?: string } | undefined)?.intent ?? m.intent,
          agent:
            (latestRoutingEvt?.data as { agent?: string } | undefined)?.agent ?? m.agent,
          toolsUsed:
            toolsAccumRef.current.length > 0 ? [...toolsAccumRef.current] : undefined,
          streaming: !latestDoneEvt && !errorEvt,
          draftSnapshot: latestDoneEvt ? draftState : m.draftSnapshot,
        }
      })
    )

    if (latestDoneEvt) {
      const sid = (latestDoneEvt.data as { session_id?: string } | undefined)?.session_id
      if (sid && !sessionId) setSessionId(sid)
      streamingMsgIdRef.current = null
    }

    if (errorEvt) {
      const errMsg =
        (errorEvt.data as { message?: string } | undefined)?.message ?? '流式请求失败'
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? { ...m, content: m.content || `抱歉，发生错误：${errMsg}`, streaming: false }
            : m
        )
      )
      streamingMsgIdRef.current = null
    }
  }, [events, currentResponse, currentReasoning, currentSkill, sessionId, draftState])

  // 发送消息
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
    toolsAccumRef.current = []

    try {
      await streamMessage(content, undefined, sessionId)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '请求失败'
      toast(`请求失败：${msg}`, 'error')
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

  // F15：重新生成 —— 取上一条 user 消息内容，移除当前 assistant 消息，重新 streamMessage
  const handleRegenerate = async (assistantMsg: ChatMessage) => {
    if (isStreaming) return
    const idx = messages.findIndex((m) => m.id === assistantMsg.id)
    if (idx <= 0) return
    // 向前找最近的 user 消息
    let userContent = ''
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userContent = messages[i].content
        break
      }
    }
    if (!userContent) return
    // 移除当前 assistant 消息（及之后的所有消息）
    setMessages((prev) => prev.slice(0, idx))
    // 重新发送：复用 handleSend 的后半段逻辑（插入新的 assistant 占位 + streamMessage）
    const newAssistant: ChatMessage = { id: genId(), role: 'assistant', content: '', streaming: true }
    setMessages((prev) => [...prev, newAssistant])
    streamingMsgIdRef.current = newAssistant.id
    toolsAccumRef.current = []
    try {
      await streamMessage(userContent, undefined, sessionId)
    } catch (err) {
      const msg = err instanceof Error ? err.message : '请求失败'
      toast(`重新生成失败：${msg}`, 'error')
      setMessages((prev) =>
        prev.map((m) =>
          m.id === newAssistant.id
            ? { ...m, content: m.content || `抱歉，发生错误：${msg}`, streaming: false }
            : m
        )
      )
    }
  }

  // F15：反馈占位（v5.0 不接后端，仅打日志）
  const handleFeedback = (type: 'up' | 'down') => {
    console.log('[feedback]', type, { sessionId })
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  // 当前步骤（来自最新 draftState）
  const currentStepName = draftState?.current_step
  const gatesPassed = useMemo(
    () => new Set(safeArr<string>(draftState?.gates_passed)),
    [draftState?.gates_passed]
  )
  const isWorkflowDone = currentStepName === 'done' || gatesPassed.has(finalGateId)

  // 草稿回显字段（由调用方提供渲染逻辑）
  const draftItems = useMemo(
    () => draftFieldRenderer(draftState ?? null),
    [draftState, draftFieldRenderer]
  )

  // 最近一条 assistant 消息（用于展示工具调用轨迹）
  const lastAssistantMsg = useMemo(
    () => [...messages].reverse().find((m) => m.role === 'assistant'),
    [messages]
  )

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)]">
      <PageHeader
        title={pageTitle}
        description={pageDescription}
        breadcrumbs={breadcrumbs}
        icon={<Sparkles className="w-5 h-5" />}
        gradient
      />

      <div className="flex-1 grid grid-cols-12 gap-4 min-h-0">
        {/* 左侧：步骤树 + 门禁 */}
        <aside className="col-span-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 flex items-center justify-between">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                工作流进度
              </h3>
              <p className="text-xs text-slate-500 mt-1 truncate">
                {isWorkflowDone
                  ? `✓ ${doneMessage}`
                  : currentStepName
                  ? `当前步骤：${currentStepName}`
                  : '尚未开始 - 输入消息触发工作流'}
              </p>
            </div>
            {hasPersistence && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="shrink-0 ml-2 p-1.5 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/30 transition-colors"
                title="历史会话"
              >
                <History className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {steps.map((step, idx) => {
              const isCurrent = currentStepName === step.name
              const isPassed = steps.findIndex((s) => s.name === currentStepName) > idx
              const isDone = isWorkflowDone || (step.name === `Step${steps.length}` && gatesPassed.has(finalGateId))

              return (
                <div
                  key={step.name}
                  className={`p-3 rounded-xl border transition-colors ${
                    isCurrent
                      ? 'border-brand-400 bg-brand-50 dark:bg-brand-900/20 dark:border-brand-500'
                      : isDone || isPassed
                      ? 'border-emerald-200 bg-emerald-50/50 dark:bg-emerald-900/10 dark:border-emerald-800'
                      : 'border-slate-200 dark:border-slate-800'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <div
                      className={`mt-0.5 shrink-0 ${
                        isDone || isPassed
                          ? 'text-emerald-600'
                          : isCurrent
                          ? 'text-brand-600'
                          : 'text-slate-400'
                      }`}
                    >
                      {isDone || isPassed ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : isCurrent ? (
                        <div className="w-4 h-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
                      ) : (
                        <Circle className="w-4 h-4" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`text-xs font-medium ${
                            isCurrent
                              ? 'text-brand-700 dark:text-brand-300'
                              : isPassed || isDone
                              ? 'text-emerald-700 dark:text-emerald-300'
                              : 'text-slate-600 dark:text-slate-300'
                          }`}
                        >
                          {step.label}
                        </span>
                        {step.icon}
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 leading-snug">
                        {step.description}
                      </p>
                      {/* 门禁状态 */}
                      <div className="flex flex-wrap gap-1 mt-2">
                        {step.gates.map((g) => {
                          const passed = gatesPassed.has(g)
                          return (
                            <span
                              key={g}
                              className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] ${
                                passed
                                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                                  : isCurrent
                                  ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                                  : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                              }`}
                              title={gates.find((x) => x.id === g)?.label}
                            >
                              {passed ? (
                                <CheckCircle2 className="w-2.5 h-2.5" />
                              ) : (
                                <Lock className="w-2.5 h-2.5" />
                              )}
                              {g}
                            </span>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* 门禁总览 */}
          <div className="px-3 py-2 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40">
            <div className="text-[10px] text-slate-500 mb-1">门禁总览</div>
            <div className="flex flex-wrap gap-1">
              {gates.map((g) => {
                const passed = gatesPassed.has(g.id)
                return (
                  <span
                    key={g.id}
                    className={`inline-flex items-center justify-center w-7 h-5 rounded text-[10px] font-medium ${
                      passed
                        ? 'bg-emerald-500 text-white'
                        : 'bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                    }`}
                    title={g.label}
                  >
                    {g.id}
                  </span>
                )
              })}
            </div>
          </div>
        </aside>

        {/* 中间：对话区 */}
        <main className="col-span-6 flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-slate-400 animate-fade-in">
                <Sparkles className="w-12 h-12 mb-3 text-brand-400" />
                <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
                  {emptyStateTitle}
                </p>
                <p className="text-xs mt-1 text-slate-400 mb-5">
                  {emptyStateSubtitle}
                </p>
                <div className="flex flex-wrap gap-2 justify-center max-w-xl mx-auto">
                  {quickStarters.map((s) => (
                    <button
                      key={s}
                      onClick={() => handleSend(s)}
                      className="quick-starter-btn"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => (
                <div key={m.id} className={`space-y-2 ${m.role === 'assistant' ? 'group' : ''}`}>
                  <div
                    className={`flex items-start gap-3 ${
                      m.role === 'user' ? 'flex-row-reverse' : ''
                    }`}
                  >
                    <div
                      className={
                        m.role === 'user' ? 'chat-avatar-user' : 'chat-avatar-assistant'
                      }
                    >
                      {m.role === 'user' ? (
                        <User className="w-4 h-4" />
                      ) : (
                        <Bot className="w-4 h-4" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      {/* 元信息标签 */}
                      {m.role === 'assistant' &&
                        (m.intent || m.agent || m.skillUsed) && (
                          <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                            {m.intent && (
                              <span className="chat-tag-intent">
                                <Zap className="w-2.5 h-2.5" />
                                {m.intent}
                              </span>
                            )}
                            {m.agent && (
                              <span className="chat-tag-agent">
                                <Brain className="w-2.5 h-2.5" />
                                {m.agent}
                              </span>
                            )}
                            {m.skillUsed && (
                              <span className="chat-tag-skill">
                                <Sparkles className="w-2.5 h-2.5" />
                                {m.skillUsed}
                              </span>
                            )}
                          </div>
                        )}
                      <div
                        className={
                          m.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'
                        }
                      >
                        {m.role === 'user' ? (
                          m.content
                        ) : m.content ? (
                          <MessageContent content={m.content} streaming={m.streaming} />
                        ) : (
                          m.streaming && (
                            <div className="flex flex-col gap-2 py-1 w-48">
                              <Skeleton className="h-2.5 w-3/4" />
                              <Skeleton className="h-2.5 w-full" />
                              <Skeleton className="h-2.5 w-1/2" />
                            </div>
                          )
                        )}
                      </div>
                      {/* 工作流原语轨迹 */}
                      {m.role === 'assistant' &&
                        m.toolsUsed &&
                        m.toolsUsed.length > 0 &&
                        !m.streaming && (
                          <div className="mt-2 flex flex-wrap gap-1 max-w-[90%]">
                            <span className="text-[10px] text-slate-500 dark:text-slate-400 self-center">
                              调用原语：
                            </span>
                            {m.toolsUsed.map((t, idx) => (
                              <span
                                key={idx}
                                className="chat-tag-tool"
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        )}
                      {/* F15：响应操作（复制/重新生成/反馈），仅 assistant 且非流式时显示 */}
                      {m.role === 'assistant' && !m.streaming && m.content && (
                        <MessageActions
                          content={m.content}
                          onRegenerate={() => void handleRegenerate(m)}
                          onFeedback={handleFeedback}
                        />
                      )}
                    </div>
                  </div>
                  {/* 思考链折叠面板 */}
                  {m.role === 'assistant' && m.reasoning && !m.streaming && (
                    <div className="ml-11 mb-2">
                      <details className="group">
                        <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 flex items-center gap-1">
                          <Brain className="w-3 h-3" />
                          思考过程
                        </summary>
                        <div className="mt-1 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 text-xs text-slate-600 dark:text-slate-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
                          {m.reasoning}
                        </div>
                      </details>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* 快捷建议 */}
          <div className="px-4 py-2 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                <Sparkles className="w-3.5 h-3.5" />
                快捷：
              </span>
              {quickStarters.map((s) => (
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
          <div className="p-4 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={inputPlaceholder(isWorkflowDone)}
                disabled={isStreaming}
                className="flex-1 h-10 rounded-xl border border-slate-300 bg-white px-4 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-100 dark:placeholder-slate-500 disabled:opacity-50"
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
        </main>

        {/* 右侧：草稿回显 */}
        <aside className="col-span-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-2">
              <ClipboardList className="w-4 h-4 text-brand-500" />
              草稿回显
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              {draftItems.length > 0
                ? `已采集 ${draftItems.length} 项`
                : '尚未采集任何字段'}
            </p>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {draftItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-slate-400 py-12">
                <AlertCircle className="w-10 h-10 mb-2 text-slate-300" />
                <p className="text-xs">等待 AI 引导采集字段</p>
                <p className="text-[10px] text-slate-400 mt-1">
                  字段将在用户确认后写入此处
                </p>
              </div>
            ) : (
              draftItems.map((item, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800"
                >
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-500 dark:text-slate-400 mb-1">
                    {item.icon}
                    {item.label}
                  </div>
                  <div className="text-xs text-slate-800 dark:text-slate-200 break-words">
                    {item.value}
                  </div>
                </div>
              ))
            )}

            {/* 最近一次原语调用轨迹 */}
            {lastAssistantMsg?.toolsUsed && lastAssistantMsg.toolsUsed.length > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-slate-500 mb-2 flex items-center gap-1">
                  <Zap className="w-3 h-3" />
                  最近原语调用
                </div>
                <div className="space-y-1">
                  {lastAssistantMsg.toolsUsed.map((t, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-1.5 text-[10px] text-slate-600 dark:text-slate-300"
                    >
                      <CheckCircle2 className="w-2.5 h-2.5 text-emerald-500" />
                      <code className="px-1 py-0.5 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                        {t}
                      </code>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 完成提示 */}
          {isWorkflowDone && (
            <div className="px-3 py-2 border-t border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-900/20">
              <div className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-300">
                <CheckCircle2 className="w-4 h-4" />
                {doneMessage}
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* F14：历史会话侧边栏 */}
      {hasPersistence && (
        <ChatSessionsSidebar
          open={sidebarOpen}
          sessions={sessions}
          currentId={currentId}
          onClose={() => setSidebarOpen(false)}
          onLoad={handleLoadSession}
          onRemove={remove}
          onCreateNew={handleNewSession}
        />
      )}
    </div>
  )
}

// 导出辅助函数供页面使用
export { safeGet, safeArr }
