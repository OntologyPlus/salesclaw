import { useState } from 'react'
import { Users, Plus, Edit3, Trash2, Search, Sparkles, AlertCircle } from 'lucide-react'
import { motion } from 'framer-motion'
import PageHeader from '@/components/data/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Input from '@/components/ui/Input'
import Modal from '@/components/ui/Modal'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { personaAPI } from '@/services/persona'

interface Persona extends Record<string, unknown> {
  id: number
  name: string
  priority: number
  keywords: string[]
  exclusion_keywords?: string[]
  default_brief?: string
  persona_text?: string
  persona_type?: string
  is_active?: number
}

const TYPE_MAP: Record<string, { label: string; variant: 'default' | 'info' | 'warning' }> = {
  customer: { label: '客户', variant: 'info' },
  manager: { label: '管理者', variant: 'warning' },
  expert: { label: '专家', variant: 'default' },
}

export default function PersonaLibraryPage() {
  const toast = useToast()
  const { data, loading, error, refetch } = useFetch<{ items: Persona[]; total: number }>(
    () => personaAPI.list({ page: 1, page_size: 100 }),
    []
  )

  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Persona | null>(null)
  const [matchText, setMatchText] = useState('')
  const [matchResult, setMatchResult] = useState<Persona | null>(null)
  const [matching, setMatching] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)

  // 表单
  const [form, setForm] = useState({
    name: '',
    priority: 0,
    keywords: '',
    exclusion_keywords: '',
    default_brief: '',
    persona_text: '',
    persona_type: 'customer',
  })

  const openCreate = () => {
    setEditing(null)
    setForm({
      name: '',
      priority: 0,
      keywords: '',
      exclusion_keywords: '',
      default_brief: '',
      persona_text: '',
      persona_type: 'customer',
    })
    setShowModal(true)
  }

  const openEdit = (p: Persona) => {
    setEditing(p)
    setForm({
      name: p.name,
      priority: p.priority,
      keywords: (p.keywords ?? []).join(', '),
      exclusion_keywords: (p.exclusion_keywords ?? []).join(', '),
      default_brief: p.default_brief ?? '',
      persona_text: p.persona_text ?? '',
      persona_type: p.persona_type ?? 'customer',
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast('请输入角色名称', 'warning')
      return
    }
    setSaving(true)
    const payload = {
      name: form.name.trim(),
      priority: Number(form.priority) || 0,
      keywords: form.keywords.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      exclusion_keywords: form.exclusion_keywords.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      default_brief: form.default_brief.trim() || null,
      persona_text: form.persona_text.trim() || null,
      persona_type: form.persona_type,
      is_active: 1,
    }
    try {
      if (editing) {
        await personaAPI.update(editing.id, payload)
        toast('角色画像已更新', 'success')
      } else {
        await personaAPI.create(payload)
        toast('角色画像已创建', 'success')
      }
      setShowModal(false)
      refetch()
    } catch (e) {
      toast(`保存失败：${(e as Error).message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除该角色画像？')) return
    setDeleting(id)
    try {
      await personaAPI.delete(id)
      toast('已删除', 'success')
      refetch()
    } catch (e) {
      toast(`删除失败：${(e as Error).message}`, 'error')
    } finally {
      setDeleting(null)
    }
  }

  const handleMatch = async () => {
    if (!matchText.trim()) return
    setMatching(true)
    setMatchResult(null)
    try {
      const res = await personaAPI.match(matchText)
      setMatchResult(res)
      if (res?.id) {
        toast(`匹配到角色：${res.name}`, 'success')
      } else {
        toast('未匹配到合适的角色', 'info')
      }
    } catch (e) {
      toast(`匹配失败：${(e as Error).message}`, 'error')
    } finally {
      setMatching(false)
    }
  }

  const personas = data?.items ?? []

  return (
    <div>
      <PageHeader
        title="角色画像库"
        description="客户/管理者/专家画像定义，支撑剧本解析与场景匹配"
        breadcrumbs={[{ label: '智能培训' }, { label: '角色画像库' }]}
        icon={<Users className="w-5 h-5" />}
        actions={<Button size="sm" onClick={openCreate}><Plus className="w-4 h-4" /> 新建画像</Button>}
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      {/* 角色匹配测试 */}
      <div className="mb-6 rounded-2xl bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20 border border-brand-200 dark:border-brand-800 p-5">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-brand-500" />
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">角色匹配演示</h3>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">输入一段剧本或场景描述，系统将基于关键词命中数 × 优先级 自动匹配最合适的角色画像。</p>
        <div className="flex items-start gap-2">
          <textarea
            value={matchText}
            onChange={(e) => setMatchText(e.target.value)}
            placeholder="例：某三甲医院心内科主任，关注 PCI 术后抗血小板治疗的长期安全性..."
            className="flex-1 px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 dark:text-slate-100 min-h-[72px] resize-y"
          />
          <Button onClick={handleMatch} loading={matching} disabled={!matchText.trim()}>
            <Search className="w-4 h-4" /> 匹配
          </Button>
        </div>
        {matchResult && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800"
          >
            {matchResult.id ? (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="success">已匹配</Badge>
                  <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{matchResult.name}</span>
                  <span className="text-xs text-slate-400">优先级 {matchResult.priority}</span>
                </div>
                {matchResult.default_brief && <p className="text-xs text-slate-500 dark:text-slate-400">{matchResult.default_brief}</p>}
              </div>
            ) : (
              <p className="text-sm text-slate-500">无匹配结果</p>
            )}
          </motion.div>
        )}
      </div>

      {/* 画像列表 */}
      <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">画像列表（{personas.length}）</h2>
        </div>
        {loading ? (
          <div className="p-5"><Skeleton lines={6} /></div>
        ) : personas.length === 0 ? (
          <Empty description="暂无角色画像，点击右上角新建" />
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {personas.map((p, i) => {
              const typeInfo = TYPE_MAP[p.persona_type ?? 'customer'] ?? TYPE_MAP.customer
              return (
                <motion.div
                  key={p.id ?? i}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{p.name}</span>
                        <Badge variant={typeInfo.variant}>{typeInfo.label}</Badge>
                        <span className="text-xs text-slate-400">优先级 {p.priority}</span>
                        {p.is_active === 0 && <Badge variant="default">已停用</Badge>}
                      </div>
                      {p.default_brief && <p className="text-sm text-slate-600 dark:text-slate-300 mb-1.5">{p.default_brief}</p>}
                      <div className="flex items-center gap-1 flex-wrap">
                        {(p.keywords ?? []).map((k, ki) => (
                          <span key={ki} className="px-1.5 py-0.5 rounded text-xs bg-brand-50 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300">
                            #{k}
                          </span>
                        ))}
                        {(p.exclusion_keywords ?? []).length > 0 && (
                          <span className="px-1.5 py-0.5 rounded text-xs bg-rose-50 text-rose-600 dark:bg-rose-900/30 dark:text-rose-300">
                            排除：{(p.exclusion_keywords ?? []).join('、')}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => openEdit(p)}
                        className="p-1.5 rounded-md text-slate-400 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/30 transition-colors"
                        title="编辑"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(p.id)}
                        disabled={deleting === p.id}
                        className="p-1.5 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-900/30 transition-colors disabled:opacity-50"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>

      {/* 新建/编辑 Modal */}
      <Modal
        open={showModal}
        onClose={() => setShowModal(false)}
        title={editing ? '编辑角色画像' : '新建角色画像'}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
            <Button onClick={handleSave} loading={saving}>保存</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <FormField label="角色名称" required>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="例：心内科主任" />
            </FormField>
            <FormField label="角色类型">
              <select
                value={form.persona_type}
                onChange={(e) => setForm({ ...form, persona_type: e.target.value })}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 dark:text-slate-100"
              >
                <option value="customer">客户</option>
                <option value="manager">管理者</option>
                <option value="expert">专家</option>
              </select>
            </FormField>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="优先级（数字越大越优先）">
              <Input type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} />
            </FormField>
            <FormField label="关键词（逗号分隔）">
              <Input value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} placeholder="PCI, 抗血小板, 心内科" />
            </FormField>
          </div>
          <FormField label="排除关键词（命中则不匹配，逗号分隔）">
            <Input value={form.exclusion_keywords} onChange={(e) => setForm({ ...form, exclusion_keywords: e.target.value })} placeholder="护士, 实习" />
          </FormField>
          <FormField label="默认简介">
            <Input value={form.default_brief} onChange={(e) => setForm({ ...form, default_brief: e.target.value })} placeholder="一句话描述该角色" />
          </FormField>
          <FormField label="角色设定（完整文本）">
            <textarea
              value={form.persona_text}
              onChange={(e) => setForm({ ...form, persona_text: e.target.value })}
              placeholder="详细的角色背景、性格特征、决策风格..."
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 dark:text-slate-100 min-h-[100px] resize-y"
            />
          </FormField>
        </div>
      </Modal>
    </div>
  )
}

// 内联 FormField（避免 import 限制）
function FormField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">
        {label}{required && <span className="text-rose-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}
