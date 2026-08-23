import { create } from 'zustand'
import type { ToastItem } from '@/types'

interface ToastState {
  items: ToastItem[]
  push: (message: string, type?: ToastItem['type']) => void
  remove: (id: string) => void
  toast: (message: string, type?: ToastItem['type']) => void
}

const useToastStore = create<ToastState>((set) => ({
  items: [],
  push: (message, type = 'info') => {
    const id = Math.random().toString(36).slice(2, 9)
    set((state) => ({ items: [...state.items, { id, message, type }] }))
    // 自动消失
    setTimeout(() => {
      set((state) => ({ items: state.items.filter((i) => i.id !== id) }))
    }, 3000)
  },
  remove: (id) => set((state) => ({ items: state.items.filter((i) => i.id !== id) })),
  toast: (message, type = 'info') => {
    const id = Math.random().toString(36).slice(2, 9)
    set((state) => ({ items: [...state.items, { id, message, type }] }))
    setTimeout(() => {
      set((state) => ({ items: state.items.filter((i) => i.id !== id) }))
    }, 3000)
  },
}))

// 便捷 hook
export function useToast() {
  const toast = useToastStore((s) => s.toast)
  return toast
}

export { useToastStore }
export default useToast
