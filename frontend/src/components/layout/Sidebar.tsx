import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { PanelLeftClose, PanelLeft, ChevronDown } from 'lucide-react'
import useAppStore from '@/stores/app'
import { navIconMap } from './navIcons'
import navGroups from '@/config/navConfig'

// F-重构：技术模块分组（更多工具）默认折叠，降低侧边栏密度
const COLLAPSED_BY_DEFAULT = new Set(['moreTools'])

export default function Sidebar() {
  const { t } = useTranslation()
  const collapsed = useAppStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)

  return (
    <aside
      className={`flex flex-col shrink-0 border-r border-slate-200 dark:border-surface-border-subtle-dark bg-surface-sidebar dark:bg-surface-sidebar-dark transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Logo 区 */}
      <div className="flex items-center gap-2 h-16 px-4 border-b border-slate-200 dark:border-surface-border-subtle-dark shrink-0">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-500 text-white font-bold shrink-0">
          S
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
            SalesClaw
          </span>
        )}
      </div>

      {/* 导航区 */}
      <nav className="flex-1 overflow-y-auto py-3">
        {navGroups.map((group) => {
          const isCollapsedGroup =
            COLLAPSED_BY_DEFAULT.has(group.id) && !collapsed
          return (
            <details key={group.id} className="group mb-1" open={!isCollapsedGroup}>
              <summary className="flex items-center justify-between px-4 py-1.5 list-none cursor-pointer select-none">
                {!collapsed && (
                  <span className="text-xs font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                    {t(group.titleKey)}
                  </span>
                )}
                {!collapsed && (
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400 transition-transform group-open:rotate-180" />
                )}
              </summary>
              <div className="space-y-0.5 px-2 mt-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon ?? navIconMap[item.path]
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      end={item.end}
                      title={t(item.labelKey)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors ${
                          isActive
                            ? 'bg-brand-50 text-brand-700 font-medium dark:bg-brand-900/30 dark:text-brand-300'
                            : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                        } ${collapsed ? 'justify-center' : ''}`
                      }
                    >
                      {Icon && (
                        <span className="shrink-0">
                          <Icon className="w-4 h-4" />
                        </span>
                      )}
                      {!collapsed && <span className="truncate">{t(item.labelKey)}</span>}
                    </NavLink>
                  )
                })}
              </div>
            </details>
          )
        })}
      </nav>

      {/* 折叠按钮 */}
      <div className="shrink-0 border-t border-slate-200 dark:border-surface-border-subtle-dark p-2">
        <button
          onClick={toggleSidebar}
          className={`flex items-center gap-2 w-full px-2.5 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          {collapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          {!collapsed && <span>收起</span>}
        </button>
      </div>
    </aside>
  )
}
