import { useState } from 'react'
import { FileUp, Download, Send, Plus } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Modal from '@/components/ui/Modal'
import Select from '@/components/ui/Select'
import { useFetch } from '@/hooks/useFetch'
import { useToast } from '@/hooks/useToast'
import { complianceAPI, type RegulatorySubmission, type PageRes } from '@/services/compliance'

const statusVariant: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  pending: 'default',
  submitted: 'success',
  accepted: 'success',
  rejected: 'error',
  dry_run: 'warning',
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function ComplianceSubmissionPage() {
  const toast = useToast()
  const { data, loading, refetch } = useFetch<PageRes<RegulatorySubmission>>(
    () => complianceAPI.listSubmissions({ page: 1, page_size: 50 }),
    []
  )
  const [modalOpen, setModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [pushing, setPushing] = useState<number | null>(null)
  const [form, setForm] = useState({
    period_type: 'year',
    period_value: String(new Date().getFullYear()),
    submission_type: 'violation_summary',
    format: 'json',
  })

  const items = data?.items ?? []

  async function handleCreate() {
    setSubmitting(true)
    try {
      await complianceAPI.createSubmission(form)
      toast('报送数据包已生成', 'success')
      setModalOpen(false)
      refetch()
    } catch (e) {
      toast(e instanceof Error ? e.message : '生成失败', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleExport(id: number, fmt: string) {
    try {
      const blob = await complianceAPI.exportSubmission(id, fmt)
      downloadBlob(blob, `regulatory_submission_${id}.${fmt}`)
      toast('已开始下载', 'success')
    } catch (e) {
      toast(e instanceof Error ? e.message : '导出失败', 'error')
    }
  }

  async function handlePush(id: number) {
    setPushing(id)
    try {
      const res = await complianceAPI.pushSubmissionExternal(id)
      if (res.dry_run) {
        toast('未配置外部端点，已生成占位回执（DRYRUN）', 'warning')
      } else {
        toast(`已推送，回执：${res.external_ref}`, 'success')
      }
      refetch()
    } catch (e) {
      toast(e instanceof Error ? e.message : '推送失败', 'error')
    } finally {
      setPushing(null)
    }
  }

  return (
    <div>
      <PageHeader
        title="监管报送"
        description="按年/季/月聚合合规数据包并报送药监/卫健部门（《医药代表管理办法》第 26 条）"
        breadcrumbs={[{ label: '合规专项' }, { label: '监管报送' }]}
        icon={<FileUp className="w-5 h-5" />}
        gradient
        actions={
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="w-4 h-4" /> 生成报送包
          </Button>
        }
      />

      <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">报送台账</h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">共 {data?.total ?? items.length} 条</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-surface-card-dark/80">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">周期</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">类型</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">格式</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">状态</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">回执号</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {loading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">加载中...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={6}><Empty description="暂无报送记录" /></td></tr>
              ) : (
                items.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                    <td className="px-4 py-3 text-slate-800 dark:text-slate-100 whitespace-nowrap">{s.period_value}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">{s.submission_type}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">{s.format}</td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <Badge variant={statusVariant[s.status] ?? 'default'}>{s.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 font-mono text-xs whitespace-nowrap">
                      {s.external_ref ?? '-'}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        <Button size="sm" variant="ghost" onClick={() => handleExport(s.id, 'json')}>
                          <Download className="w-3.5 h-3.5" /> JSON
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => handleExport(s.id, 'csv')}>
                          <Download className="w-3.5 h-3.5" /> CSV
                        </Button>
                        <Button size="sm" variant="secondary" loading={pushing === s.id} onClick={() => handlePush(s.id)}>
                          <Send className="w-3.5 h-3.5" /> 推送
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="生成监管报送包"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>取消</Button>
            <Button loading={submitting} onClick={handleCreate}>生成</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Select
            label="周期类型"
            value={form.period_type}
            onChange={(e) => setForm({ ...form, period_type: e.target.value })}
            options={[
              { label: '年（year）', value: 'year' },
              { label: '季（quarter）', value: 'quarter' },
              { label: '月（month）', value: 'month' },
            ]}
          />
          <Input
            label="周期值"
            value={form.period_value}
            onChange={(e) => setForm({ ...form, period_value: e.target.value })}
            placeholder="如 2026 / 2026-Q2 / 2026-08"
          />
          <Select
            label="报送类型"
            value={form.submission_type}
            onChange={(e) => setForm({ ...form, submission_type: e.target.value })}
            options={[
              { label: '违规汇总', value: 'violation_summary' },
              { label: '活动汇总', value: 'activity_summary' },
              { label: '年度', value: 'annual' },
            ]}
          />
          <Select
            label="导出格式"
            value={form.format}
            onChange={(e) => setForm({ ...form, format: e.target.value })}
            options={[
              { label: 'JSON', value: 'json' },
              { label: 'CSV', value: 'csv' },
            ]}
          />
        </div>
      </Modal>
    </div>
  )
}
