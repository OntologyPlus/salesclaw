import { Layers, Users, ShieldCheck, Activity, Building2 } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import { useFetch } from '@/hooks/useFetch'
import { platformAPI } from '@/services/platform'
import AIInsightPanel from '@/components/ai/AIInsightPanel'
import type { PageRes } from '@/types/page'

// 租户
interface Tenant {
  id: number | string
  name: string
  code: string
  created_at: string
}

// 平台用户
interface PlatformUser {
  id: number | string
  username: string
  display_name: string
  email: string
  role_id: number | string
  is_active: boolean
  last_login_at: string
}

// 用户分页响应

// 总览数据
interface PlatformOverview {
  tenant: Tenant
  users_count: number
  roles_count: number
  active_sessions: number
}

export default function PlatformPage() {
  const { data, loading } = useFetch<PlatformOverview>(() => platformAPI.getOverview(), [])
  const { data: usersRes, loading: usersLoading } = useFetch<PageRes<PlatformUser>>(
    () => platformAPI.getUsers({ page: 1, page_size: 20 }),
    []
  )

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const tenant = data.tenant
  const users = usersRes?.items ?? []

  return (
    <div>
      <PageHeader
        title="平台管理"
        description="租户、用户与角色管理"
        breadcrumbs={[{ label: '平台管理' }]}
        icon={<Layers className="w-5 h-5" />}
        gradient
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <StatCard
          title="用户数"
          value={data.users_count}
          icon={<Users className="w-5 h-5" />}
          color="brand"
        />
        <StatCard
          title="角色数"
          value={data.roles_count}
          icon={<ShieldCheck className="w-5 h-5" />}
          color="violet"
        />
        <StatCard
          title="活跃会话"
          value={data.active_sessions}
          icon={<Activity className="w-5 h-5" />}
          color="emerald"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 租户信息 */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400">
              <Building2 className="w-4 h-4" />
            </div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">租户信息</h2>
          </div>
          <dl className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-slate-500 dark:text-slate-400">租户名称</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{tenant?.name || '-'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-slate-500 dark:text-slate-400">租户编码</dt>
              <dd className="font-mono text-slate-900 dark:text-slate-100">{tenant?.code || '-'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-slate-500 dark:text-slate-400">租户 ID</dt>
              <dd className="font-mono text-xs text-slate-700 dark:text-slate-300">{String(tenant?.id ?? '-')}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-slate-500 dark:text-slate-400">创建时间</dt>
              <dd className="text-slate-700 dark:text-slate-300">{tenant?.created_at || '-'}</dd>
            </div>
          </dl>
        </div>

        {/* 用户列表 */}
        <div className="lg:col-span-2 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">用户列表</h2>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              共 {usersRes?.total ?? users.length} 人
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-900/80">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">用户名</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">显示名</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">邮箱</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">状态</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">最近登录</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {usersLoading ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-400">加载中...</td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <Empty description="暂无用户" />
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                      <td className="px-4 py-3 text-slate-900 dark:text-slate-100 font-medium whitespace-nowrap">
                        {u.username || '-'}
                      </td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-200 whitespace-nowrap">
                        {u.display_name || '-'}
                      </td>
                      <td className="px-4 py-3 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {u.email || '-'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {u.is_active ? (
                          <Badge variant="success">启用</Badge>
                        ) : (
                          <Badge variant="default">停用</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {u.last_login_at || '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <AIInsightPanel domain="platform" title="AI 平台运营洞察" className="mt-6" />
    </div>
  )
}
