import { useState } from 'react'
import { FileSignature, ShieldCheck, DoorClosed, DoorOpen } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Badge from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'
import { useFetch } from '@/hooks/useFetch'
import { useToast } from '@/hooks/useToast'
import useAuthStore from '@/stores/auth'
import { complianceAPI } from '@/services/compliance'

interface OnboardingCheck {
  user_id: number
  trainings: Array<{ id: number; title: string; status: string; progress: number; passed: boolean }>
  exams: Array<{ id: number; title: string; passed: boolean; score: number | null }>
  commitment: { signed: boolean; version: string | null }
  all_passed: boolean
}

interface OnboardingGate {
  user_id: number
  allowed: boolean
  reasons: string[]
}

export default function ComplianceCommitmentPage() {
  const toast = useToast()
  const userId = useAuthStore((s) => s.user?.id) as number
  const { data: check } = useFetch<OnboardingCheck>(
    () => complianceAPI.checkOnboarding(userId),
    [userId]
  )
  const { data: gate } = useFetch<OnboardingGate>(
    () => complianceAPI.checkOnboardingGate(userId),
    [userId]
  )
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    commitment_type: 'employment_ethics',
    commitment_text: '本人承诺遵守《医药代表管理办法》、公司合规准则及医药代表职业操守，不参与商业贿赂、不违规接触医疗卫生人员。',
    version: '2024.1',
    course_id: '' as string,
    exam_record_id: '' as string,
  })
  const [signing, setSigning] = useState(false)

  async function handleSign() {
    setSigning(true)
    try {
      await complianceAPI.signCommitment({
        commitment_type: form.commitment_type,
        commitment_text: form.commitment_text,
        version: form.version,
        course_id: form.course_id ? Number(form.course_id) : null,
        exam_record_id: form.exam_record_id ? Number(form.exam_record_id) : null,
      })
      toast('合规承诺已签署（第 9、10、15 条）', 'success')
      setOpen(false)
    } catch (e) {
      toast(e instanceof Error ? e.message : '签署失败', 'error')
    } finally {
      setSigning(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="合规承诺 / 准入"
        description="医药代表从业准入：培训+考试+承诺三件套（第 9、10、15 条）"
        breadcrumbs={[{ label: '合规专项' }, { label: '合规承诺' }]}
        icon={<FileSignature className="w-5 h-5" />}
        gradient
        actions={<Button onClick={() => setOpen(true)}><FileSignature className="w-4 h-4" /> 签署承诺</Button>}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">培训</h2>
          <ul className="mt-3 space-y-2">
            {check?.trainings?.map((t) => (
              <li key={t.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-600 dark:text-slate-300">{t.title}</span>
                <Badge variant={t.passed ? 'success' : 'warning'}>{t.passed ? '已完成' : `${t.progress}%`}</Badge>
              </li>
            )) ?? <li className="text-sm text-slate-400">加载中...</li>}
          </ul>
        </div>

        <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">考试</h2>
          <ul className="mt-3 space-y-2">
            {check?.exams?.map((e) => (
              <li key={e.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-600 dark:text-slate-300">{e.title}</span>
                <Badge variant={e.passed ? 'success' : 'error'}>{e.passed ? `通过 ${e.score ?? ''}` : '未通过'}</Badge>
              </li>
            )) ?? <li className="text-sm text-slate-400">加载中...</li>}
          </ul>
        </div>

        <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">承诺</h2>
          <div className="mt-3 text-sm">
            {check?.commitment?.signed ? (
              <Badge variant="success">已签署 v{check.commitment.version}</Badge>
            ) : (
              <Badge variant="warning">未签署</Badge>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-slate-100">
          {gate?.allowed ? <DoorOpen className="w-4 h-4 text-emerald-500" /> : <DoorClosed className="w-4 h-4 text-rose-500" />}
          准入门禁
        </h2>
        {gate?.allowed ? (
          <p className="mt-2 text-sm text-emerald-600 dark:text-emerald-400">已满足从业准入条件，可上岗。</p>
        ) : (
          <div className="mt-2">
            <p className="text-sm text-rose-600 dark:text-rose-400">存在未满足的准入条件：</p>
            <ul className="mt-1 list-disc list-inside text-sm text-slate-600 dark:text-slate-300">
              {gate?.reasons?.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        )}
        <div className="mt-3">
          <Badge variant={check?.all_passed ? 'success' : 'warning'}>
            {check?.all_passed ? '三件套齐备' : '三件套未齐备'}
          </Badge>
        </div>
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="签署合规承诺"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>取消</Button>
            <Button onClick={handleSign} disabled={signing}>{signing ? '签署中...' : '确认签署'}</Button>
          </>
        }
      >
        <div className="space-y-3">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">承诺类型</label>
          <select
            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            value={form.commitment_type}
            onChange={(e) => setForm({ ...form, commitment_type: e.target.value })}
          >
            <option value="employment_ethics">职业操守承诺</option>
            <option value="no_bribery">反商业贿赂承诺</option>
            <option value="data_compliance">数据合规承诺</option>
          </select>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">承诺内容</label>
          <textarea
            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm h-28"
            value={form.commitment_text}
            onChange={(e) => setForm({ ...form, commitment_text: e.target.value })}
          />
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">版本</label>
          <input
            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            value={form.version}
            onChange={(e) => setForm({ ...form, version: e.target.value })}
          />
          <p className="text-xs text-slate-400">签署后将作为准入门禁的承诺条件（选填关联培训/考试记录）。</p>
        </div>
      </Modal>
    </div>
  )
}
