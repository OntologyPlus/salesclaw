import { useState, useCallback, useRef, useEffect } from 'react'
import useAuthStore from '@/stores/auth'

// SSE 事件类型
export type AIStreamEventType =
  | 'thinking'
  | 'intent'
  | 'routing'
  | 'reasoning'
  | 'content'
  | 'tools_used'
  | 'suggestions'
  | 'skill'
  | 'done'
  | 'error'

// 单个 SSE 事件
export interface AIStreamEvent {
  type: AIStreamEventType
  data: unknown
  ts: number
}

// 工作流 Skill 的 draft_state（用于向导式 UI 渲染步骤进度与草稿回显）
export interface DraftState {
  current_step?: string
  gates_passed?: string[]
  scenario_id?: number | null
  // WorkflowSkillExecutor 在 next_step_hint 中返回下一步提示
  next_step_hint?: string
  // 以下字段由 WorkflowSkillExecutor.execute() 的 draft_state 透传
  // （executor.py 的 draft_state 当前只含 current_step/gates_passed/scenario_id，
  //  这里允许扩展字段，前端做可选渲染）
  collection?: Record<string, unknown>
  title_bg?: Record<string, unknown>
  knowledge?: Record<string, unknown>
  context_payload?: Record<string, unknown>
  [key: string]: unknown
}

// useAIStream 返回值
export interface UseAIStreamReturn {
  streamMessage: (content: string, agent?: string, sessionId?: string) => Promise<void>
  isStreaming: boolean
  events: AIStreamEvent[]
  currentResponse: string
  currentReasoning: string
  currentSkill: string | null
  // N+5：工作流 Skill done 事件携带的 draft_state（每次流式完成后更新）
  draftState: DraftState | null
  reset: () => void
}

// API 基础地址：优先使用 VITE_API_URL，回退到 /v1（与 services/api.ts 一致）
const API_BASE: string =
  ((import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_API_URL) ??
  '/v1'

// 从 content 事件 data 中提取文本片段
function extractText(data: unknown): string {
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>
    const candidate = obj.text ?? obj.delta ?? obj.content ?? obj.chunk
    if (typeof candidate === 'string') return candidate
  }
  return ''
}

// 解析单个 SSE 数据块（形如 "event: xxx\ndata: {...}"）
function parseSSEBlock(block: string): { type: string; data: unknown } | null {
  let type = ''
  let dataStr = ''
  for (const line of block.split('\n')) {
    const trimmed = line.trimStart()
    if (trimmed.startsWith('event:')) {
      type = trimmed.slice(6).trim()
    } else if (trimmed.startsWith('data:')) {
      dataStr += trimmed.slice(5).trim()
    }
  }
  if (!type) return null
  let data: unknown = dataStr
  if (dataStr) {
    try {
      data = JSON.parse(dataStr)
    } catch {
      // 非 JSON，保留原始字符串
    }
  }
  return { type, data }
}

// SSE 流式接收 Hook，使用 fetch + ReadableStream（支持 POST 与认证头）
export function useAIStream(): UseAIStreamReturn {
  const [isStreaming, setIsStreaming] = useState(false)
  const [events, setEvents] = useState<AIStreamEvent[]>([])
  const [currentResponse, setCurrentResponse] = useState('')
  const [currentReasoning, setCurrentReasoning] = useState('')
  const [currentSkill, setCurrentSkill] = useState<string | null>(null)
  const [draftState, setDraftState] = useState<DraftState | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)

  // 组件卸载时中止进行中的流，避免对已卸载组件 setState
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (abortRef.current) {
        abortRef.current.abort()
        abortRef.current = null
      }
    }
  }, [])

  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    setEvents([])
    setCurrentResponse('')
    setCurrentReasoning('')
    setCurrentSkill(null)
    setDraftState(null)
    setIsStreaming(false)
  }, [])

  const streamMessage = useCallback(
    async (content: string, agent?: string, sessionId?: string) => {
      if (!content.trim()) return
      // 中断上一次未完成的流
      if (abortRef.current) {
        abortRef.current.abort()
      }
      const controller = new AbortController()
      abortRef.current = controller

      // 重置累积状态
      setEvents([])
      setCurrentResponse('')
      setCurrentReasoning('')
      setCurrentSkill(null)
      // 注意：不重置 draftState —— 工作流 Skill 的草稿需要跨多轮对话累积
      setIsStreaming(true)

      const token = useAuthStore.getState().token
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      }
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }

      try {
        const res = await fetch(`${API_BASE}/ai/chat/stream`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            message: content,
            agent,
            session_id: sessionId,
            stream: true,
          }),
          signal: controller.signal,
        })

        if (!res.ok || !res.body) {
          const message = `HTTP ${res.status}`
          setEvents((prev) => [...prev, { type: 'error', data: { message }, ts: Date.now() }])
          throw new Error(`流式请求失败: ${res.status}`)
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          if (!mountedRef.current) {
            reader.cancel().catch(() => {})
            return
          }
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          // SSE 事件以空行分隔
          const parts = buffer.split('\n\n')
          buffer = parts.pop() ?? ''
          for (const part of parts) {
            if (!part.trim()) continue
            const parsed = parseSSEBlock(part)
            if (!parsed) continue
            const evt: AIStreamEvent = {
              type: parsed.type as AIStreamEventType,
              data: parsed.data,
              ts: Date.now(),
            }
            setEvents((prev) => [...prev, evt])

            if (evt.type === 'content') {
              const chunk = extractText(evt.data)
              if (chunk) {
                setCurrentResponse((prev) => prev + chunk)
              }
            } else if (evt.type === 'reasoning') {
              const chunk = extractText(evt.data)
              if (chunk) {
                setCurrentReasoning((prev) => prev + chunk)
              }
            } else if (evt.type === 'skill') {
              const skillData = evt.data as Record<string, unknown>
              const skillName = typeof skillData === 'object' && skillData ? skillData.name as string : ''
              if (skillName) setCurrentSkill(skillName)
            } else if (evt.type === 'error') {
              // SSE 错误事件：释放 reader 后结束流式
              reader.cancel().catch(() => {})
              return
            } else if (evt.type === 'done') {
              // N+5：从 done 事件提取 draft_state（工作流 Skill 透传）
              const doneData = evt.data as Record<string, unknown> | undefined
              if (doneData && typeof doneData === 'object' && doneData.draft_state) {
                setDraftState(doneData.draft_state as DraftState)
              }
              // 正常结束
              return
            }
          }
        }
      } catch (err) {
        // 主动中断视为正常结束
        if (err instanceof DOMException && err.name === 'AbortError') {
          return
        }
        const message = err instanceof Error ? err.message : '流式请求失败'
        setEvents((prev) => [...prev, { type: 'error', data: { message }, ts: Date.now() }])
        throw err
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
          // 仅当仍是当前流时才复位：旧流被 abort 后其 finally 会在微任务中晚于
          // 新流的 setIsStreaming(true) 执行，错误复位会把新流标记为已结束
          setIsStreaming(false)
        }
      }
    },
    []
  )

  return { streamMessage, isStreaming, events, currentResponse, currentReasoning, currentSkill, draftState, reset }
}

export default useAIStream
