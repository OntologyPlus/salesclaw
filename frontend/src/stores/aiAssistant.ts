import { create } from 'zustand'
import type { ChatMessage } from '@/types'

interface AIAssistantState {
  open: boolean
  pinned: boolean
  loading: boolean
  currentAgent: string
  messages: ChatMessage[]
  currentSessionId: string | null
  toggle: () => void
  setOpen: (open: boolean) => void
  pin: () => void
  setAgent: (name: string) => void
  setMessages: (messages: ChatMessage[]) => void
  addMessage: (message: ChatMessage) => void
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void
  setLoading: (loading: boolean) => void
  setSessionId: (id: string | null) => void
  newSession: () => void
  clearMessages: () => void
}

const useAIAssistantStore = create<AIAssistantState>((set) => ({
  open: false,
  pinned: false,
  loading: false,
  currentAgent: 'supervisor',
  messages: [],
  currentSessionId: null,
  toggle: () => set((state) => ({ open: !state.open })),
  setOpen: (open) => set({ open }),
  pin: () => set((state) => ({ pinned: !state.pinned })),
  setAgent: (name) => set({ currentAgent: name }),
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (id, patch) =>
    set((state) => ({
      messages: state.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),
  setLoading: (loading) => set({ loading }),
  setSessionId: (id) => set({ currentSessionId: id }),
  newSession: () => set({ messages: [], currentSessionId: null }),
  clearMessages: () => set({ messages: [] }),
}))

export default useAIAssistantStore
