import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, FileText, Eye, HelpCircle, Search, TrendingUp } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import StatCard from '@/components/data/StatCard'
import Empty from '@/components/ui/Empty'
import SectionCard from '@/components/layout/SectionCard'
import ListSection from '@/components/layout/ListSection'
import AIInsightBlock from '@/components/ai/AIInsightBlock'
import AIInsightPanel from '@/components/ai/AIInsightPanel'
import useFetch from '@/hooks/useFetch'
import { knowledgeAPI } from '@/services/knowledge'

interface CategoryItem {
  key: string
  count: number
}

interface HotDocument {
  id: number
  title: string
  category: string
  view_count: number
  author_name?: string
}

interface RecentFaq {
  id: number
  question: string
  category: string
  view_count: number
}

interface OverviewData {
  documents_count: number
  faqs_count: number
  total_views: number
  categories: CategoryItem[]
  hot_documents: HotDocument[]
  recent_faqs: RecentFaq[]
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

export default function KnowledgeOverviewPage() {
  const navigate = useNavigate()
  const [searchKeyword, setSearchKeyword] = useState('')
  const { data, loading } = useFetch<OverviewData>(() => knowledgeAPI.getOverview(), [])

  const handleSearch = (e: FormEvent) => {
    e.preventDefault()
    navigate(`/knowledge/documents?keyword=${encodeURIComponent(searchKeyword)}`)
  }

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const categories: CategoryItem[] = data.categories || []
  const maxCount = categories.reduce((m, c) => Math.max(m, c.count || 0), 0) || 1
  const hotDocuments: HotDocument[] = data.hot_documents || []
  const recentFaqs: RecentFaq[] = data.recent_faqs || []

  return (
    <div>
      <PageHeader
        title="知识库"
        description="企业知识、文档与智能检索"
        breadcrumbs={[{ label: '协同与知识' }, { label: '知识总览' }]}
        icon={<BookOpen className="w-5 h-5" />}
      />

      {/* 智能检索 */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="relative max-w-xl">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            placeholder="搜索知识文档..."
            className="w-full pl-12 pr-24 py-3 rounded-2xl border border-slate-200 dark:border-surface-border-subtle-dark bg-white dark:bg-surface-card-dark text-sm text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm"
          />
          <button
            type="submit"
            className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 rounded-xl bg-brand-600 text-white text-sm hover:bg-brand-700 transition-colors"
          >
            检索
          </button>
        </div>
      </form>

      {/* 关键指标卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <StatCard title="知识文档" value={data.documents_count ?? 0} icon={<BookOpen className="w-5 h-5" />} color="brand" />
        <StatCard title="FAQ" value={data.faqs_count ?? 0} icon={<HelpCircle className="w-5 h-5" />} color="violet" />
        <StatCard title="总浏览量" value={data.total_views ?? 0} icon={<Eye className="w-5 h-5" />} color="cyan" />
      </div>

      {/* 快捷入口 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Link to="/knowledge/documents" className="p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-sky-100 text-sky-600 dark:bg-sky-900/20 dark:text-sky-400">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">知识文档</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">产品、临床、合规与销售知识库</p>
        </Link>

        <Link to="/knowledge/faqs" className="p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-100 text-violet-600 dark:bg-violet-900/20 dark:text-violet-400">
              <HelpCircle className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-brand-600">常见问题</h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">高频问题与标准答案</p>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 分类分布 */}
        <SectionCard title="分类分布" icon={<TrendingUp className="w-4 h-4" />}>
          {categories.length > 0 ? (
            <div className="p-5 space-y-3">
              {categories.map((c) => {
                const cfg = CATEGORY_CONFIG[c.key] || CATEGORY_CONFIG.other
                const pct = Math.round(((c.count || 0) / maxCount) * 100)
                return (
                  <div key={c.key}>
                    <div className="flex items-center justify-between mb-1">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
                        {cfg.label}
                      </span>
                      <span className="text-xs text-slate-500 dark:text-slate-400">{c.count} 篇</span>
                    </div>
                    <div className="w-full h-2 bg-slate-100 dark:bg-surface-raised-dark rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="px-5 py-10">
              <Empty description="暂无分类数据" />
            </div>
          )}
        </SectionCard>

        {/* 热门文档 */}
        <SectionCard title="热门文档" icon={<FileText className="w-4 h-4" />} viewAllTo="/knowledge/documents">
          <ListSection<HotDocument>
            items={hotDocuments.slice(0, 5)}
            emptyText="暂无热门文档"
            skeletonRows={5}
            renderRow={(doc) => (
              <div className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{doc.title}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <CategoryBadge category={doc.category} />
                    {doc.author_name && (
                      <span className="text-xs text-slate-500 dark:text-slate-400">{doc.author_name}</span>
                    )}
                  </div>
                </div>
                <span className="inline-flex items-center gap-1 text-xs text-slate-400 shrink-0">
                  <Eye className="w-3.5 h-3.5" />
                  {doc.view_count ?? 0}
                </span>
              </div>
            )}
          />
        </SectionCard>
      </div>

      {/* 最近 FAQ */}
      <SectionCard title="最近 FAQ" icon={<HelpCircle className="w-4 h-4" />} viewAllTo="/knowledge/faqs" className="mt-6">
        <ListSection<RecentFaq>
          items={recentFaqs.slice(0, 5)}
          emptyText="暂无 FAQ"
          skeletonRows={5}
          renderRow={(faq) => (
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{faq.question}</p>
                <div className="mt-1">
                  <CategoryBadge category={faq.category} />
                </div>
              </div>
              <span className="inline-flex items-center gap-1 text-xs text-slate-400 shrink-0">
                <Eye className="w-3.5 h-3.5" />
                {faq.view_count ?? 0}
              </span>
            </div>
          )}
        />
      </SectionCard>

      <div className="mt-6">
        <AIInsightBlock title="AI 知识洞察">
          <AIInsightPanel domain="knowledge" />
        </AIInsightBlock>
      </div>
    </div>
  )
}
