import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  CalendarCheck, Plus, Sparkles, Eye, Send, Trash2, AlertCircle, Wand2, X,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import AIEnhancedPage from '@/components/ai/AIEnhancedPage'
import AIFormFiller from '@/components/ai/AIFormFiller'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import FormField from '@/components/forms/FormField'
import Tabs from '@/components/ui/Tabs'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { salesAPI } from '@/services/sales'

// 计划行
interface PlanItem extends Record<string, unknown> {
  id: number | string
  period?: string
  status?: string
  target_count?: number
  ai_score?: number
  created_at?: string
  items?: PlanDetailItem[]
}

// 计划明细
interface PlanDetailItem {
  hospital_id?: number
  doctor_id?: number
  product_id?: number
  visit_date?: string
  hospital_name?: string
  doctor_name?: string
  product_name?: string
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 医院/医生/产品
interface Option { id: number; name: string }
interface Doctor extends Option { hospital_id?: number }

// AI 推荐项
interface AIRecommend {
  id?: number | string
  hospital_name?: string
  doctor_name?: string
  product_name?: string
  visit_date?: string
  reason?: string
  score?: number
}

// 状态映射
const statusMap: Record<string, { label: string; variant: 'default' | 'warning' | 'success' | 'error' }> = {
  draft: { label: '草稿', variant: 'default' },
  pending: { label: '待审批', variant: 'warning' },
  approved: { label: '已批准', variant: 'success' },
  rejected: { label: '已驳回', variant: 'error' },
}

// 状态 Tabs
const statusTabs = [
  { key: 'all', label: '全部' },
  { key: 'draft', label: '草稿' },
  { key: 'pending', label: '待审批' },
  { key: 'approved', label: '已批准' },
  { key: 'rejected', label: '已驳回' },
]

export default function VisitPlansPage() {
  const toast = useToast()
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(1)
  const pageSize = 10

  // 列表数据
  const { data, loading, error, refetch } = useFetch<PageRes<PlanItem>>(
    () => salesAPI.listPlans({
      status: statusFilter === 'all' ? undefined : statusFilter,
      page,
      page_size: pageSize,
    }),
    [statusFilter, page]
  )

  // 主数据：医院 / 产品
  const { data: hospitals } = useFetch<Option[]>(() => salesAPI.listHospitals(), [])
  const { data: products } = useFetch<Option[]>(() => salesAPI.listProducts(), [])
  const { data: doctors } = useFetch<Doctor[]>(() => salesAPI.listDoctors(), [])

  // 新建计划 Modal
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [form, setForm] = useState({ period: '', target_count: 10 })
  const [formItems, setFormItems] = useState<PlanDetailItem[]>([])

  // AI 推荐 Modal
  const [aiOpen, setAiOpen] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiList, setAiList] = useState<AIRecommend[]>([])
  const [aiSelected, setAiSelected] = useState<Set<number | string>>(new Set())

