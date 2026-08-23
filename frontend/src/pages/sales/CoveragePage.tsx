import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Map, Plus, AlertCircle, Dumbbell } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import AIEnhancedPage from '@/components/ai/AIEnhancedPage'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Select from '@/components/ui/Select'
import Input from '@/components/ui/Input'
import FormField from '@/components/forms/FormField'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { salesAPI } from '@/services/sales'
import { trainingAPI } from '@/services/training'

// 覆盖分通行
interface Coverage extends Record<string, unknown> {
  id: number | string
  user_id?: number
  user?: string | { name?: string }
  hospital_id?: number
  hospital?: string | { name?: string }
  doctor_id?: number
  doctor?: string | { name?: string }
  product_id?: number
  product?: string | { name?: string }
  role?: string
  start_date?: string
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 主数据
interface Option { id: number; name: string }
interface Doctor extends Option { hospital_id?: number }

// 角色映射
const roleMap: Record<string, { label: string; variant: 'info' | 'default' }> = {
  primary: { label: '主管', variant: 'info' },
  assistant: { label: '协助', variant: 'default' },
}

const roleOptions = [
  { label: '主管', value: 'primary' },
  { label: '协助', value: 'assistant' },
]

// 取名称
function getName(v: unknown): string {
  if (typeof v === 'string') return v
  if (v && typeof v === 'object' && 'name' in v) return String((v as { name?: string }).name ?? '-')
  return '-'
}

export default function CoveragePage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [drillingDoctorId, setDrillingDoctorId] = useState<number | null>(null)
  const pageSize = 10

  // 列表
  const { data, loading, error, refetch } = useFetch<PageRes<Coverage>>(
    () => salesAPI.listCoverage({ page }),
    [page]
  )
  // 主数据
  const { data: hospitals } = useFetch<Option[]>(() => salesAPI.listHospitals(), [])
  const { data: doctors } = useFetch<Doctor[]>(() => salesAPI.listDoctors(), [])
  const { data: products } = useFetch<Option[]>(() => salesAPI.listProducts(), [])

  // 表单 Modal
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    hospital_id: '',
    doctor_id: '',
    product_id: '',
    role: 'primary',
    start_date: '',
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const hospitalOptions = (hospitals ?? []).map(h => ({ label: h.name, value: h.id }))
  const doctorOptions = (doctors ?? []).map(d => ({ label: d.name, value: d.id }))
  const productOptions = (products ?? []).map(p => ({ label: p.name, value: p.id }))

  const openCreate = () => {
    setForm({ hospital_id: '', doctor_id: '', product_id: '', role: 'primary', start_date: '' })
    setModalOpen(true)
  }

