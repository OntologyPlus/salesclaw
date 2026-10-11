import { useState } from 'react'
import { Megaphone, Plus, Send } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'
import { useFetch } from '@/hooks/useFetch'
import { useToast } from '@/hooks/useToast'
import { complianceAPI, type PublicDisclosure, type PageRes } from '@/services/compliance'

const categoryLabel: Record<string, string> = {
  violation_disposal: '违规处置',
  registration_anomaly: '备案异常',
  commitment_breach: '承诺违约',
}

const statusVariant: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  draft: 'default',
  published: 'success',
  withdrawn: 'error',
}

export default function ComplianceDisclosurePage() {
  const toast = useToast()
  const { data, loading, refetch } = useFetch<PageRes<PublicDisclosure>>(
    () => complianceAPI.listDisclosures({ page: 1, page_size: 50 }),
    []
  )
  const [modalOpen, setModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    category: 'violation_disposal',
    title: '',
    disclosed_level: 'internal',
    summary: '',
  })

  const items = data?.items ?? []

  async function handleCreate() {
    if (!form.title.trim()) {
      toast('请填写公示标题', 'error')
      return
    }
    setSubmitting(true)
    try {
      await complianceAPI.createDisclosure({
        category: form.category,
        title: form.title.trim(),
        disclosed_level: form.disclosed_level,
        content: { summary: form.summary },
      })
      toast('公示已登记（草稿态）', 'success')
      setModalOpen(false)
      setForm({ category: 'violation_disposal', title: '', disclosed_level: 'internal', summary: '' })
      refetch()
    } catch (e) {
      toast(e instanceof Error ? e.message : '登记失败', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  async function handlePublish(id: number) {
    try {
      await complianceAPI.publishDisclosure(id)
      toast('公示已发布', 'success')
      refetch()
    } catch (e) {
      toast(e instanceof Error ? e.message : '发布失败', 'error')
    }
  }

  return (
    <div>
      <PageHeader
        title="合规公示"
        description="将违规处置、备案异常等需监督的信息登记并对外公示（《医药代表管理办法》第 13 条）"
        breadcrumbs={[{ label: '合规专项' }, { label: '公示' }]}
        icon={<Megaphone className="w-5 h-5" />}
        gradient
        actions={
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="w-4 h-4" /> 新建公示
          </Button>
        }
      />

      <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">公示列表</h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">共 {data?.total ?? items.length} 条</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-surface-card-dark/80">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">标题</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">类别</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">公示级别</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">状态</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">发布时间</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {loading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">加载中...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={6}><Empty description="暂无公示记录" /></td></tr>
              ) : (
                items.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                    <td className="px-4 py-3 text-slate-800 dark:text-slate-100">{d.title}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                      {categoryLabel[d.category] ?? d.category}
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                      <Badge variant={d.disclosed_level === 'public' ? 'info' : 'default'}>
                        {d.disclosed_level === 'public' ? '对外' : '内部'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <Badge variant={statusVariant[d.status] ?? 'default'}>{d.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {d.published_at ?? '-'}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {d.status === 'draft' && (
                        <Button size="sm" variant="secondary" onClick={() => handlePublish(d.id)}>
                          <Send className="w-3.5 h-3.5" /> 发布
                        </Button>
                      )}
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
        title="新建合规公示"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>取消</Button>
            <Button loading={submitting} onClick={handleCreate}>登记</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">类别</label>
            <select
              className="w-full h-10 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 text-sm"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              <option value="violation_disposal">违规处置</option>
              <option value="registration_anomaly">备案异常</option>
              <option value="commitment_breach">承诺违约</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">标题</label>
            <input
              className="w-full h-10 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 text-sm"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="如：某代表违反第24条处置公示"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">公示级别</label>
            <select
              className="w-full h-10 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 text-sm"
              value={form.disclosed_level}
              onChange={(e) => setForm({ ...form, disclosed_level: e.target.value })}
            >
              <option value="internal">内部</option>
              <option value="public">对外</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">摘要</label>
            <textarea
              className="w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm"
              rows={3}
              value={form.summary}
              onChange={(e) => setForm({ ...form, summary: e.target.value })}
              placeholder="违规事实摘要（脱敏后对外展示）"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
