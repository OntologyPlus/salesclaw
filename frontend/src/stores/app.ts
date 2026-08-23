import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark'
type Locale = 'zh-CN' | 'en'

interface AppState {
  theme: Theme
  locale: Locale
  sidebarCollapsed: boolean
  toggleTheme: () => void
  setTheme: (theme: Theme) => void
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  setLocale: (locale: Locale) => void
}

const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      theme: 'light',
      locale: 'zh-CN',
      sidebarCollapsed: false,
      toggleTheme: () => set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
      setTheme: (theme) => set({ theme }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setLocale: (locale) => set({ locale }),
    }),
    {
      name: 'salesclaw-app',
    }
  )
)

export default useAppStore