  // 保存
  const handleSave = async () => {
    if (!form.hospital_id || !form.doctor_id) {
      toast('请选择医院和医生', 'warning')
      return
    }
    setSaving(true)
    try {
      await salesAPI.assignCoverage({
        hospital_id: Number(form.hospital_id),
        doctor_id: Number(form.doctor_id),
        product_id: form.product_id ? Number(form.product_id) : undefined,
        role: form.role,
        start_date: form.start_date || undefined,
      })
      toast('分配成功', 'success')
      setModalOpen(false)
      refetch()
    } catch (e) {
      toast(`分配失败：${(e as Error).message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  // 基于医生画像生成演练场景并跳转
  const handleDrill = async (doctorId?: number, doctorName?: string) => {
    if (!doctorId) {
      toast('该记录未关联医生，无法生成演练', 'warning')
      return
    }
    setDrillingDoctorId(doctorId)
    try {
      const scenario = await trainingAPI.generateScenarioFromDoctor(doctorId)
      toast(`已为「${doctorName ?? '该医生'}」生成演练场景`, 'success')
      // 跳转到演练页，携带自动启动场景
      navigate('/training/practice', {
        state: { autoStartScenario: scenario, fromDoctorName: doctorName },
      })
    } catch (e) {
      toast(`生成演练失败：${(e as Error).message}`, 'error')
    } finally {
      setDrillingDoctorId(null)
    }
  }

  const columns: Column<Coverage>[] = [
    { key: 'user', title: '代表', render: (r) => <span className="font-medium text-slate-900 dark:text-slate-100">{getName(r.user)}</span> },
    { key: 'hospital', title: '医院', render: (r) => <span>{getName(r.hospital)}</span> },
    { key: 'doctor', title: '医生', render: (r) => <span>{getName(r.doctor)}</span> },
    { key: 'product', title: '产品', render: (r) => <span>{getName(r.product)}</span> },
    {
      key: 'role', title: '角色',
      render: (r) => {
        const st = roleMap[r.role ?? 'primary'] ?? roleMap.primary
        return <Badge variant={st.variant}>{st.label}</Badge>
      },
    },
    { key: 'start_date', title: '开始日期', render: (r) => <span className="text-slate-500">{r.start_date ?? '-'}</span> },
    {
      key: 'actions', title: '操作',
      render: (r) => {
        const doctorId = typeof r.doctor_id === 'number' ? r.doctor_id : Number(r.doctor_id)
        const doctorName = getName(r.doctor)
        const isLoading = drillingDoctorId === doctorId
        return (
          <Button
            size="sm"
            variant="ghost"
            loading={isLoading}
            disabled={!r.doctor_id}
            onClick={() => handleDrill(doctorId, doctorName)}
            title={r.doctor_id ? '基于该医生画像生成 AI 演练场景' : '未关联医生'}
          >
            <Dumbbell className="w-3.5 h-3.5" />
            AI 演练
          </Button>
        )
      },
    },
  ]

  return (
    <AIEnhancedPage
      header={
        <PageHeader
          title="覆盖分管"
          description="客户覆盖、分管与 territory 划分管理"
          breadcrumbs={[{ label: '销售执行' }, { label: '覆盖分管' }]}
          icon={<Map className="w-5 h-5" />}
          actions={
            <>
              <AIActionButton label="AI覆盖分析" prompt="分析我的覆盖空白，推荐应优先覆盖的医院" variant="ghost" size="sm" />
              <Button onClick={openCreate}>
                <Plus className="w-4 h-4" />
                新建分配
              </Button>
            </>
          }
        />
      }
    >
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <DataTable<Coverage>
        columns={columns}
        data={items}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
        emptyResource="覆盖分配"
        emptyDescription="还没有任何覆盖分配"
        emptyContext={`当前时间：${new Date().toISOString().slice(0, 10)}`}
        aiExplainable={(r) => {
          const h = typeof r.hospital === 'object' ? r.hospital?.name : r.hospital
          const u = typeof r.user === 'object' ? r.user?.name : r.user
          return `覆盖分配：代表=${u}，医院=${h}，角色=${r.role}，开始日期=${r.start_date}`
        }}
      />

      {/* 新建分配 Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="新建覆盖分配"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>取消</Button>
            <Button loading={saving} onClick={handleSave}>创建</Button>
          </>
        }
      >
        <div className="space-y-4">
          <FormField label="医院" required>
            <Select
              options={[{ label: '请选择医院', value: '' }, ...hospitalOptions]}
              value={form.hospital_id}
              onChange={(e) => setForm(p => ({ ...p, hospital_id: e.target.value }))}
            />
          </FormField>
          <FormField label="医生" required>
            <Select
              options={[{ label: '请选择医生', value: '' }, ...doctorOptions]}
              value={form.doctor_id}
              onChange={(e) => setForm(p => ({ ...p, doctor_id: e.target.value }))}
            />
          </FormField>
          <FormField label="产品">
            <Select
              options={[{ label: '请选择产品', value: '' }, ...productOptions]}
              value={form.product_id}
              onChange={(e) => setForm(p => ({ ...p, product_id: e.target.value }))}
            />
          </FormField>
          <FormField label="角色" required>
            <Select options={roleOptions} value={form.role} onChange={(e) => setForm(p => ({ ...p, role: e.target.value }))} />
          </FormField>
          <FormField label="开始日期">
            <Input type="date" value={form.start_date} onChange={(e) => setForm(p => ({ ...p, start_date: e.target.value }))} />
          </FormField>
        </div>
      </Modal>
    </AIEnhancedPage>
  )
}
