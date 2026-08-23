import { useState } from 'react'
import { FileText, Plus, Eye, Pencil, Trash2, AlertCircle } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import AIEnhancedPage from '@/components/ai/AIEnhancedPage'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import FormField from '@/components/forms/FormField'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { salesAPI } from '@/services/sales'

// 拜访记录行
interface VisitRecord extends Record<string, unknown> {
  id: number | string
  visit_date?: string
  hospital_id?: number
  doctor_id?: number
  product_id?: number
  hospital?: string | { name?: string }
  doctor?: string | { name?: string }
  product?: string | { name?: string }
  visit_type?: string
  duration?: number
  location?: string
  summary?: string
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 主数据选项
interface Option { id: number; name: string }
interface Doctor extends Option { hospital_id?: number }

// 拜访形式映射
const visitTypeMap: Record<string, string> = {
  academic: '学术拜访',
  daily: '日常拜访',
  meeting: '会议',
}

const visitTypeOptions = [
  { label: '学术拜访', value: 'academic' },
  { label: '日常拜访', value: 'daily' },
  { label: '会议', value: 'meeting' },
]

// 取名称（兼容字符串或对象）
function getName(v: unknown): string {
  if (typeof v === 'string') return v
  if (v && typeof v === 'object' && 'name' in v) return String((v as { name?: string }).name ?? '-')
  return '-'
}

export default function VisitRecordsPage() {
  const toast = useToast()
  const [page, setPage] = useState(1)
  const pageSize = 10

  // 列表数据
  const { data, loading, error, refetch } = useFetch<PageRes<VisitRecord>>(
    () => salesAPI.listRecords({ page, page_size: pageSize }),
    [page]
  )

  // 主数据
  const { data: hospitals } = useFetch<Option[]>(() => salesAPI.listHospitals(), [])
  const { data: doctors } = useFetch<Doctor[]>(() => salesAPI.listDoctors(), [])
  const { data: products } = useFetch<Option[]>(() => salesAPI.listProducts(), [])

  // 表单 Modal
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<VisitRecord | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    visit_date: '',
    hospital_id: '',
    doctor_id: '',
    product_id: '',
    visit_type: 'daily',
    duration: 30,
    location: '',
    summary: '',
  })

  // 详情 Modal
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailRec, setDetailRec] = useState<VisitRecord | null>(null)

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const hospitalOptions = (hospitals ?? []).map(h => ({ label: h.name, value: h.id }))
  const doctorOptions = (doctors ?? []).map(d => ({ label: d.name, value: d.id }))
  const productOptions = (products ?? []).map(p => ({ label: p.name, value: p.id }))

  // 打开新建
  const openCreate = () => {
    setEditing(null)
    setForm({
      visit_date: '',
      hospital_id: '',
      doctor_id: '',
      product_id: '',
      visit_type: 'daily',
      duration: 30,
      location: '',
      summary: '',
    })
    setModalOpen(true)
  }

  // 打开编辑
  const openEdit = (rec: VisitRecord) => {
    setEditing(rec)
    setForm({
      visit_date: rec.visit_date ?? '',
      hospital_id: rec.hospital_id ? String(rec.hospital_id) : '',
      doctor_id: rec.doctor_id ? String(rec.doctor_id) : '',
      product_id: rec.product_id ? String(rec.product_id) : '',
      visit_type: rec.visit_type ?? 'daily',
      duration: rec.duration ?? 30,
      location: rec.location ?? '',
      summary: rec.summary ?? '',
    })
    setModalOpen(true)
  }

  // 保存
  const handleSave = async () => {
    if (!form.visit_date) {
      toast('请选择拜访日期', 'warning')
      return
    }
    setSaving(true)
    try {
      const payload = {
        visit_date: form.visit_date,
        hospital_id: form.hospital_id ? Number(form.hospital_id) : undefined,
        doctor_id: form.doctor_id ? Number(form.doctor_id) : undefined,
        product_id: form.product_id ? Number(form.product_id) : undefined,
        visit_type: form.visit_type,
        duration: Number(form.duration) || 0,
        location: form.location,
        summary: form.summary,
      }
      if (editing) {
        await salesAPI.updateRecord(editing.id as number, payload)
        toast('更新成功', 'success')
      } else {
        await salesAPI.createRecord(payload)
        toast('创建成功', 'success')
      }
      setModalOpen(false)
      refetch()
    } catch (e) {
      toast(`保存失败：${(e as Error).message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  // 删除
  const handleDelete = async (id: number | string) => {
    if (!confirm('确认删除该拜访记录？')) return
    try {
      await salesAPI.deleteRecord(id as number)
      toast('已删除', 'success')
      refetch()
    } catch (e) {
      toast(`删除失败：${(e as Error).message}`, 'error')
    }
  }

  // 查看详情
  const handleView = (rec: VisitRecord) => {
    setDetailRec(rec)
    setDetailOpen(true)
  }

  // 表格列
  const columns: Column<VisitRecord>[] = [
    { key: 'visit_date', title: '拜访日期', render: (r) => <span className="text-slate-700 dark:text-slate-200">{r.visit_date ?? '-'}</span> },
    { key: 'hospital', title: '医院', render: (r) => <span className="font-medium text-slate-900 dark:text-slate-100">{getName(r.hospital)}</span> },
    { key: 'doctor', title: '医生', render: (r) => <span>{getName(r.doctor)}</span> },
    { key: 'product', title: '产品', render: (r) => <span>{getName(r.product)}</span> },
    {
      key: 'visit_type', title: '形式',
      render: (r) => r.visit_type ? (
        <Badge variant="info">{visitTypeMap[r.visit_type] ?? r.visit_type}</Badge>
      ) : <span className="text-slate-400">-</span>,
    },
    { key: 'duration', title: '时长', render: (r) => <span>{r.duration ? `${r.duration} 分钟` : '-'}</span> },
    { key: 'summary', title: '摘要', render: (r) => <span className="text-slate-500 truncate max-w-[200px] inline-block">{r.summary ?? '-'}</span> },
    {
      key: 'actions', title: '操作', width: '140px',
      render: (r) => (
        <div className="flex items-center gap-1">
          <button onClick={() => handleView(r)} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-700 transition-colors" title="查看详情">
            <Eye className="w-4 h-4" />
          </button>
          <button onClick={() => openEdit(r)} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-sky-600 dark:hover:bg-slate-700 transition-colors" title="编辑">
            <Pencil className="w-4 h-4" />
          </button>
          <button onClick={() => handleDelete(r.id)} className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-rose-600 dark:hover:bg-slate-700 transition-colors" title="删除">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ]

  return (
    <AIEnhancedPage
      header={
        <PageHeader
          title="拜访记录"
          description="拜访执行记录、签到、照片与跟进事项"
          breadcrumbs={[{ label: '销售执行' }, { label: '拜访记录' }]}
          icon={<FileText className="w-5 h-5" />}
          actions={
            <>
              <AIActionButton label="AI分析拜访" prompt="分析我最近的拜访记录，给出优化建议" variant="ghost" size="sm" />
              <Button onClick={openCreate}>
                <Plus className="w-4 h-4" />
                新建记录
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

      <DataTable<VisitRecord>
        columns={columns}
        data={items}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
        emptyResource="拜访记录"
        emptyDescription="还没有任何拜访记录"
        emptyContext={`当前时间：${new Date().toISOString().slice(0, 10)}`}
        aiExplainable={(r) => `拜访记录：日期=${r.visit_date}，形式=${visitTypeMap[r.visit_type ?? ''] ?? r.visit_type}，摘要=${(r.summary ?? '').slice(0, 50)}`}
      />

      {/* 新建/编辑 Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? '编辑拜访记录' : '新建拜访记录'}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>取消</Button>
            <Button loading={saving} onClick={handleSave}>{editing ? '保存' : '创建'}</Button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="拜访日期" required>
            <Input type="date" value={form.visit_date} onChange={(e) => setForm(p => ({ ...p, visit_date: e.target.value }))} />
          </FormField>
          <FormField label="拜访形式" required>
            <Select options={visitTypeOptions} value={form.visit_type} onChange={(e) => setForm(p => ({ ...p, visit_type: e.target.value }))} />
          </FormField>
          <FormField label="医院">
            <Select
              options={[{ label: '请选择医院', value: '' }, ...hospitalOptions]}
              value={form.hospital_id}
              onChange={(e) => setForm(p => ({ ...p, hospital_id: e.target.value }))}
            />
          </FormField>
          <FormField label="医生">
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
          <FormField label="时长（分钟）">
            <Input type="number" min={1} value={form.duration} onChange={(e) => setForm(p => ({ ...p, duration: Number(e.target.value) || 0 }))} />
          </FormField>
          <FormField label="地点">
            <Input placeholder="拜访地点" value={form.location} onChange={(e) => setForm(p => ({ ...p, location: e.target.value }))} />
          </FormField>
          <div className="sm:col-span-2">
            <FormField label="摘要">
              <textarea
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-100 min-h-[80px]"
                placeholder="请输入拜访摘要"
                value={form.summary}
                onChange={(e) => setForm(p => ({ ...p, summary: e.target.value }))}
              />
            </FormField>
          </div>
        </div>
      </Modal>

      {/* 详情 Modal */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title="拜访记录详情"
        size="lg"
        footer={<Button variant="secondary" onClick={() => setDetailOpen(false)}>关闭</Button>}
      >
        {detailRec && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div><p className="text-xs text-slate-400">拜访日期</p><p className="text-sm font-medium text-slate-900 dark:text-slate-100">{detailRec.visit_date ?? '-'}</p></div>
            <div><p className="text-xs text-slate-400">形式</p><p className="text-sm font-medium text-slate-900 dark:text-slate-100">{detailRec.visit_type ? (visitTypeMap[detailRec.visit_type] ?? detailRec.visit_type) : '-'}</p></div>
            <div><p className="text-xs text-slate-400">医院</p><p className="text-sm font-medium text-slate-900 dark:text-slate-100">{getName(detailRec.hospital)}</p></div>
            <div><p className="text-xs text-slate-400">医生</p><p className="text-sm font-medium text-slate-900 dark:text-slate-100">{getName(detailRec.doctor)}</p></div>
            <div><p className="text-xs text-slate-400">产品</p><p className="text-sm font-medium text-slate-900 dark:text-slate-100">{getName(detailRec.product)}</p></div>
            <div><p className="text-xs text-slate-400">时长</p><p className="text-sm font-medium text-slate-900 dark:text-slate-100">{detailRec.duration ? `${detailRec.duration} 分钟` : '-'}</p></div>
            <div><p className="text-xs text-slate-400">地点</p><p className="text-sm font-medium text-slate-900 dark:text-slate-100">{detailRec.location ?? '-'}</p></div>
            <div className="sm:col-span-2"><p className="text-xs text-slate-400">摘要</p><p className="text-sm text-slate-700 dark:text-slate-200">{detailRec.summary ?? '-'}</p></div>
          </div>
        )}
      </Modal>
    </AIEnhancedPage>
  )
}
