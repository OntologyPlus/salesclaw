import { useState } from 'react'
import { ClipboardCheck, Plus } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'
import { useFetch } from '@/hooks/useFetch'
import { useToast } from '@/hooks/useToast'
import { complianceAPI, type AnnualComplianceAudit, type PageRes } from '@/services/compliance'

const conclusionVariant: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  pass: 'success',
  conditional: 'warning',
  fail: 'error',
  pending: 'default',
}

export default function ComplianceAuditPage() {
  const toast = useToast()
  const { data, loading, refetch } = useFetch<PageRes<AnnualComplianceAudit>>(
    () => complianceAPI.listAnnualAudits({ page: 1, page_size: 50 }),
    []
  )
  const [modalOpen, setModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [year, setYear] = useState(new Date().getFullYear())
  const [scope, setScope] = useState('')

  const items = data?.items ?? []

  async function handleGenerate() {
    setSubmitting(true)
    try {
      await complianceAPI.generateAnnualAudit(year, scope || undefined)
      toast(`${year} 年度审计已生成`, 'success')
      setModalOpen(false)
      refetch()
    } catch (e) {
      toast(e instanceof Error ? e.message : '生成失败', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="年度合规审计"
        description="基于 AuditLog 证据链 + 违规记录 + 公示生成年度审计结论（pass / conditional / fail）"
        breadcrumbs={[{ label: '合规专项' }, { label: '年度审计' }]}
        icon={<ClipboardCheck className="w-5 h-5" />}
        gradient
        actions={
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="w-4 h-4" /> 生成年度审计
          </Button>
        }
      />

      <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">年度审计报告</h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">共 {data?.total ?? items.length} 份</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-surface-card-dark/80">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">年度</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">结论</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">违规总数</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">公示发布数</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">证据链</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">审计时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {loading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">加载中...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={6}><Empty description="暂无年度审计" /></td></tr>
              ) : (
                items.map((a) => {
                  const m = (a.metrics ?? {}) as Record<string, any>
                  const ci = (a.chain_integrity ?? {}) as Record<string, any>
                  return (
                    <tr key={a.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                      <td className="px-4 py-3 text-slate-800 dark:text-slate-100 font-semibold">{a.year}</td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <Badge variant={conclusionVariant[a.conclusion] ?? 'default'}>{a.conclusion}</Badge>
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                        {m.violation_total ?? '-'}
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                        {m.disclosure_published ?? '-'}
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                        {ci.verified ?? 0}/{ci.total ?? 0}
                        {(ci.tampered ?? []).length > 0 && (
                          <Badge variant="error" className="ml-2">篡改{(ci.tampered as unknown[]).length}</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {a.audited_at ?? '-'}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="生成年度合规审计"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>取消</Button>
            <Button loading={submitting} onClick={handleGenerate}>生成</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">年度</label>
            <input
              type="number"
              className="w-full h-10 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 text-sm"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">审计范围（可选）</label>
            <textarea
              className="w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm"
              rows={3}
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder="如：2026 年度合规审计（违规处置 + 公示 + 全过程留痕证据链）"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
