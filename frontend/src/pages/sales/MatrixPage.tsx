import { useState } from 'react'
import { motion } from 'framer-motion'
import { Grid3x3, Sparkles, AlertCircle, Eye } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Select from '@/components/ui/Select'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import { salesAPI } from '@/services/sales'

// 矩阵单元格
interface MatrixCell {
  hospital_id?: number
  product_id?: number
  hospital_name?: string
  product_name?: string
  coverage_level?: string
  visit_count?: number
}

// 矩阵数据
interface MatrixData {
  hospitals?: { id: number; name: string }[]
  products?: { id: number; name: string }[]
  cells?: MatrixCell[]
}

// 主数据选项
interface Option { id: number; name: string }

// 覆盖度映射
const coverageMap: Record<string, { label: string; variant: 'success' | 'info' | 'warning' | 'default'; dot: string }> = {
  high: { label: '高', variant: 'success', dot: 'bg-emerald-500' },
  medium: { label: '中', variant: 'info', dot: 'bg-sky-400' },
  low: { label: '低', variant: 'warning', dot: 'bg-amber-400' },
  none: { label: '无', variant: 'default', dot: 'bg-slate-300' },
}

// AI 洞察 Mock 文本
const aiInsights = [
  '识别到 2 个空白点：市第一人民医院的脑复康、市第二医院的心血通尚未覆盖，建议优先安排拜访。',
  '市第三人民医院的胃复安覆盖度较低（仅 2 次拜访），建议提升至中高覆盖。',
  '本月矩阵覆盖率较上月提升 8%，持续保持当前拜访节奏。',
]

export default function MatrixPage() {
  const [productId, setProductId] = useState<string>('')
  const [cellModal, setCellModal] = useState<MatrixCell | null>(null)

  // 矩阵数据
  const { data: matrix, loading, error } = useFetch<MatrixData>(
    () => salesAPI.getMatrix({ product_id: productId ? Number(productId) : undefined }),
    [productId]
  )
  // 产品列表
  const { data: products } = useFetch<Option[]>(() => salesAPI.listProducts(), [])

  const hospitals = matrix?.hospitals ?? []
  const productList = matrix?.products ?? []
  const cells = matrix?.cells ?? []

  // 构建单元格查找表 key=`${hospitalId}_${productId}`
  const cellMap = new Map<string, MatrixCell>()
  cells.forEach((c) => {
    const key = `${c.hospital_id}_${c.product_id}`
    cellMap.set(key, c)
  })

  const productOptions = [
    { label: '全部产品', value: '' },
    ...(products ?? []).map(p => ({ label: p.name, value: String(p.id) })),
  ]

  return (
    <div>
      <PageHeader
        title="矩阵看板"
        description="多维矩阵分析与可视化看板"
        breadcrumbs={[{ label: '销售执行' }, { label: '矩阵看板' }]}
        icon={<Grid3x3 className="w-5 h-5" />}
        actions={
          <Select
            options={productOptions}
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="w-40"
          />
        }
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      {/* 矩阵表格 */}
      <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden mb-6">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-5"><Skeleton lines={5} /></div>
          ) : hospitals.length === 0 || productList.length === 0 ? (
            <Empty description="暂无矩阵数据" />
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/80">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap sticky left-0 bg-slate-50 dark:bg-slate-800">
                    医院 \ 产品
                  </th>
                  {productList.map((p) => (
                    <th key={p.id} className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">
                      {p.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {hospitals.map((h, hi) => (
                  <motion.tr
                    key={h.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: hi * 0.03 }}
                    className="hover:bg-slate-50 dark:hover:bg-slate-700/40"
                  >
                    <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100 whitespace-nowrap sticky left-0 bg-white dark:bg-slate-800">
                      {h.name}
                    </td>
                    {productList.map((p) => {
                      const cell = cellMap.get(`${h.id}_${p.id}`)
                      const level = cell?.coverage_level ?? 'none'
                      const cv = coverageMap[level] ?? coverageMap.none
                      return (
                        <td key={p.id} className="px-4 py-3">
                          <button
                            onClick={() => cell && setCellModal(cell)}
                            disabled={!cell}
                            className="inline-flex items-center gap-2 px-2 py-1 rounded-lg transition-colors hover:bg-slate-100 dark:hover:bg-slate-700 disabled:cursor-default"
                          >
                            <span className={`w-2 h-2 rounded-full ${cv.dot}`} />
                            <Badge variant={cv.variant}>{cv.label}</Badge>
                            {typeof cell?.visit_count === 'number' && (
                              <span className="text-xs text-slate-500">{cell.visit_count} 次</span>
                            )}
                          </button>
                        </td>
                      )
                    })}
                  </motion.tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* AI 洞察卡片 */}
      <div className="rounded-2xl bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20 border border-brand-200 dark:border-brand-800 p-5">
        <div className="flex items-center gap-2 mb-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-brand-100 text-brand-600 dark:bg-brand-900/40 dark:text-brand-300">
            <Sparkles className="w-4 h-4" />
          </div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">AI 洞察</h2>
        </div>
        <div className="space-y-2">
          {aiInsights.map((text, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200"
            >
              <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
              <span>{text}</span>
            </motion.div>
          ))}
        </div>
      </div>

      {/* 单元格详情 Modal */}
      {cellModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={() => setCellModal(null)} />
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="relative w-full max-w-md rounded-2xl bg-white dark:bg-slate-800 shadow-2xl"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
              <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">覆盖详情</h3>
              <button onClick={() => setCellModal(null)} className="p-1 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700">
                <Eye className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">医院</span>
                <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{cellModal.hospital_name ?? '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">产品</span>
                <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{cellModal.product_name ?? '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">覆盖度</span>
                {(() => {
                  const cv = coverageMap[cellModal.coverage_level ?? 'none'] ?? coverageMap.none
                  return <Badge variant={cv.variant}>{cv.label}</Badge>
                })()}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">拜访次数</span>
                <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{cellModal.visit_count ?? 0} 次</span>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-slate-200 dark:border-slate-700">
              <Button variant="secondary" onClick={() => setCellModal(null)}>关闭</Button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
