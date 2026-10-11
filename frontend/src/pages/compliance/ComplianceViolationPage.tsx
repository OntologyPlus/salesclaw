import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertOctagon, BellRing, ScanLine, Package } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import { useToast } from '@/hooks/useToast'
import { complianceAPI } from '@/services/compliance'

interface ViolationEvent {
  id: number
  rule_code: string
  rule_subject: string | null
  description: string | null
  severity: string
  status: string
  entity_type: string | null
  entity_id: number | null
  created_at: string | null
}

interface Alert {
  id: number
  alert_type: string
  subject: string | null
  severity: string
  status: string
  due_date: string | null
}

const sevVariant: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
  low: 'default',
  medium: 'warning',
  high: 'error',
  critical: 'error',
}
const statusVariant: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
  open: 'warning',
  pending: 'warning',
  investigating: 'warning',
  resolved: 'success',
  dismissed: 'default',
}

export default function ComplianceViolationPage() {
  const toast = useToast()
  const { data: events, refetch: refetchEvents } = useFetch<{ items: ViolationEvent[]; total: number }>(
    () => complianceAPI.listViolationEvents({ page: 1, page_size: 100 }),
    []
  )
  const { data: alerts, refetch: refetchAlerts } = useFetch<{ items: Alert[]; total: number }>(
    () => complianceAPI.listAlerts({ page: 1, page_size: 100 }),
    []
  )

  const [handleOpen, setHandleOpen] = useState<{ kind: 'event' | 'alert'; id: number } | null>(null)
  const [result, setResult] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleConfirm() {
    if (!handleOpen) return
    if (!result.trim()) {
      toast('请填写处置结论', 'error')
      return
    }
    setBusy(true)
    try {
      if (handleOpen.kind === 'event') {
        await complianceAPI.handleViolationEvent(handleOpen.id, result.trim(), 'resolved')
      } else {
        await complianceAPI.handleAlert(handleOpen.id, result.trim(), 'resolved')
      }
      toast('处置已提交', 'success')
      setHandleOpen(null)
      setResult('')
      refetchEvents()
      refetchAlerts()
    } catch (e) {
      toast(e instanceof Error ? e.message : '处置失败', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function handleScan() {
    try {
      const r = await complianceAPI.scanDeadlines() as { triggered: number }
      toast(`合规时效扫描完成，触发 ${r.triggered ?? 0} 条预警（第 24、25 条）`, 'success')
      refetchAlerts()
    } catch (e) {
      toast(e instanceof Error ? e.message : '扫描失败', 'error')
    }
  }

  return (
    <div>
      <PageHeader
        title="违规管理"
        description="违规事件处置与合规预警时效（第 11、12、24、25 条）"
        breadcrumbs={[{ label: '合规专项' }, { label: '违规管理' }]}
        icon={<AlertOctagon className="w-5 h-5" />}
        gradient
        actions={
          <div className="flex gap-2">
            <Link to="/compliance/audit-pack">
              <Button variant="secondary"><Package className="w-4 h-4" /> 稽查包</Button>
            </Link>
            <Button onClick={handleScan}><ScanLine className="w-4 h-4" /> 合规时效扫描</Button>
          </div>
        }
      />

      <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark flex items-center gap-2">
          <AlertOctagon className="w-4 h-4 text-rose-500" />
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">违规事件</h2>
          <span className="text-xs text-slate-400">共 {events?.total ?? 0} 条</span>
        </div>
        {!events?.items?.length ? (
          <Empty description="暂无违规事件" />
        ) : (
          <table className="w-full text-sm">
            <thead className="text-slate-400 dark:text-slate-500 text-left">
              <tr className="border-b border-slate-100 dark:border-slate-700">
                <th className="px-5 py-2 font-medium">规则</th>
                <th className="px-5 py-2 font-medium">说明</th>
                <th className="px-5 py-2 font-medium">严重度</th>
                <th className="px-5 py-2 font-medium">状态</th>
                <th className="px-5 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {events.items.map((e) => (
                <tr key={e.id}>
                  <td className="px-5 py-2 text-slate-700 dark:text-slate-200">
                    <div>{e.rule_code}</div>
                    <div className="text-xs text-slate-400">{e.rule_subject ?? '-'}</div>
                  </td>
                  <td className="px-5 py-2 text-slate-600 dark:text-slate-300 max-w-xs truncate">
                    {e.description ?? '-'}
                  </td>
                  <td className="px-5 py-2"><Badge variant={sevVariant[e.severity] ?? 'default'}>{e.severity}</Badge></td>
                  <td className="px-5 py-2"><Badge variant={statusVariant[e.status] ?? 'default'}>{e.status}</Badge></td>
                  <td className="px-5 py-2">
                    <div className="flex gap-2">
                      {e.status !== 'resolved' && e.status !== 'dismissed' && (
                        <Button size="sm" variant="secondary" onClick={() => setHandleOpen({ kind: 'event', id: e.id })}>处置</Button>
                      )}
                      <Link to={`/compliance/audit-pack?violation_event_id=${e.id}${e.entity_type === 'academic_activity' && e.entity_id ? `&activity_id=${e.entity_id}` : ''}`}>
                        <Button size="sm" variant="ghost">导出稽查包</Button>
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="mt-4 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark flex items-center gap-2">
          <BellRing className="w-4 h-4 text-amber-500" />
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">合规预警</h2>
          <span className="text-xs text-slate-400">共 {alerts?.total ?? 0} 条</span>
        </div>
        {!alerts?.items?.length ? (
          <Empty description="暂无预警" />
        ) : (
          <table className="w-full text-sm">
            <thead className="text-slate-400 dark:text-slate-500 text-left">
              <tr className="border-b border-slate-100 dark:border-slate-700">
                <th className="px-5 py-2 font-medium">类型</th>
                <th className="px-5 py-2 font-medium">对象</th>
                <th className="px-5 py-2 font-medium">严重度</th>
                <th className="px-5 py-2 font-medium">截止</th>
                <th className="px-5 py-2 font-medium">状态</th>
                <th className="px-5 py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {alerts.items.map((a) => (
                <tr key={a.id}>
                  <td className="px-5 py-2 text-slate-700 dark:text-slate-200">{a.alert_type}</td>
                  <td className="px-5 py-2 text-slate-600 dark:text-slate-300">{a.subject ?? '-'}</td>
                  <td className="px-5 py-2"><Badge variant={sevVariant[a.severity] ?? 'default'}>{a.severity}</Badge></td>
                  <td className="px-5 py-2 text-slate-600 dark:text-slate-300">{a.due_date ?? '-'}</td>
                  <td className="px-5 py-2"><Badge variant={statusVariant[a.status] ?? 'default'}>{a.status}</Badge></td>
                  <td className="px-5 py-2">
                    {a.status !== 'resolved' && a.status !== 'dismissed' && (
                      <Button size="sm" variant="secondary" onClick={() => setHandleOpen({ kind: 'alert', id: a.id })}>处置</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        open={!!handleOpen}
        onClose={() => setHandleOpen(null)}
        title="处置结论"
        footer={
          <>
            <Button variant="ghost" onClick={() => setHandleOpen(null)}>取消</Button>
            <Button onClick={handleConfirm} disabled={busy}>{busy ? '提交中...' : '确认处置'}</Button>
          </>
        }
      >
        <p className="text-sm text-slate-500 dark:text-slate-400">填写处置结果，提交后该事项标记为 resolved。</p>
        <textarea
          className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm h-28 mt-3"
          value={result}
          onChange={(e) => setResult(e.target.value)}
          placeholder="处置结论"
        />
      </Modal>
    </div>
  )
}
