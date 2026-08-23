import { create } from 'zustand'

interface CommandPaletteState {
  open: boolean
  query: string
  recent: string[]
  toggle: () => void
  setOpen: (open: boolean) => void
  setQuery: (query: string) => void
  addRecent: (item: string) => void
  clearRecent: () => void
}

const useCommandPaletteStore = create<CommandPaletteState>((set) => ({
  open: false,
  query: '',
  recent: [],
  toggle: () => set((state) => ({ open: !state.open })),
  setOpen: (open) => set({ open }),
  setQuery: (query) => set({ query }),
  addRecent: (item) =>
    set((state) => ({
      recent: [item, ...state.recent.filter((r) => r !== item)].slice(0, 8),
    })),
  clearRecent: () => set({ recent: [] }),
}))

export default useCommandPaletteStore
