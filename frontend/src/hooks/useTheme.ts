import { useEffect } from 'react'
import useAppStore from '@/stores/app'

// 主题 Hook：读写主题，localStorage 持久化，切换 dark class
export function useTheme() {
  const theme = useAppStore((s) => s.theme)
  const toggleTheme = useAppStore((s) => s.toggleTheme)
  const setTheme = useAppStore((s) => s.setTheme)

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  return { theme, toggleTheme, setTheme }
}

export default useTheme
