import {
  Settings as SettingsIcon, Sun, Moon, Languages, PanelLeftClose, PanelLeft,
  User, Mail, Shield, Bell, Cpu, Zap,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import { useFetch } from '@/hooks/useFetch'
import { settingsAPI, type AIConfig, type LlmLog } from '@/services/settings'
import useAppStore from '@/stores/app'
import AIInsightPanel from '@/components/ai/AIInsightPanel'

// 个人资料
interface Profile {
  id: number | string
  username: string
  display_name: string
  email: string
  role_id: number | string
  role_name: string
}

// 通知订阅
interface Subscription {
  id: number | string
  channel: string
  target: string
  config: Record<string, unknown>
}

// 总览数据
interface SettingsOverview {
  profile: Profile
  subscriptions: Subscription[]
}

// 渠道映射
const channelMap: Record<string, string> = {
  email: '邮件',
  sms: '短信',
  webhook: 'Webhook',
  in_app: '站内信',
}

export default function SettingsPage() {
  const { theme, locale, sidebarCollapsed, setTheme, setLocale, toggleSidebar } = useAppStore()
  const { data, loading } = useFetch<SettingsOverview>(() => settingsAPI.getOverview(), [])
  const { data: aiConfig } = useFetch<AIConfig>(() => settingsAPI.getAIConfig(), [])
  const { data: llmLogsData } = useFetch<{ items: LlmLog[]; total: number }>(
    () => settingsAPI.getLLMLogs(10), []
  )

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const llmLogs = llmLogsData?.items ?? []

  const profile = data.profile
  const subscriptions = data.subscriptions ?? []

  return (
    <div>
      <PageHeader
        title="设置"
        description="个人偏好与通知配置"
        breadcrumbs={[{ label: '设置' }]}
        icon={<SettingsIcon className="w-5 h-5" />}
        gradient
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 个人资料 */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400">
              <User className="w-4 h-4" />
            </div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">个人资料</h2>
          </div>
          <dl className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                <User className="w-3.5 h-3.5" /> 用户名
              </dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{profile?.username || '-'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                <User className="w-3.5 h-3.5" /> 显示名
              </dt>
              <dd className="text-slate-700 dark:text-slate-200">{profile?.display_name || '-'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                <Mail className="w-3.5 h-3.5" /> 邮箱
              </dt>
              <dd className="text-slate-700 dark:text-slate-200">{profile?.email || '-'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                <Shield className="w-3.5 h-3.5" /> 角色
              </dt>
              <dd>
                <Badge variant="info">{profile?.role_name || '-'}</Badge>
              </dd>
            </div>
          </dl>
        </div>

        {/* 偏好设置 */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400">
              <SettingsIcon className="w-4 h-4" />
            </div>
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">偏好设置</h2>
          </div>
          <div className="space-y-3">
            {/* 主题切换 */}
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                <span>主题</span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setTheme('light')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    theme === 'light'
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                  }`}
                >
                  浅色
                </button>
                <button
                  onClick={() => setTheme('dark')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    theme === 'dark'
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                  }`}
                >
                  深色
                </button>
              </div>
            </div>

            {/* 语言切换 */}
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                <Languages className="w-4 h-4" />
                <span>语言</span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setLocale('zh-CN')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    locale === 'zh-CN'
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                  }`}
                >
                  中文
                </button>
                <button
                  onClick={() => setLocale('en')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    locale === 'en'
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                  }`}
                >
                  English
                </button>
              </div>
            </div>

            {/* 侧边栏折叠 */}
            <div className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                {sidebarCollapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
                <span>侧边栏折叠</span>
              </div>
              <button
                onClick={toggleSidebar}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  sidebarCollapsed ? 'bg-slate-300 dark:bg-slate-600' : 'bg-brand-600'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    sidebarCollapsed ? 'translate-x-1' : 'translate-x-6'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 通知订阅 */}
      <div className="mt-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-slate-500 dark:text-slate-400" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">通知订阅</h2>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">共 {subscriptions.length} 项</span>
        </div>
        {subscriptions.length === 0 ? (
          <Empty description="暂无通知订阅" />
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {subscriptions.map((sub) => (
              <div key={sub.id} className="px-5 py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                      {sub.target || '-'}
                    </span>
                    <Badge variant="info">{channelMap[sub.channel] ?? sub.channel}</Badge>
                  </div>
                  {sub.config && Object.keys(sub.config).length > 0 && (
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 truncate">
                      {JSON.stringify(sub.config)}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* AI 模型配置 */}
      <div className="mt-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-violet-500" />
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">AI 模型配置</h2>
          </div>
          {aiConfig?.provider && (
            <Badge variant={aiConfig.provider === 'openai' ? 'success' : 'default'}>
              {aiConfig.provider}
            </Badge>
          )}
        </div>
        <div className="px-5 py-4">
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400">Provider</dt>
              <dd className="mt-0.5 font-medium text-slate-900 dark:text-slate-100">
                {aiConfig?.provider || '-'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400">Model</dt>
              <dd className="mt-0.5 font-medium text-slate-900 dark:text-slate-100 truncate" title={aiConfig?.model}>
                {aiConfig?.model || '-'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400">Temperature</dt>
              <dd className="mt-0.5 font-medium text-slate-900 dark:text-slate-100">
                {aiConfig?.temperature ?? '-'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400">Max Tokens</dt>
              <dd className="mt-0.5 font-medium text-slate-900 dark:text-slate-100">
                {aiConfig?.max_tokens ?? '-'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400">思考链</dt>
              <dd className="mt-0.5 font-medium text-slate-900 dark:text-slate-100">
                {aiConfig?.enable_thinking ? '启用' : '关闭'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400">推理预算</dt>
              <dd className="mt-0.5 font-medium text-slate-900 dark:text-slate-100">
                {aiConfig?.reasoning_budget ?? '-'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400">Top P</dt>
              <dd className="mt-0.5 font-medium text-slate-900 dark:text-slate-100">
                {aiConfig?.top_p ?? '-'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500 dark:text-slate-400">Base URL</dt>
              <dd className="mt-0.5 font-medium text-slate-900 dark:text-slate-100 truncate" title={aiConfig?.base_url}>
                {aiConfig?.base_url || '-'}
              </dd>
            </div>
          </dl>
        </div>

        {/* 最近 LLM 调用日志 */}
        <div className="border-t border-slate-200 dark:border-slate-800">
          <div className="flex items-center justify-between px-5 py-3 bg-slate-50 dark:bg-slate-800/40">
            <div className="flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">最近 LLM 调用</h3>
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400">共 {llmLogs.length} 条</span>
          </div>
          {llmLogs.length === 0 ? (
            <div className="px-5 py-6">
              <Empty description="暂无调用记录" />
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-700">
              {llmLogs.map((log) => (
                <div key={log.id} className="px-5 py-2.5 flex items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-medium text-slate-900 dark:text-slate-100 truncate">
                      {log.model || log.provider}
                    </span>
                    <Badge variant={log.status === 'ok' ? 'success' : 'error'}>
                      {log.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 text-slate-500 dark:text-slate-400 shrink-0">
                    <span>{log.prompt_tokens}+{log.completion_tokens} tok</span>
                    <span>{log.duration_ms}ms</span>
                    <span>{log.ts}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AIInsightPanel domain="settings" title="AI 个性化洞察" className="mt-6" />
    </div>
  )
}
