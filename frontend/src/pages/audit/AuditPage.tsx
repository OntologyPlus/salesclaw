import { Shield, ScrollText, Download } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { useFetch } from '@/hooks/useFetch'
import { auditAPI } from '@/services/audit'
import AIInsightPanel from '@/components/ai/AIInsightPanel'
import type { PageRes } from '@/types/page'

// Top action
interface TopAction {
  action: string
  count: number
}

// 审计日志
interface AuditLog {
  id: number | string
  actor_id: number | string
  action: string
  target: string
  target_id: number | string
  // 后端 detail 是 JSON 列（v2.1 合规证据链后可能为对象 {prev_hash, record_hash, payload, ...}）
  // 渲染前需安全转为字符串
  detail: string | Record<string, unknown> | null
  ts: string
}

// 把 detail 安全渲染为字符串（兼容字符串/对象/null）
function formatDetail(d: AuditLog['detail']): string {
  if (d == null) return '-'
  if (typeof d === 'string') return d || '-'
  try {
    return JSON.stringify(d)
  } catch {
    return '-'
  }
}

// 分页响应

// 总览数据
interface AuditOverview {
  total_logs: number
  today_logs: number
  top_actions: TopAction[]
}

// 操作类型颜色映射
const actionVariantMap: Record<string, 'default' | 'info' | 'success' | 'warning' | 'error'> = {
  create: 'success',
  update: 'info',
  delete: 'error',
  login: 'default',
  logout: 'default',
  approve: 'success',
  reject: 'warning',
}

function getActionVariant(action: string): 'default' | 'info' | 'success' | 'warning' | 'error' {
  return actionVariantMap[action.toLowerCase()] ?? 'default'
}

export default function AuditPage() {
  const { data, loading } = useFetch<AuditOverview>(() => auditAPI.getOverview(), [])
  const { data: logsRes, loading: logsLoading } = useFetch<PageRes<AuditLog>>(
    () => auditAPI.getLogs({ page: 1, page_size: 20 }),
    []
  )

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const topActions = data.top_actions ?? []
  const logs = logsRes?.items ?? []
  const maxCount = topActions.reduce((m, a) => Math.max(m, a.count || 0), 0) || 1

  // 导出审计日志：构造浏览器端 Blob 下载（后端返回 csv 文本或 json 数组）
  const handleExport = async (format: 'csv' | 'json') => {
    const res = await auditAPI.exportLogs({ format })
    const isCsv = res.format === 'csv'
    const content = isCsv
      ? res.content
      : JSON.stringify(res.items ?? [], null, 2)
    const blob = new Blob([content], {
      type: isCsv ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `audit-logs.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader
        title="审计"
        description="操作日志与安全审计"
        breadcrumbs={[{ label: '审计' }]}
        icon={<Shield className="w-5 h-5" />}
        gradient
        actions={
          <>
            <Button size="sm" variant="secondary" onClick={() => handleExport('csv')}>
              <Download className="w-4 h-4" />
              导出 CSV
            </Button>
            <Button size="sm" variant="secondary" onClick={() => handleExport('json')}>
              <Download className="w-4 h-4" />
              导出 JSON
            </Button>
          </>
        }
      />

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <StatCard
          title="总日志"
          value={data.total_logs}
          icon={<ScrollText className="w-5 h-5" />}
          color="brand"
        />
        <StatCard
          title="今日日志"
          value={data.today_logs}
          icon={<Shield className="w-5 h-5" />}
          color="emerald"
        />
      </div>

      {/* Top 操作 */}
      {topActions.length > 0 && (
        <div className="mb-6 p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-4">高频操作</h2>
          <div className="space-y-3">
            {topActions.map((a, i) => (
              <div key={`${a.action}-${i}`} className="flex items-center gap-3">
                <div className="w-24 shrink-0">
                  <Badge variant={getActionVariant(a.action)}>{a.action}</Badge>
                </div>
                <div className="flex-1 h-6 bg-slate-100 dark:bg-slate-700 rounded-lg overflow-hidden">
                  <div
                    className="h-full bg-brand-500 dark:bg-brand-400 rounded-lg transition-all"
                    style={{ width: `${(a.count / maxCount) * 100}%` }}
                  />
                </div>
                <span className="w-16 text-right text-xs text-slate-600 dark:text-slate-300 shrink-0">
                  {a.count} 次
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 审计日志表 */}
      <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">审计日志</h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            共 {logsRes?.total ?? logs.length} 条
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-900/80">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">时间</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">操作者</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">操作</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">目标</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">目标 ID</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">详情</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {logsLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400">加载中...</td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <Empty description="暂无审计日志" />
                  </td>
                </tr>
              ) : (
                logs.map((log, idx) => (
                  <tr key={log.id ?? idx} className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {log.ts || '-'}
                    </td>
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-200 whitespace-nowrap">
                      {String(log.actor_id ?? '-')}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <Badge variant={getActionVariant(log.action)}>{log.action || '-'}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-200 whitespace-nowrap">
                      {log.target || '-'}
                    </td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 font-mono text-xs whitespace-nowrap">
                      {String(log.target_id ?? '-')}
                    </td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 max-w-xs truncate" title={formatDetail(log.detail)}>
                      {formatDetail(log.detail)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <AIInsightPanel domain="audit" title="AI 审计洞察" className="mt-6" />
    </div>
  )
}
