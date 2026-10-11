import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BookOpen, Search, Eye, FileText, Tag, User } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import Empty from '@/components/ui/Empty'
import useFetch from '@/hooks/useFetch'
import { knowledgeAPI } from '@/services/knowledge'
import type { PageRes } from '@/types/page'

interface DocumentItem {
  id: number
  title: string
  category: string
  summary?: string
  tags?: string[]
  author_name?: string
  view_count?: number
  is_published?: boolean
  created_at?: string
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

export default function DocumentListPage() {
  const [searchParams] = useSearchParams()
  const initialKeyword = searchParams.get('keyword') || ''
  const [keyword, setKeyword] = useState(initialKeyword)
  const [appliedKeyword, setAppliedKeyword] = useState(initialKeyword)
  const [category, setCategory] = useState('all')

  const { data, loading } = useFetch<PageRes<DocumentItem>>(
    () =>
      knowledgeAPI.getDocuments({
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

  return (
    <div>
      <PageHeader
        title="知识文档"
        description="产品、临床、合规与销售知识库"
        breadcrumbs={[{ label: '知识库', path: '/knowledge' }, { label: '知识文档' }]}
        icon={<BookOpen className="w-5 h-5" />}
        actions={<AIActionButton label="AI文档搜索" prompt="搜索关于产品知识的文档" variant="ghost" size="sm" />}
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
              placeholder="搜索文档标题或摘要"
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
        <span className="text-sm text-slate-400">共 {total} 篇</span>
      </div>

      {/* 文档列表 */}
      {loading ? (
        <div className="p-6 text-slate-500">加载中...</div>
      ) : items.length === 0 ? (
        <Empty description="暂无文档" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((doc) => (
            <div
              key={doc.id}
              className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:shadow-md transition-shadow flex flex-col"
            >
              <div className="flex items-start gap-2 mb-2">
                <FileText className="w-4 h-4 text-slate-400 shrink-0 mt-1" />
                <h3 className="font-semibold text-slate-900 dark:text-slate-100 line-clamp-2 flex-1">{doc.title}</h3>
              </div>
              <div className="mb-2">
                <CategoryBadge category={doc.category} />
              </div>
              {doc.summary && (
                <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-2 mb-3 flex-1">{doc.summary}</p>
              )}
              {doc.tags && doc.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {doc.tags.map((tag, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300"
                    >
                      <Tag className="w-3 h-3 mr-0.5" />
                      {tag}
                    </span>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-4 text-xs text-slate-400">
                {doc.author_name && (
                  <span className="inline-flex items-center gap-1">
                    <User className="w-3.5 h-3.5" />
                    {doc.author_name}
                  </span>
                )}
                <span className="inline-flex items-center gap-1">
                  <Eye className="w-3.5 h-3.5" />
                  {doc.view_count ?? 0}
                </span>
                {doc.created_at && <span className="ml-auto">{doc.created_at}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
