import { useState } from 'react'
import { CreditCard, Send, Trash2, AlertTriangle } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import { useToast } from '@/hooks/useToast'
import useAuthStore from '@/stores/auth'
import { complianceAPI } from '@/services/compliance'

interface Profile {
  id: number
  user_id: number
  id_card_type: string | null
  id_card_no: string | null
  gender: string | null
  education_level: string | null
  major: string | null
  contract_start: string | null
  contract_end: string | null
  drug_categories: string[] | null
  therapeutic_areas: string[] | null
  authorized_regions: string[] | null
  has_bribery_record: number | null
  registration_no: string | null
  registration_status: string | null
}

const statusVariant: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
  unregistered: 'default',
  registered: 'success',
  revoked: 'error',
}

export default function ComplianceProfilePage() {
  const toast = useToast()
  const userId = useAuthStore((s: { user: { id?: number } | null }) => s.user?.id)
  const { data: profile, loading, refetch } = useFetch<Profile>(
    () => complianceAPI.getProfile(userId!),
    [userId]
  )
  const { data: pending } = useFetch<Array<{ profile_id: number; user_id: number; registration_no: string; revoke_scheduled_at: string; days_left: number }>>(
    () => complianceAPI.listPendingRevokes(),
    []
  )

  const [editOpen, setEditOpen] = useState(false)
  const [revokeOpen, setRevokeOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [form, setForm] = useState({
    id_card_type: '身份证',
    education_level: '',
    major: '',
    contract_start: '',
    contract_end: '',
    drug_categories: '',
    therapeutic_areas: '',
    authorized_regions: '',
    has_bribery_record: false,
    bribery_record_detail: '',
  })

  function openEdit() {
    if (!profile) return
    setForm({
      id_card_type: profile.id_card_type || '身份证',
      education_level: profile.education_level || '',
      major: profile.major || '',
      contract_start: profile.contract_start ? profile.contract_start.slice(0, 10) : '',
      contract_end: profile.contract_end ? profile.contract_end.slice(0, 10) : '',
      drug_categories: (profile.drug_categories || []).join('、'),
      therapeutic_areas: (profile.therapeutic_areas || []).join('、'),
      authorized_regions: (profile.authorized_regions || []).join('、'),
      has_bribery_record: !!profile.has_bribery_record,
      bribery_record_detail: '',
    })
    setEditOpen(true)
  }

  async function handleUpdate() {
    try {
      const data: Record<string, unknown> = {
        id_card_type: form.id_card_type || null,
        education_level: form.education_level || null,
        major: form.major || null,
        contract_start: form.contract_start || null,
        contract_end: form.contract_end || null,
        drug_categories: form.drug_categories ? form.drug_categories.split('、').map((s) => s.trim()) : [],
        therapeutic_areas: form.therapeutic_areas ? form.therapeutic_areas.split('、').map((s) => s.trim()) : [],
        authorized_regions: form.authorized_regions ? form.authorized_regions.split('、').map((s) => s.trim()) : [],
        has_bribery_record: form.has_bribery_record,
      }
      if (form.bribery_record_detail) data.bribery_record_detail = form.bribery_record_detail
      await complianceAPI.updateProfile(userId!, data)
      toast('资质档案已更新（30 日变更时效将触发预警）', 'success')
      setEditOpen(false)
      refetch()
    } catch (e) {
      toast(e instanceof Error ? e.message : '更新失败', 'error')
    }
  }

  async function handleSubmit() {
    try {
      const r = await complianceAPI.submitRegistration(userId!) as { registration_no?: string }
      toast(`备案已提交，备案号：${r.registration_no ?? '-'}`, 'success')
      refetch()
    } catch (e) {
      toast(e instanceof Error ? e.message : '提交失败', 'error')
    }
  }

  async function handleRevoke() {
    if (!reason.trim()) {
      toast('请填写撤销原因', 'error')
      return
    }
    try {
      await complianceAPI.revokeRegistration(userId!, reason.trim())
      toast('备案已撤销（30 日内删除）', 'success')
      setRevokeOpen(false)
      setReason('')
      refetch()
    } catch (e) {
      toast(e instanceof Error ? e.message : '撤销失败', 'error')
    }
  }

  const rows: Array<[string, React.ReactNode]> = [
    ['备案状态', profile?.registration_status ? <Badge variant={statusVariant[profile.registration_status] ?? 'default'}>{profile.registration_status}</Badge> : '-'],
    ['备案号', profile?.registration_no ?? '-'],
    ['证件类型', profile?.id_card_type ?? '-'],
    ['证件号', profile?.id_card_no ?? '-'],
    ['性别', profile?.gender ?? '-'],
    ['学历', profile?.education_level ?? '-'],
    ['专业', profile?.major ?? '-'],
    ['合同起', profile?.contract_start ?? '-'],
    ['合同止', profile?.contract_end ?? '-'],
    ['负责药品类别', (profile?.drug_categories || []).join('、') || '-'],
    ['治疗领域', (profile?.therapeutic_areas || []).join('、') || '-'],
    ['授权区域', (profile?.authorized_regions || []).join('、') || '-'],
    ['商业贿赂记录', profile?.has_bribery_record ? <Badge variant="error">有</Badge> : '无'],
  ]

  return (
    <div>
      <PageHeader
        title="代表备案"
        description="医药代表资质档案管理（第 14-18 条备案管理）"
        breadcrumbs={[{ label: '合规专项' }, { label: '代表备案' }]}
        icon={<CreditCard className="w-5 h-5" />}
        gradient
        actions={
          <>
            <Button variant="secondary" onClick={() => setRevokeOpen(true)} disabled={profile?.registration_status !== 'registered'}>
              <Trash2 className="w-4 h-4" /> 撤销备案
            </Button>
            <Button variant="secondary" onClick={openEdit}>编辑档案</Button>
            <Button onClick={handleSubmit} disabled={profile?.registration_status === 'registered'}>
              <Send className="w-4 h-4" /> 提交备案
            </Button>
          </>
        }
      />

      <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-surface-border-subtle-dark">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">资质档案</h2>
        </div>
        {loading ? (
          <div className="px-5 py-8 text-center text-slate-400">加载中...</div>
        ) : !profile ? (
          <Empty description="暂无资质档案" />
        ) : (
          <dl className="divide-y divide-slate-100 dark:divide-slate-700">
            {rows.map(([k, v]) => (
              <div key={k} className="flex px-5 py-3 text-sm">
                <dt className="w-32 shrink-0 text-slate-500 dark:text-slate-400">{k}</dt>
                <dd className="text-slate-800 dark:text-slate-100">{v}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {pending && pending.length > 0 && (
        <div className="mt-4 rounded-2xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 p-5">
          <h2 className="flex items-center gap-2 text-base font-semibold text-amber-800 dark:text-amber-300">
            <AlertTriangle className="w-4 h-4" /> 待删除备案（30 日时效预警）
          </h2>
          <ul className="mt-2 space-y-1 text-sm text-amber-700 dark:text-amber-200">
            {pending.map((p) => (
              <li key={p.profile_id}>
                备案号 {p.registration_no} · 计划删除 {p.revoke_scheduled_at} · 剩余 {p.days_left} 日
              </li>
            ))}
          </ul>
        </div>
      )}

      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title="编辑资质档案"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditOpen(false)}>取消</Button>
            <Button onClick={handleUpdate}>保存</Button>
          </>
        }
      >
        <div className="space-y-3">
          <Field label="证件类型">
            <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.id_card_type} onChange={(e) => setForm({ ...form, id_card_type: e.target.value })} />
          </Field>
          <Field label="学历">
            <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.education_level} onChange={(e) => setForm({ ...form, education_level: e.target.value })} placeholder="大专/本科/硕士/博士" />
          </Field>
          <Field label="专业">
            <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.major} onChange={(e) => setForm({ ...form, major: e.target.value })} />
          </Field>
          <Field label="合同开始">
            <input type="date" className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.contract_start} onChange={(e) => setForm({ ...form, contract_start: e.target.value })} />
          </Field>
          <Field label="合同结束">
            <input type="date" className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.contract_end} onChange={(e) => setForm({ ...form, contract_end: e.target.value })} />
          </Field>
          <Field label="负责药品类别（、分隔）">
            <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.drug_categories} onChange={(e) => setForm({ ...form, drug_categories: e.target.value })} />
          </Field>
          <Field label="治疗领域（、分隔）">
            <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.therapeutic_areas} onChange={(e) => setForm({ ...form, therapeutic_areas: e.target.value })} />
          </Field>
          <Field label="授权区域（、分隔）">
            <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.authorized_regions} onChange={(e) => setForm({ ...form, authorized_regions: e.target.value })} />
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
            <input type="checkbox" checked={form.has_bribery_record} onChange={(e) => setForm({ ...form, has_bribery_record: e.target.checked })} />
            有商业贿赂记录
          </label>
          {form.has_bribery_record && (
            <Field label="记录说明">
              <input className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-surface-card-dark px-3 py-2 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-400" value={form.bribery_record_detail} onChange={(e) => setForm({ ...form, bribery_record_detail: e.target.value })} />
            </Field>
          )}
        </div>
      </Modal>

      <Modal
        open={revokeOpen}
        onClose={() => setRevokeOpen(false)}
        title="撤销备案"
        footer={
          <>
            <Button variant="ghost" onClick={() => setRevokeOpen(false)}>取消</Button>
            <Button variant="danger" onClick={handleRevoke}>确认撤销</Button>
          </>
        }
      >
        <p className="text-sm text-slate-500 dark:text-slate-400">撤销后将在 30 日内删除备案信息并对外公示（第 17、26 条）。请填写原因。</p>
        <textarea className="input mt-3 h-24" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="撤销原因" />
      </Modal>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">{label}</label>
      {children}
    </div>
  )
}
