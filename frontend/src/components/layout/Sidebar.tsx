import { NavLink, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { PanelLeftClose, PanelLeft, ChevronDown } from 'lucide-react'
import useAppStore from '@/stores/app'
import { navIconMap } from './navIcons'
import { sidebarNavGroups } from '@/config/navConfig'

/** 默认仅展开今日工作台，降低首屏密度 */
const OPEN_BY_DEFAULT = new Set(['today'])

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
      <div className="flex items-center gap-2 h-16 px-4 border-b border-slate-200 dark:border-surface-border-subtle-dark shrink-0">
        <Link to="/portal" className="flex items-center gap-2 min-w-0" title={t('nav.portal')}>
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-500 text-white font-bold shrink-0">
            S
          </div>
          {!collapsed && (
            <span className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
              SalesClaw
            </span>
          )}
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto py-3" aria-label={t('nav.group.today')}>
        {sidebarNavGroups.map((group) => {
          // 宽侧栏：默认仅今日展开；窄侧栏（图标模式）：全部展开以便点到各入口
          const openByDefault = collapsed || OPEN_BY_DEFAULT.has(group.id)
          return (
            <details key={group.id} className="group mb-1" open={openByDefault}>
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
                      title={t(item.labelKey, { defaultValue: item.label })}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors ${
                          isActive
                            ? 'bg-brand-50 text-brand-700 font-medium dark:bg-brand-900/30 dark:text-brand-300'
                            : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-surface-raised-dark'
                        } ${collapsed ? 'justify-center' : ''}`
                      }
                    >
                      {Icon && (
                        <span className="shrink-0">
                          <Icon className="w-4 h-4" />
                        </span>
                      )}
                      {!collapsed && (
                        <span className="truncate">
                          {t(item.labelKey, { defaultValue: item.label })}
                        </span>
                      )}
                    </NavLink>
                  )
                })}
              </div>
            </details>
          )
        })}
      </nav>

      <div className="shrink-0 border-t border-slate-200 dark:border-surface-border-subtle-dark p-2">
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label={collapsed ? t('common.expandSidebar') : t('common.collapseSidebar')}
          className={`flex items-center gap-2 w-full px-2.5 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-100 dark:hover:bg-surface-raised-dark transition-colors ${
            collapsed ? 'justify-center' : ''
          }`}
        >
          {collapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          {!collapsed && <span>{t('common.collapseSidebar')}</span>}
        </button>
      </div>
    </aside>
  )
}
