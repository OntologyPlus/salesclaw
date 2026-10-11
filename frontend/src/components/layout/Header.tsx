import { useLocation } from 'react-router-dom'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Menu, Search, Sun, Moon, User as UserIcon, LogOut } from 'lucide-react'
import useAppStore from '@/stores/app'
import useAuthStore from '@/stores/auth'
import useCommandPaletteStore from '@/stores/commandPalette'
import { useTheme } from '@/hooks/useTheme'
import Dropdown, { type DropdownItem } from '@/components/ui/Dropdown'

// 顶部栏：折叠按钮 + 面包屑 + 命令面板触发 + 主题切换 + 用户菜单
export default function Header() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const { theme, toggleTheme } = useTheme()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const setPaletteOpen = useCommandPaletteStore((s) => s.setOpen)

  // 生成面包屑
  const segments = location.pathname.split('/').filter(Boolean)
  const breadcrumbs = segments.map((seg, i) => ({
    label: seg,
    path: '/' + segments.slice(0, i + 1).join('/'),
  }))

  const userMenuItems: DropdownItem[] = [
    {
      label: t('common.profile'),
      icon: <UserIcon className="w-4 h-4" />,
      onClick: () => navigate('/profile'),
    },
    {
      label: t('common.logout'),
      icon: <LogOut className="w-4 h-4" />,
      danger: true,
      onClick: () => {
        logout()
        navigate('/login')
      },
    },
  ]

  return (
    <header className="flex items-center justify-between gap-4 h-16 px-4 border-b border-slate-200 dark:border-surface-border-subtle-dark bg-surface-header dark:bg-surface-header-dark shrink-0">
      {/* 左侧：折叠 + 面包屑 */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={toggleSidebar}
          className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <nav className="flex items-center gap-1.5 text-sm min-w-0">
          {breadcrumbs.length === 0 ? (
            <span className="text-slate-700 dark:text-slate-200 font-medium">{t('nav.portal')}</span>
          ) : (
            breadcrumbs.map((bc, i) => (
              <span key={i} className="flex items-center gap-1.5 min-w-0">
                <span className={i === breadcrumbs.length - 1 ? 'text-slate-900 dark:text-slate-100 font-medium truncate' : 'text-slate-500 dark:text-slate-400 truncate'}>
                  {bc.label}
                </span>
                {i < breadcrumbs.length - 1 && <span className="text-slate-300 dark:text-slate-600">/</span>}
              </span>
            ))
          )}
        </nav>
      </div>

      {/* 中间：命令面板触发 */}
      <button
        type="button"
        onClick={() => setPaletteOpen(true)}
        aria-label={t('common.openCommandPalette')}
        className="flex items-center gap-2 px-3 h-9 rounded-xl border border-slate-200 dark:border-surface-border-subtle-dark bg-white dark:bg-surface-card-dark text-sm text-slate-500 hover:border-slate-300 dark:hover:border-slate-600 transition-colors w-64"
      >
        <Search className="w-4 h-4" />
        <span className="flex-1 text-left text-slate-400">{t('common.commandPlaceholder')}</span>
        <kbd className="px-1.5 py-0.5 text-xs rounded bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-300 font-mono">⌘K</kbd>
      </button>

      {/* 右侧：主题 + 用户 */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title={theme === 'light' ? t('common.dark') : t('common.light')}
        >
          {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </button>
        <Dropdown
          trigger={
            <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer">
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-br from-brand-500 to-violet-500 text-white text-sm font-medium">
                {user?.display_name?.[0] || user?.username?.[0] || 'U'}
              </div>
              <span className="text-sm text-slate-700 dark:text-slate-200 hidden sm:block">
                {user?.display_name || user?.username || 'User'}
              </span>
            </div>
          }
          items={userMenuItems}
        />
      </div>
    </header>
  )
}
