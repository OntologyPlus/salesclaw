import { useState, type FormEvent } from 'react'
import { HelpCircle, Search, Eye, ChevronDown, ChevronUp } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import { knowledgeAPI } from '@/services/knowledge'

interface FaqItem {
  id: number
  question: string
  answer: string
  category: string
  sort_order?: number
  view_count?: number
  created_at?: string
}

interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

const CATEGORY_CONFIG: Record<string, { label: string; cls: string }> = {
  product: { label: '产品', cls: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300' },
  clinical: { label: '临床', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
  compliance: { label: '合规', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
  sales: { label: '销售', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  other: { label: '其他', cls: 'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300' },
}

function CategoryBadge({ category }: { category: string }) {
  const cfg = CATEGORY_CONFIG[category] || CATEGORY_CONFIG.other
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}

export default function FaqListPage() {
  const [keyword, setKeyword] = useState('')
  const [appliedKeyword, setAppliedKeyword] = useState('')
  const [category, setCategory] = useState('all')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { data, loading } = useFetch<PageRes<FaqItem>>(
    () =>
      knowledgeAPI.getFaqs({
        category: category === 'all' ? undefined : category,
        keyword: appliedKeyword || undefined,
        page: 1,
        page_size: 50,
      }),
    [category, appliedKeyword]
  )

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const handleSearch = (e: FormEvent) => {
    e.preventDefault()
    setAppliedKeyword(keyword)
  }

  const toggle = (id: number) => {
    setExpandedId((cur) => (cur === id ? null : id))
  }

  return (
    <div>
      <PageHeader
        title="常见问题"
        description="高频问题与标准答案"
        breadcrumbs={[{ label: '知识库', path: '/knowledge' }, { label: '常见问题' }]}
        icon={<HelpCircle className="w-5 h-5" />}
        actions={<AIActionButton label="AI智能问答" prompt="药品不良反应有哪些？" variant="ghost" size="sm" />}
      />

      {/* 筛选栏 */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索问题"
              className="pl-9 pr-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 w-64"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg bg-brand-600 text-white text-sm hover:bg-brand-700 transition-colors"
          >
            搜索
          </button>
        </form>
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-500 dark:text-slate-400">分类</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="all">全部</option>
            <option value="product">产品</option>
            <option value="clinical">临床</option>
            <option value="compliance">合规</option>
            <option value="sales">销售</option>
            <option value="other">其他</option>
          </select>
        </div>
        <span className="text-sm text-slate-400">共 {total} 条</span>
      </div>

      {/* FAQ 列表 */}
      {loading ? (
        <div className="p-6 text-slate-500">加载中...</div>
      ) : items.length === 0 ? (
        <Empty description="暂无 FAQ" />
      ) : (
        <div className="space-y-3">
          {items.map((faq) => {
            const expanded = expandedId === faq.id
            return (
              <div
                key={faq.id}
                className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => toggle(faq.id)}
                  className="w-full flex items-center gap-3 p-5 text-left hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors"
                >
                  <HelpCircle className="w-5 h-5 text-brand-500 shrink-0" />
                  <span className="flex-1 font-medium text-slate-900 dark:text-slate-100">{faq.question}</span>
                  <CategoryBadge category={faq.category} />
                  <span className="inline-flex items-center gap-1 text-xs text-slate-400 shrink-0">
                    <Eye className="w-3.5 h-3.5" />
                    {faq.view_count ?? 0}
                  </span>
                  {expanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-400 shrink-0" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
                  )}
                </button>
                {expanded && (
                  <div className="px-5 pb-5">
                    <div className="pt-3 border-t border-slate-100 dark:border-slate-700">
                      <p className="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-wrap">{faq.answer}</p>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
