import { useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// 跨页 AI 上下文项
export interface AIContextItem {
  id: string
  page: string
  pageTitle: string
  data?: Record<string, unknown>  // 页面关键数据快照
  timestamp: number
}

interface AIContextState {
  stack: AIContextItem[]
  push: (item: Omit<AIContextItem, 'id' | 'timestamp'>) => void
  pop: (id?: string) => void
  clear: () => void
  // 拼接成给 LLM 的上下文描述
  asPromptFragment: () => string
}

// 全局 store + localStorage 持久化
export const useAIContextStore = create<AIContextState>()(
  persist(
    (set, get) => ({
      stack: [],
      push: (item) => set((s) => {
        // 避免重复（同 page+data）
        if (s.stack.some(x => x.page === item.page)) return s
        const newItem: AIContextItem = {
          ...item,
          id: `${item.page}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          timestamp: Date.now(),
        }
        // 最多保留 5 条
        return { stack: [...s.stack, newItem].slice(-5) }
      }),
      pop: (id) => set((s) => ({
        stack: id ? s.stack.filter(x => x.id !== id) : s.stack.slice(0, -1),
      })),
      clear: () => set({ stack: [] }),
      asPromptFragment: () => {
        const s = get().stack
        if (s.length === 0) return ''
        return s.map(x => `[来自 ${x.pageTitle}]`).join(' → ')
      },
    }),
    {
      name: 'salesclaw:ai-context-stack',
      version: 1,
    }
  )
)

/**
 * 跨页 AI 上下文 Hook
 *
 * 自动追踪当前路由 push 到 stack；提供操作方法。
 * 任何 AI 提问时可附带 asPromptFragment() 给 LLM 上下文。
 */
export function useAIContextStack() {
  const location = useLocation()
  const stack = useAIContextStore((s) => s.stack)
  const push = useAIContextStore((s) => s.push)
  const pop = useAIContextStore((s) => s.pop)
  const clear = useAIContextStore((s) => s.clear)
  const asPromptFragment = useAIContextStore((s) => s.asPromptFragment)

  // 简化版：当前页变化时自动 push（不带数据快照）
  // 业务页可手动调用 push({page, pageTitle, data}) 携带额外数据
  // 这里不做自动 push，避免污染；仅暴露 API

  const trackPage = useCallback((pageTitle?: string, data?: Record<string, unknown>) => {
    if (!pageTitle) return
    push({ page: location.pathname, pageTitle, data })
  }, [location.pathname, push])

  return {
    stack,
    trackPage,
    pop,
    clear,
    asPromptFragment,
  }
}
