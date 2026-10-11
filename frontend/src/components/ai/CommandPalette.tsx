import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, CornerDownLeft, ArrowUp, ArrowDown, Moon, Sun } from 'lucide-react'
import useCommandPaletteStore from '@/stores/commandPalette'
import useAppStore from '@/stores/app'
import { useTheme } from '@/hooks/useTheme'
import useAIAssistantStore from '@/stores/aiAssistant'
import { allNavItems, navGroups } from '@/config/navConfig'
import type { CommandItem } from '@/types'

// 全局命令面板，⌘K 触发；导航索引来自 navConfig.allNavItems
export default function CommandPalette() {
  const { t } = useTranslation()
  const open = useCommandPaletteStore((s) => s.open)
  const query = useCommandPaletteStore((s) => s.query)
  const setOpen = useCommandPaletteStore((s) => s.setOpen)
  const setQuery = useCommandPaletteStore((s) => s.setQuery)
  const addRecent = useCommandPaletteStore((s) => s.addRecent)
  const navigate = useNavigate()
  const toggleTheme = useAppStore((s) => s.toggleTheme)
  const theme = useAppStore((s) => s.theme)
  const { toggleTheme: applyToggle } = useTheme()
  const toggleAIPanel = useAIAssistantStore((s) => s.toggle)
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // 全局 ⌘K 监听
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(!open)
      }
      if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, setOpen])

  // 打开时聚焦输入框
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setActiveIndex(0)
      setQuery('')
    }
  }, [open, setQuery])

  const groupTitleByPath = useMemo(() => {
    const map = new Map<string, string>()
    for (const g of navGroups) {
      const title = t(g.titleKey)
      for (const item of g.items) map.set(item.path, title)
    }
    return map
  }, [t])

  // 构建命令列表：全量 navConfig + 主题/AI 操作
  const commands: CommandItem[] = useMemo(() => {
    const navItems: CommandItem[] = allNavItems.map((item) => {
      const zh = item.label
      const en = t(item.labelKey, { lng: 'en', defaultValue: item.label })
      const label = t(item.labelKey, { defaultValue: item.label })
      return {
        id: item.path,
        label,
        group: groupTitleByPath.get(item.path) || t('nav.group.moreTools'),
        keywords: `${item.path} ${zh} ${en} ${item.labelKey}`,
        action: () => navigate(item.path),
      }
    })
    const actionItems: CommandItem[] = [
      {
        id: 'toggle-theme',
        label: theme === 'light' ? t('common.dark') : t('common.light'),
        group: t('common.actions'),
        keywords: 'theme dark light 主题',
        action: () => {
          toggleTheme()
          applyToggle()
        },
      },
      {
        id: 'open-ai',
        label: t('common.aiAssistant'),
        group: t('common.actions'),
        keywords: 'ai assistant 助手',
        action: () => toggleAIPanel(),
      },
      {
        id: 'profile',
        label: t('nav.profile'),
        group: t('common.actions'),
        keywords: 'profile 画像',
        action: () => navigate('/profile'),
      },
    ]
    return [...navItems, ...actionItems]
  }, [navigate, theme, toggleTheme, applyToggle, toggleAIPanel, t, groupTitleByPath])

  // 过滤
  const filtered = useMemo(() => {
    if (!query.trim()) return commands
    const q = query.toLowerCase()
    return commands.filter(
      (c) => c.label.toLowerCase().includes(q) || (c.keywords?.toLowerCase().includes(q))
    )
  }, [commands, query])

  // 分组
  const grouped = useMemo(() => {
    const map = new Map<string, CommandItem[]>()
    filtered.forEach((c) => {
      if (!map.has(c.group)) map.set(c.group, [])
      map.get(c.group)!.push(c)
    })
    return Array.from(map.entries())
  }, [filtered])

  // 重置选中
  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  // 键盘导航
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const item = filtered[activeIndex]
      if (item) {
        item.action()
        addRecent(item.label)
        setOpen(false)
      }
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[90] flex items-start justify-center pt-[15vh] px-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />
          <motion.div
            initial={{ opacity: 0, y: -16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
            className="relative w-full max-w-xl rounded-2xl bg-white dark:bg-slate-800 shadow-2xl overflow-hidden"
          >
            {/* 搜索框 */}
            <div className="flex items-center gap-3 px-4 border-b border-slate-200 dark:border-slate-700">
              <Search className="w-5 h-5 text-slate-400 shrink-0" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('common.commandPlaceholder')}
                aria-label={t('common.openCommandPalette')}
                className="flex-1 h-14 bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none"
              />
              <kbd className="px-1.5 py-0.5 text-xs rounded bg-slate-100 dark:bg-slate-700 text-slate-400 font-mono">ESC</kbd>
            </div>

            {/* 结果列表 */}
            <div className="max-h-[50vh] overflow-y-auto py-2">
              {filtered.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-slate-400">无匹配结果</div>
              ) : (
                grouped.map(([group, items]) => (
                  <div key={group} className="mb-1">
                    <p className="px-4 py-1 text-xs font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                      {group}
                    </p>
                    {items.map((item) => {
                      const idx = filtered.indexOf(item)
                      const isActive = idx === activeIndex
                      return (
                        <button
                          key={item.id}
                          onMouseEnter={() => setActiveIndex(idx)}
                          onClick={() => {
                            item.action()
                            addRecent(item.label)
                            setOpen(false)
                          }}
                          className={`flex items-center gap-3 w-full px-4 py-2.5 text-left text-sm transition-colors ${
                            isActive
                              ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300'
                              : 'text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/50'
                          }`}
                        >
                          <span className="flex-1 truncate">{item.label}</span>
                          {isActive && <CornerDownLeft className="w-3.5 h-3.5 text-brand-400" />}
                        </button>
                      )
                    })}
                  </div>
                ))
              )}
            </div>

            {/* 底部提示 */}
            <div className="flex items-center gap-4 px-4 py-2 border-t border-slate-200 dark:border-slate-700 text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <ArrowUp className="w-3 h-3" /><ArrowDown className="w-3 h-3" /> 选择
              </span>
              <span className="flex items-center gap-1">
                <CornerDownLeft className="w-3 h-3" /> 确认
              </span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

export { Moon, Sun }