  // 详情 Modal
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailPlan, setDetailPlan] = useState<PlanItem | null>(null)

  const items = data?.items ?? []
  const total = data?.total ?? 0

  // 医院/医生/产品选项
  const hospitalOptions = (hospitals ?? []).map(h => ({ label: h.name, value: h.id }))
  const productOptions = (products ?? []).map(p => ({ label: p.name, value: p.id }))
  const doctorOptions = (doctors ?? []).map(d => ({ label: d.name, value: d.id }))

  // 添加明细行
  const addFormItem = () => {
    setFormItems(prev => [...prev, { hospital_id: undefined, doctor_id: undefined, product_id: undefined, visit_date: '' }])
  }
  // 更新明细行
  const updateFormItem = (idx: number, patch: Partial<PlanDetailItem>) => {
    setFormItems(prev => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  }
  // 删除明细行
  const removeFormItem = (idx: number) => {
    setFormItems(prev => prev.filter((_, i) => i !== idx))
  }

  // 提交新建计划
  const handleCreate = async () => {
    if (!form.period) {
      toast('请填写周期', 'warning')
      return
    }
    setCreateLoading(true)
    try {
      await salesAPI.createPlan({
        period: form.period,
        target_count: form.target_count,
        items: formItems.filter(it => it.hospital_id),
      })
      toast('计划创建成功', 'success')
      setCreateOpen(false)
      setForm({ period: '', target_count: 10 })
      setFormItems([])
      refetch()
    } catch (e) {
      toast(`创建失败：${(e as Error).message}`, 'error')
    } finally {
      setCreateLoading(false)
    }
  }

  // 提交审批
  const handleSubmit = async (id: number | string) => {
    try {
      await salesAPI.submitPlan(id as number)
      toast('已提交审批', 'success')
      refetch()
    } catch (e) {
      toast(`提交失败：${(e as Error).message}`, 'error')
    }
  }

  // 删除计划
  const handleDelete = async (id: number | string) => {
    if (!confirm('确认删除该计划？')) return
    try {
      await salesAPI.deletePlan(id as number)
      toast('已删除', 'success')
      refetch()
    } catch (e) {
      toast(`删除失败：${(e as Error).message}`, 'error')
    }
  }

  // 查看详情
  const handleView = (plan: PlanItem) => {
    setDetailPlan(plan)
    setDetailOpen(true)
  }

  // 打开 AI 推荐
  const handleAIRecommend = async () => {
    setAiOpen(true)
    setAiLoading(true)
    setAiSelected(new Set())
    try {
      const res = await salesAPI.aiRecommend()
      const list: AIRecommend[] = Array.isArray(res) ? res : (res?.items ?? res?.recommendations ?? [])
      setAiList(list)
    } catch (e) {
      toast(`AI 推荐失败：${(e as Error).message}`, 'error')
      setAiList([])
    } finally {
      setAiLoading(false)
    }
  }

  // 切换 AI 推荐选中
  const toggleAISelect = (id: number | string) => {
    setAiSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // 应用选中的 AI 推荐（加入当前新建表单）
  // 注意：key 必须与列表渲染处的 key 构造规则完全一致（使用带 idx 的 fallback key）
  const handleApplyAI = () => {
    const selected = aiList
      .map((it, i) => ({ it, key: it.id ?? `${it.hospital_name}-${it.doctor_name}-${i}` }))
      .filter(({ key }) => aiSelected.has(key))
      .map(({ it }) => it)
    if (selected.length === 0) {
      toast('请至少选择一条推荐', 'warning')
      return
    }
    const newItems: PlanDetailItem[] = selected.map(it => ({
      hospital_name: it.hospital_name,
      doctor_name: it.doctor_name,
      product_name: it.product_name,
      visit_date: it.visit_date,
    }))
    setFormItems(prev => [...prev, ...newItems])
    setCreateOpen(true)
    setAiOpen(false)
    toast(`已应用 ${selected.length} 条推荐到新建计划`, 'success')
  }

  // 表格列定义
  const columns: Column<PlanItem>[] = [
    {
      key: 'period', title: '周期',
      render: (row) => <span className="font-medium text-slate-900 dark:text-slate-100">{row.period ?? '-'}</span>,
    },
    {
      key: 'target_count', title: '目标数',
      render: (row) => <span>{row.target_count ?? 0} 次</span>,
    },
    {
      key: 'status', title: '状态',
      render: (row) => {
        const st = statusMap[row.status ?? 'draft'] ?? statusMap.draft
        return <Badge variant={st.variant}>{st.label}</Badge>
      },
    },
    {
      key: 'ai_score', title: 'AI 评分',
      render: (row) => typeof row.ai_score === 'number' ? (
        <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
          <Sparkles className="w-3.5 h-3.5" /> {row.ai_score}
        </span>
      ) : <span className="text-slate-400">-</span>,
    },
    { key: 'created_at', title: '创建时间', render: (row) => <span className="text-slate-500">{row.created_at ?? '-'}</span> },
    {
      key: 'actions', title: '操作', width: '180px',
      render: (row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleView(row)}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-700 transition-colors"
            title="查看详情"
          >
            <Eye className="w-4 h-4" />
          </button>
          {row.status === 'draft' && (
            <button
              onClick={() => handleSubmit(row.id)}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-sky-600 dark:hover:bg-slate-700 transition-colors"
              title="提交审批"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={() => handleDelete(row.id)}
            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-rose-600 dark:hover:bg-slate-700 transition-colors"
            title="删除"
          >
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
          title="拜访计划"
          description="月度/周度拜访计划编制、提交、审批与 AI 优化"
          breadcrumbs={[{ label: '销售执行' }, { label: '拜访计划' }]}
          icon={<CalendarCheck className="w-5 h-5" />}
          actions={
            <>
              <AIActionButton label="AI优化计划" prompt="根据我的拜访计划，给出优先级调整建议" variant="ghost" size="sm" />
              <Button variant="secondary" onClick={handleAIRecommend}>
                <Wand2 className="w-4 h-4" />
                AI 智能推荐
              </Button>
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="w-4 h-4" />
                新建计划
              </Button>
            </>
          }
        />
      }
    >
      {/* 状态过滤 */}
      <div className="mb-4">
        <Tabs tabs={statusTabs} activeKey={statusFilter} onChange={(k) => { setStatusFilter(k); setPage(1) }} />
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <DataTable<PlanItem>
        columns={columns}
        data={items}
        loading={loading}
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        rowKey="id"
        emptyResource="拜访计划"
        emptyDescription="还没有任何拜访计划"
        emptyContext={`用户角色：${localStorage.getItem('role') || 'sales'}；当前时间：${new Date().toISOString().slice(0, 10)}`}
        aiExplainable={(row) => {
          const items = Array.isArray(row.items) ? row.items : []
          return `拜访计划：周期=${row.period}，状态=${row.status}，目标=${row.target_count}，AI 评分=${row.ai_score}，明细数=${items.length}`}
        }
      />

      {/* 新建计划 Modal */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建拜访计划"
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button loading={createLoading} onClick={handleCreate}>创建</Button>
          </>
        }
      >
        <div className="space-y-4">
          {/* AI 智能预填 */}
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20 border border-brand-200/40 dark:border-brand-800/40">
            <Sparkles className="w-4 h-4 text-brand-500 shrink-0" />
            <div className="flex-1 text-xs text-slate-600 dark:text-slate-300">
              让 AI 基于你的画像和近期模式预填
            </div>
            <AIFormFiller
              formSchema={`{
  "period": "周期（YYYY-MM 或 YYYY-Wnn）",
  "target_count": "目标拜访数量（数字 5-30）",
  "first_visit_date": "首次拜访日期（YYYY-MM-DD）"
}`}
              context={`当前时间：${new Date().toISOString().slice(0, 10)}`}
              onFill={(data) => {
                setForm(prev => ({
                  ...prev,
                  period: data.period || prev.period,
                  target_count: Number(data.target_count) || prev.target_count,
                }))
                // 首项日期也尝试填充
                if (data.first_visit_date && formItems[0]) {
                  setFormItems(prev => prev.map((it, i) => i === 0 ? { ...it, visit_date: data.first_visit_date } : it))
                }
              }}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField label="周期" required hint="如 2026-07 或 2026-W28">
              <Input
                placeholder="请输入周期，如 2026-07"
                value={form.period}
                onChange={(e) => setForm(prev => ({ ...prev, period: e.target.value }))}
              />
            </FormField>
            <FormField label="目标拜访数" required>
              <Input
                type="number"
                min={1}
                value={form.target_count}
                onChange={(e) => setForm(prev => ({ ...prev, target_count: Number(e.target.value) || 0 }))}
              />
            </FormField>
          </div>

          {/* 明细列表 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">明细列表</span>
              <Button size="sm" variant="ghost" onClick={addFormItem}>
                <Plus className="w-4 h-4" /> 添加明细
              </Button>
            </div>
            {formItems.length === 0 ? (
              <p className="text-xs text-slate-400 py-4 text-center">暂无明细，点击"添加明细"创建</p>
            ) : (
              <div className="space-y-2">
                {formItems.map((it, idx) => (
                  <div key={idx} className="grid grid-cols-1 sm:grid-cols-5 gap-2 items-end p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                    <Select
                      label="医院"
                      options={hospitalOptions}
                      value={it.hospital_id}
                      onChange={(e) => updateFormItem(idx, { hospital_id: Number(e.target.value) })}
                    />
                    <Select
                      label="医生"
                      options={doctorOptions}
                      value={it.doctor_id}
                      onChange={(e) => updateFormItem(idx, { doctor_id: Number(e.target.value) })}
                    />
                    <Select
                      label="产品"
                      options={productOptions}
                      value={it.product_id}
                      onChange={(e) => updateFormItem(idx, { product_id: Number(e.target.value) })}
                    />
                    <Input
                      label="拜访日期"
                      type="date"
                      value={it.visit_date ?? ''}
                      onChange={(e) => updateFormItem(idx, { visit_date: e.target.value })}
                    />
                    <button
                      onClick={() => removeFormItem(idx)}
                      className="h-10 inline-flex items-center justify-center rounded-xl text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/30 transition-colors"
                      title="删除明细"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Modal>

      {/* AI 推荐 Modal */}
      <Modal
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        title="AI 智能推荐拜访计划"
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAiOpen(false)}>取消</Button>
            <Button onClick={handleApplyAI} disabled={aiSelected.size === 0}>
              应用选中（{aiSelected.size}）
            </Button>
          </>
        }
      >
        {aiLoading ? (
          <div className="py-8 text-center text-sm text-slate-500">
            <Sparkles className="w-6 h-6 mx-auto mb-2 animate-pulse text-brand-500" />
            AI 正在生成推荐方案...
          </div>
        ) : aiList.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">暂无推荐数据</p>
        ) : (
          <div className="space-y-2">
            {aiList.map((rec, i) => {
              const key = rec.id ?? `${rec.hospital_name}-${rec.doctor_name}-${i}`
              const checked = aiSelected.has(key)
              return (
                <motion.div
                  key={key}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className={`flex items-start gap-3 p-4 rounded-xl border transition-colors cursor-pointer ${
                    checked
                      ? 'border-brand-400 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-slate-200 dark:border-slate-700 hover:border-brand-300'
                  }`}
                  onClick={() => toggleAISelect(key)}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleAISelect(key)}
                    className="mt-0.5 w-4 h-4 rounded accent-brand-600"
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                        {rec.hospital_name ?? '-'}
                      </span>
                      <span className="text-xs text-slate-500">·</span>
                      <span className="text-sm text-slate-700 dark:text-slate-300">{rec.doctor_name ?? '-'}</span>
                      <span className="text-xs text-slate-500">·</span>
                      <span className="text-sm text-slate-700 dark:text-slate-300">{rec.product_name ?? '-'}</span>
                      {rec.visit_date && (
                        <Badge variant="info">{rec.visit_date}</Badge>
                      )}
                    </div>
                    {rec.reason && (
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{rec.reason}</p>
                    )}
                  </div>
                  {typeof rec.score === 'number' && (
                    <div className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 shrink-0">
                      <Sparkles className="w-3.5 h-3.5" />
                      {rec.score}
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        )}
      </Modal>

      {/* 详情 Modal */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title="计划详情"
        size="lg"
        footer={<Button variant="secondary" onClick={() => setDetailOpen(false)}>关闭</Button>}
      >
        {detailPlan && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-slate-400">周期</p>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{detailPlan.period ?? '-'}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">状态</p>
                <div className="mt-0.5">
                  {(() => {
                    const st = statusMap[detailPlan.status ?? 'draft'] ?? statusMap.draft
                    return <Badge variant={st.variant}>{st.label}</Badge>
                  })()}
                </div>
              </div>
              <div>
                <p className="text-xs text-slate-400">目标数</p>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{detailPlan.target_count ?? 0} 次</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">AI 评分</p>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{detailPlan.ai_score ?? '-'}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">创建时间</p>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{detailPlan.created_at ?? '-'}</p>
              </div>
            </div>
            {detailPlan.items && detailPlan.items.length > 0 && (
              <div>
                <p className="text-xs text-slate-400 mb-2">明细</p>
                <div className="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-700/40">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300">医院</th>
                        <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300">医生</th>
                        <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300">产品</th>
                        <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300">日期</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                      {detailPlan.items.map((it, i) => (
                        <tr key={i}>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{it.hospital_name ?? '-'}</td>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{it.doctor_name ?? '-'}</td>
                          <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{it.product_name ?? '-'}</td>
                          <td className="px-3 py-2 text-slate-500">{it.visit_date ?? '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </AIEnhancedPage>
  )
}
