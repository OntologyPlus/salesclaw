import type { ReactNode } from 'react'
import { ChevronLeft, ChevronRight, Sparkles, Loader2 } from 'lucide-react'
import Skeleton from '@/components/ui/Skeleton'
import AIEmpty from '@/components/ai/AIEmpty'
import { useState, useCallback } from 'react'
import { chatSend } from '@/services/ai'
import { useToast } from '@/hooks/useToast'

export interface Column<T> {
  key: string
  title: string
  render?: (row: T, index: number) => ReactNode
  width?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  loading?: boolean
  total?: number
  page?: number
  pageSize?: number
  onPageChange?: (page: number) => void
  toolbar?: ReactNode
  rowKey?: string | ((row: T) => string)
  /** 空态资源名（用于 AIEmpty 上下文） */
  emptyResource?: string
  /** 空态 AI 上下文（页面路径、域等） */
  emptyContext?: string
  /** 行级 AI 解读：传入行摘要生成函数 */
  aiExplainable?: (row: T) => string
  /** 自定义空态描述 */
  emptyDescription?: string
}

// 通用数据表格，支持分页、loading、空状态
export default function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  loading = false,
  total = 0,
  page = 1,
  pageSize = 20,
  onPageChange,
  toolbar,
  rowKey = 'id',
  emptyResource = '数据',
  emptyContext,
  aiExplainable,
  emptyDescription,
}: DataTableProps<T>) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const getRowKey = (row: T, index: number): string => {
    if (typeof rowKey === 'function') return rowKey(row)
    return String(row[rowKey] ?? index)
  }

  // 行级 AI 解读（轻量版：弹底部 mini 卡片）
  const [explainCard, setExplainCard] = useState<{ title: string; content: string; loading: boolean } | null>(null)
  const toast = useToast()
  const handleExplain = useCallback(async (row: T) => {
    if (!aiExplainable) return
    const summary = aiExplainable(row)
    setExplainCard({ title: 'AI 行解读', content: '', loading: true })
    try {
      const res = await chatSend(`请分析这一行数据，给出业务解读和潜在建议：\n\n${summary}`)
      setExplainCard({ title: 'AI 行解读', content: res.response, loading: false })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'AI 解读失败'
      toast(msg, 'error')
      setExplainCard(null)
    }
  }, [aiExplainable, toast])

  return (
    <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
      {toolbar && (
        <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-slate-200 dark:border-surface-border-subtle-dark">
          {toolbar}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-900/80 sticky top-0">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap"
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.title}
                </th>
              ))}
              {aiExplainable && (
                <th className="px-2 py-3 w-10" title="AI 行级解读">
                  <Sparkles className="w-3.5 h-3.5 text-brand-500 mx-auto" />
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {loading ? (
              <>
                {Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: columns.length + (aiExplainable ? 1 : 0) }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <Skeleton lines={1} />
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <td colSpan={columns.length + (aiExplainable ? 1 : 0)} className="px-4 py-2 text-center">
                    <div className="flex items-center justify-center gap-1.5 text-xs text-slate-400">
                      <Loader2 className="w-3 h-3 animate-spin text-brand-500" />
                      <span>AI 正在预分析本页数据…</span>
                    </div>
                  </td>
                </tr>
              </>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length + (aiExplainable ? 1 : 0)}>
                  <AIEmpty
                    resource={emptyResource}
                    description={emptyDescription}
                    context={emptyContext}
                  />
                </td>
              </tr>
            ) : (
              data.map((row, index) => (
                <tr key={getRowKey(row, index)} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-700/40">
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3 text-slate-700 dark:text-slate-200 whitespace-nowrap">
                      {col.render ? col.render(row, index) : String(row[col.key] ?? '')}
                    </td>
                  ))}
                  {aiExplainable && (
                    <td className="px-2 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleExplain(row)}
                        title="AI 解读此行"
                        className="p-1 rounded-md text-slate-400 hover:text-brand-500 hover:bg-brand-50 dark:hover:bg-brand-900/30 transition-colors"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {onPageChange && total > 0 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-800 text-sm">
          <span className="text-slate-500 dark:text-slate-400">
            共 {total} 条
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 text-slate-600 dark:text-slate-300">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => onPageChange(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* 行级 AI 解读弹窗（底部居中 mini 卡片） */}
      {explainCard && (
        <>
          <div className="fixed inset-0 bg-black/20 z-[55]" onClick={() => setExplainCard(null)} />
          <div className="fixed left-1/2 -translate-x-1/2 bottom-12 z-[65] w-96 max-w-[calc(100vw-2rem)] rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-200 dark:border-slate-800 bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20">
              <Sparkles className="w-3.5 h-3.5 text-brand-500" />
              <span className="flex-1 text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{explainCard.title}</span>
              <button onClick={() => setExplainCard(null)} className="text-xs text-slate-400 hover:text-slate-600">关闭</button>
            </div>
            <div className="p-3 max-h-64 overflow-y-auto text-xs text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
              {explainCard.loading ? (
                <div className="flex items-center gap-1.5 text-slate-400">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>AI 正在分析此行…</span>
                </div>
              ) : (
                explainCard.content
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
