/**
 * 合规稽查包导出：按活动 / 违规事件 / 代表 user_id 组装三流合一证据快照。
 */
import { useMemo, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Package, Download, RefreshCw } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import SectionCard from '@/components/layout/SectionCard'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import { complianceAPI } from '@/services/compliance'

export interface AuditPackPayload {
  summary?: string[]
  [key: string]: unknown
}

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function AuditPackPage() {
  const toast = useToast()
  const [params] = useSearchParams()
  const [activityId, setActivityId] = useState(params.get('activity_id') || '')
  const [violationId, setViolationId] = useState(params.get('violation_event_id') || '')
  const [userId, setUserId] = useState(params.get('user_id') || '')
  const [busy, setBusy] = useState(false)
  const [pack, setPack] = useState<AuditPackPayload | null>(null)

  const scopeHint = useMemo(() => {
    const parts: string[] = []
    if (activityId) parts.push(`活动 #${activityId}`)
    if (violationId) parts.push(`违规 #${violationId}`)
    if (userId) parts.push(`代表 user_id=${userId}`)
    return parts.length ? parts.join(' · ') : '未指定范围（将导出近期合规关键审计抽样）'
  }, [activityId, violationId, userId])

  async function loadPack() {
    setBusy(true)
    try {
      const data = (await complianceAPI.getAuditPack({
        activity_id: activityId ? Number(activityId) : undefined,
        violation_event_id: violationId ? Number(violationId) : undefined,
        user_id: userId ? Number(userId) : undefined,
      })) as AuditPackPayload
      setPack(data)
      toast('稽查包已生成', 'success')
    } catch (e) {
      toast(e instanceof Error ? e.message : '生成失败', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function downloadPack() {
    setBusy(true)
    try {
      const blob = await complianceAPI.downloadAuditPack({
        activity_id: activityId ? Number(activityId) : undefined,
        violation_event_id: violationId ? Number(violationId) : undefined,
        user_id: userId ? Number(userId) : undefined,
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const suffix = activityId
        ? `activity_${activityId}`
        : violationId
          ? `violation_${violationId}`
          : userId
            ? `user_${userId}`
            : 'snapshot'
      a.download = `audit_pack_${suffix}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast('已开始下载', 'success')
    } catch (e) {
      try {
        const data =
          pack ||
          ((await complianceAPI.getAuditPack({
            activity_id: activityId ? Number(activityId) : undefined,
            violation_event_id: violationId ? Number(violationId) : undefined,
            user_id: userId ? Number(userId) : undefined,
          })) as AuditPackPayload)
        downloadJson(data, 'audit_pack.json')
        toast('已下载 JSON', 'success')
      } catch (e2) {
        toast(e2 instanceof Error ? e2.message : e instanceof Error ? e.message : '下载失败', 'error')
      }
    } finally {
      setBusy(false)
    }
  }

  const summary = Array.isArray(pack?.summary) ? pack.summary : []

  return (
    <div className="space-y-6">
      <PageHeader
        title="稽查包导出"
        description="一次导出活动协议/签到/费用三流 + 违规事件 + 备案 + AuditLog 证据链快照"
        breadcrumbs={[{ label: '合规专项' }, { label: '稽查包导出' }]}
        icon={<Package className="w-5 h-5" />}
        gradient
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={loadPack} disabled={busy}>
              <RefreshCw className="w-4 h-4" /> 预览
            </Button>
            <Button onClick={downloadPack} disabled={busy}>
              <Download className="w-4 h-4" /> 下载 JSON
            </Button>
          </div>
        }
      />

      <SectionCard title="导出范围">
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input
              label="学术活动 ID"
              value={activityId}
              onChange={(e) => setActivityId(e.target.value.replace(/\D/g, ''))}
              placeholder="可选"
            />
            <Input
              label="违规事件 ID"
              value={violationId}
              onChange={(e) => setViolationId(e.target.value.replace(/\D/g, ''))}
              placeholder="可选"
            />
            <Input
              label="代表 user_id"
              value={userId}
              onChange={(e) => setUserId(e.target.value.replace(/\D/g, ''))}
              placeholder="可选"
            />
          </div>
          <p className="text-xs text-slate-500">当前范围：{scopeHint}</p>
          <p className="text-xs text-slate-400">
            也可从{' '}
            <Link className="text-brand-600 dark:text-brand-400 hover:underline" to="/collab/academic-board">
              学术三流看板
            </Link>{' '}
            或违规列表一键带参进入。
          </p>
        </div>
      </SectionCard>

      {pack && (
        <SectionCard title="摘要">
          <div className="p-5 space-y-3">
            {summary.length ? (
              <ul className="list-disc pl-5 text-sm text-slate-700 dark:text-slate-300 space-y-1">
                {summary.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">无摘要</p>
            )}
            <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-slate-50 dark:bg-surface-raised-dark p-3 text-xs text-slate-700 dark:text-slate-300">
              {JSON.stringify(pack, null, 2)}
            </pre>
          </div>
        </SectionCard>
      )}
    </div>
  )
}
