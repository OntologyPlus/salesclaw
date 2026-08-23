import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, CornerDownLeft, ArrowUp, ArrowDown, Moon, Sun } from 'lucide-react'
import useCommandPaletteStore from '@/stores/commandPalette'
import useAppStore from '@/stores/app'
import { useTheme } from '@/hooks/useTheme'
import useAIAssistantStore from '@/stores/aiAssistant'
import type { CommandItem } from '@/types'

// 全局命令面板，⌘K 触发
export default function CommandPalette() {
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

  // 构建命令列表
  const commands: CommandItem[] = useMemo(() => {
    const navItems: CommandItem[] = [
      { id: 'portal', label: '门户', group: '导航', keywords: 'portal 门户', action: () => navigate('/portal') },
      { id: 'sales', label: '销售总览', group: '导航', keywords: 'sales 销售', action: () => navigate('/sales') },
      { id: 'sales-plans', label: '拜访计划', group: '导航', keywords: 'plans 拜访计划', action: () => navigate('/sales/plans') },
      { id: 'sales-records', label: '拜访记录', group: '导航', keywords: 'records 拜访记录', action: () => navigate('/sales/records') },
      { id: 'sales-feedback', label: '拜访反馈', group: '导航', keywords: 'feedback 拜访反馈', action: () => navigate('/sales/feedback') },
      { id: 'sales-coverage', label: '覆盖分管', group: '导航', keywords: 'coverage 覆盖', action: () => navigate('/sales/coverage') },
      { id: 'sales-scoring', label: '积分管理', group: '导航', keywords: 'scoring 积分', action: () => navigate('/sales/scoring') },
      { id: 'sales-matrix', label: '矩阵看板', group: '导航', keywords: 'matrix 矩阵', action: () => navigate('/sales/matrix') },
      { id: 'sales-roi', label: 'ROI 分析', group: '导航', keywords: 'roi', action: () => navigate('/sales/roi') },
      { id: 'training', label: '智能培训', group: '导航', keywords: 'training 培训', action: () => navigate('/training') },
      { id: 'decision', label: '决策支持', group: '导航', keywords: 'decision 决策', action: () => navigate('/decision') },
      { id: 'collab', label: '协同办公', group: '导航', keywords: 'collab 协同', action: () => navigate('/collab') },
      { id: 'knowledge', label: '知识库', group: '导航', keywords: 'knowledge 知识库', action: () => navigate('/knowledge') },
      { id: 'crm', label: '客户关系', group: '导航', keywords: 'crm 客户', action: () => navigate('/crm') },
      { id: 'cfm', label: '会议论坛', group: '导航', keywords: 'cfm 会议', action: () => navigate('/cfm') },
      { id: 'tools', label: '内容工具', group: '导航', keywords: 'tools 工具', action: () => navigate('/tools') },
      { id: 'platform', label: '平台管理', group: '导航', keywords: 'platform 平台', action: () => navigate('/platform') },
      { id: 'mdm', label: '主数据', group: '导航', keywords: 'mdm 主数据', action: () => navigate('/mdm') },
      { id: 'settings', label: '设置', group: '导航', keywords: 'settings 设置', action: () => navigate('/settings') },
      { id: 'audit', label: '审计', group: '导航', keywords: 'audit 审计', action: () => navigate('/audit') },
      { id: 'observability', label: '可观测', group: '导航', keywords: 'observability 可观测', action: () => navigate('/observability') },
      { id: 'ai', label: 'AI 助手', group: '导航', keywords: 'ai 助手', action: () => navigate('/ai') },
    ]
    const actionItems: CommandItem[] = [
      {
        id: 'toggle-theme',
        label: theme === 'light' ? '切换到深色模式' : '切换到浅色模式',
        group: '操作',
        keywords: 'theme 主题 dark light',
        action: () => {
          toggleTheme()
          applyToggle()
        },
      },
      {
        id: 'open-ai',
        label: '打开 AI 助手',
        group: '操作',
        keywords: 'ai assistant 助手',
        action: () => toggleAIPanel(),
      },
    ]
    const agentItems: CommandItem[] = [
      { id: 'agent-supervisor', label: 'Supervisor Agent', group: 'AI Agent', keywords: 'supervisor 默认', action: () => toggleAIPanel() },
      { id: 'agent-visit', label: '销售助手 Agent', group: 'AI Agent', keywords: 'visit 销售', action: () => toggleAIPanel() },
      { id: 'agent-course', label: '培训助手 Agent', group: 'AI Agent', keywords: 'course 培训', action: () => toggleAIPanel() },
      { id: 'agent-kpi', label: '决策助手 Agent', group: 'AI Agent', keywords: 'kpi 决策', action: () => toggleAIPanel() },
      { id: 'agent-rag', label: '知识助手 Agent', group: 'AI Agent', keywords: 'rag 知识', action: () => toggleAIPanel() },
    ]
    return [...navItems, ...actionItems, ...agentItems]
  }, [navigate, theme, toggleTheme, applyToggle, toggleAIPanel])

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
                placeholder="搜索页面、功能或命令..."
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
