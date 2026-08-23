/**
 * 会话历史持久化 Hook（localStorage）
 *
 * F14：解决 WorkflowChatLayout 刷新即丢消息的问题。
 * - 按 pageKey 分区存储，避免跨页面串扰
 * - key 格式：salesclaw:chat-sessions:{pageKey}:{sessionId}
 * - 提供 save / load / remove / createNew 能力
 *
 * 注意：消息中的 DraftState 等结构会被 JSON.stringify，需保证可序列化。
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import type { DraftState } from '@/hooks/useAIStream'

export interface ChatMessagePersisted {
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

export interface ChatSessionMeta {
  id: string
  title: string // 取首条 user 消息前 20 字
  updatedAt: number
  messageCount: number
}

export interface ChatSessionData extends ChatSessionMeta {
  messages: ChatMessagePersisted[]
  draftState: DraftState | null
  sessionId?: string // 后端 sessionId（如有）
}

const PREFIX = 'salesclaw:chat-sessions:'

function keyOf(pageKey: string, id: string) {
  return `${PREFIX}${pageKey}:${id}`
}

export function useChatSessions(pageKey: string) {
  const storageKey = PREFIX + pageKey
  const [sessions, setSessions] = useState<ChatSessionMeta[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 初次挂载：扫描 localStorage，加载本 pageKey 下所有会话元信息
  useEffect(() => {
    const list: ChatSessionMeta[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (!k || !k.startsWith(storageKey + ':')) continue
      const raw = localStorage.getItem(k)
      if (!raw) continue
      try {
        const data = JSON.parse(raw) as ChatSessionData
        list.push({
          id: data.id,
          title: data.title,
          updatedAt: data.updatedAt,
          messageCount: data.messageCount,
        })
      } catch {
        // 损坏数据，跳过
      }
    }
    list.sort((a, b) => b.updatedAt - a.updatedAt)
    setSessions(list)
  }, [storageKey])

  // 组件卸载时清除未触发的防抖保存定时器，避免对已卸载组件 setState
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current)
        saveTimerRef.current = null
      }
    }
  }, [])

  // 防抖保存：messages 变化时延迟 500ms 写入，避免高频 IO
  const save = useCallback(
    (messages: ChatMessagePersisted[], draftState: DraftState | null, sessionId?: string) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => {
        if (messages.length === 0) return
        const id = currentId || Math.random().toString(36).slice(2) + Date.now().toString(36)
        const firstUser = messages.find((m) => m.role === 'user')
        const title = firstUser ? firstUser.content.slice(0, 20) : '新会话'
        const data: ChatSessionData = {
          id,
          title,
          updatedAt: Date.now(),
          messageCount: messages.length,
          messages: messages.map((m) => ({ ...m, streaming: false })), // 持久化时清除 streaming 标记
          draftState,
          sessionId,
        }
        try {
          localStorage.setItem(keyOf(pageKey, id), JSON.stringify(data))
          if (currentId !== id) setCurrentId(id)
          setSessions((prev) => {
            const next = prev.filter((s) => s.id !== id)
            next.unshift({
              id,
              title,
              updatedAt: data.updatedAt,
              messageCount: messages.length,
            })
            return next
          })
        } catch (e) {
          // localStorage 空间不足等异常，静默降级
          console.warn('[useChatSessions] save failed', e)
        }
      }, 500)
    },
    [currentId, pageKey]
  )

  const load = useCallback(
    (id: string): ChatSessionData | null => {
      const raw = localStorage.getItem(keyOf(pageKey, id))
      if (!raw) return null
      try {
        const data = JSON.parse(raw) as ChatSessionData
        setCurrentId(id)
        return data
      } catch {
        return null
      }
    },
    [pageKey]
  )

  const remove = useCallback(
    (id: string) => {
      localStorage.removeItem(keyOf(pageKey, id))
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (currentId === id) setCurrentId(null)
    },
    [pageKey, currentId]
  )

  const createNew = useCallback(() => {
    setCurrentId(null)
  }, [])

  return { sessions, currentId, save, load, remove, createNew }
}
