import { useCallback } from 'react'
import useAIAssistantStore from '@/stores/aiAssistant'
import useToast from './useToast'
import { chatSend } from '@/services/ai'
import type { ChatMessage } from '@/types'

// 封装 AI 助手交互
export function useAI() {
  const open = useAIAssistantStore((s) => s.open)
  const pinned = useAIAssistantStore((s) => s.pinned)
  const loading = useAIAssistantStore((s) => s.loading)
  const currentAgent = useAIAssistantStore((s) => s.currentAgent)
  const messages = useAIAssistantStore((s) => s.messages)
  const currentSessionId = useAIAssistantStore((s) => s.currentSessionId)
  const toggle = useAIAssistantStore((s) => s.toggle)
  const setOpen = useAIAssistantStore((s) => s.setOpen)
  const pin = useAIAssistantStore((s) => s.pin)
  const setAgent = useAIAssistantStore((s) => s.setAgent)
  const addMessage = useAIAssistantStore((s) => s.addMessage)
  const updateMessage = useAIAssistantStore((s) => s.updateMessage)
  const setLoading = useAIAssistantStore((s) => s.setLoading)
  const setSessionId = useAIAssistantStore((s) => s.setSessionId)
  const newSession = useAIAssistantStore((s) => s.newSession)
  const toast = useToast()

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return
      const userMessage: ChatMessage = {
        id: Math.random().toString(36).slice(2, 9),
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      }
      addMessage(userMessage)

      const assistantId = Math.random().toString(36).slice(2, 9)
      const pendingMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        pending: true,
      }
      addMessage(pendingMessage)
      setLoading(true)

      try {
        const res = await chatSend(content, currentAgent, currentSessionId ?? undefined)
        setSessionId(res.session_id)
        updateMessage(assistantId, {
          content: res.response,
          agent_used: res.agent_used,
          actions_called: res.actions_called,
          references: res.references,
          pending: false,
        })
      } catch (err) {
        const message = err instanceof Error ? err.message : 'AI 调用失败'
        updateMessage(assistantId, {
          content: '',
          pending: false,
          error: message,
        })
        toast(message, 'error')
      } finally {
        setLoading(false)
      }
    },
    [addMessage, updateMessage, setLoading, setSessionId, currentAgent, currentSessionId, toast]
  )

  return {
    open,
    pinned,
    loading,
    currentAgent,
    messages,
    currentSessionId,
    toggle,
    setOpen,
    pin,
    setAgent,
    sendMessage,
    newSession,
  }
}

export default useAI
