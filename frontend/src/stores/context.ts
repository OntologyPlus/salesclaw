import { create } from 'zustand'
import { contextAPI } from '@/services/context'

// 上下文维度类型
type ScopeType = 'post' | 'zone' | 'region' | 'area'
type PeriodType = 'day' | 'week' | 'month' | 'quarter' | 'year'
type Perspective = 'management' | 'customer_development' | 'report'

interface ContextState {
  // 三维上下文
  scope_type: ScopeType
  scope_id: number | null
  scope_label: string
  period_type: PeriodType
  period_end: string | null // ISO 日期 YYYY-MM-DD
  perspective: Perspective
  // 元信息
  loaded: boolean
  loading: boolean
  // 操作
  load: () => Promise<void>
  setScope: (scope_type: ScopeType, scope_id: number | null, scope_label?: string) => Promise<void>
  setPeriod: (period_type: PeriodType, period_end: string | null) => Promise<void>
  setPerspective: (perspective: Perspective) => Promise<void>
  reset: () => Promise<void>
}

const DEFAULT_CONTEXT = {
  scope_type: 'post' as ScopeType,
  scope_id: null,
  scope_label: '我的岗位',
  period_type: 'month' as PeriodType,
  period_end: null,
  perspective: 'management' as Perspective,
}

export const useContextStore = create<ContextState>()((set, get) => ({
  ...DEFAULT_CONTEXT,
  loaded: false,
  loading: false,

  load: async () => {
    if (get().loading) return
    set({ loading: true })
    try {
      const data = await contextAPI.get()
      set({
        scope_type: data.scope_type ?? DEFAULT_CONTEXT.scope_type,
        scope_id: data.scope_id ?? DEFAULT_CONTEXT.scope_id,
        scope_label: data.scope_label ?? DEFAULT_CONTEXT.scope_label,
        period_type: data.period_type ?? DEFAULT_CONTEXT.period_type,
        period_end: data.period_end ?? DEFAULT_CONTEXT.period_end,
        perspective: data.perspective ?? DEFAULT_CONTEXT.perspective,
        loaded: true,
        loading: false,
      })
    } catch {
      set({ loaded: true, loading: false })
    }
  },

  setScope: async (scope_type, scope_id, scope_label) => {
    const state = get()
    const next = { ...state, scope_type, scope_id, scope_label: scope_label ?? state.scope_label }
    set({ ...next })
    try {
      await contextAPI.set({
        scope_type: next.scope_type,
        scope_id: next.scope_id,
        scope_label: next.scope_label,
        period_type: next.period_type,
        period_end: next.period_end,
        perspective: next.perspective,
      })
    } catch {
      // 静默失败：本地状态已更新，下次切换会重新同步
    }
  },

  setPeriod: async (period_type, period_end) => {
    const state = get()
    const next = { ...state, period_type, period_end }
    set({ ...next })
    try {
      await contextAPI.set({
        scope_type: next.scope_type,
        scope_id: next.scope_id,
        scope_label: next.scope_label,
        period_type: next.period_type,
        period_end: next.period_end,
        perspective: next.perspective,
      })
    } catch {
      // 静默失败
    }
  },

  setPerspective: async (perspective) => {
    const state = get()
    const next = { ...state, perspective }
    set({ ...next })
    try {
      await contextAPI.set({
        scope_type: next.scope_type,
        scope_id: next.scope_id,
        scope_label: next.scope_label,
        period_type: next.period_type,
        period_end: next.period_end,
        perspective: next.perspective,
      })
    } catch {
      // 静默失败
    }
  },

  reset: async () => {
    set({ ...DEFAULT_CONTEXT })
    try {
      await contextAPI.set(DEFAULT_CONTEXT)
    } catch {
      // 静默失败
    }
  },
}))

export default useContextStore
