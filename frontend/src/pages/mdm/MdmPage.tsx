import { useState } from 'react'
import { Grid3x3, Search } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import { useFetch } from '@/hooks/useFetch'
import { mdmAPI } from '@/services/mdm'
import AIInsightPanel from '@/components/ai/AIInsightPanel'

// 通用分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 主数据行（统一为带 id 的记录）
interface MdmRow extends Record<string, unknown> {
  id: number | string
}

// Tab 配置
type TabKey = 'hospitals' | 'doctors' | 'products' | 'zones'

interface TabConfig {
  key: TabKey
  label: string
  columns: { key: string; title: string }[]
  hasKeyword: boolean
}

const tabs: TabConfig[] = [
  {
    key: 'hospitals',
    label: '医院',
    hasKeyword: true,
    columns: [
      { key: 'name', title: '名称' },
      { key: 'code', title: '编码' },
      { key: 'level', title: '等级' },
      { key: 'city', title: '城市' },
      { key: 'district', title: '区县' },
    ],
  },
  {
    key: 'doctors',
    label: '医生',
    hasKeyword: true,
    columns: [
      { key: 'name', title: '姓名' },
      { key: 'hospital_name', title: '医院' },
      { key: 'department', title: '科室' },
      { key: 'title', title: '职称' },
      { key: 'phone', title: '电话' },
    ],
  },
  {
    key: 'products',
    label: '产品',
    hasKeyword: true,
    columns: [
      { key: 'name', title: '名称' },
      { key: 'code', title: '编码' },
      { key: 'category', title: '分类' },
      { key: 'specifications', title: '规格' },
      { key: 'manufacturer', title: '厂家' },
    ],
  },
  {
    key: 'zones',
    label: '区域',
    hasKeyword: false,
    columns: [
      { key: 'name', title: '名称' },
      { key: 'code', title: '编码' },
      { key: 'level', title: '层级' },
    ],
  },
]

export default function MdmPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('hospitals')
  const [keyword, setKeyword] = useState('')

  const currentTab = tabs.find((t) => t.key === activeTab)!

  // 根据当前 tab 选择对应的 fetcher
  const fetcher = () => {
    const params = { keyword: keyword || undefined, page: 1, page_size: 20 } as
      { keyword?: string; page: number; page_size: number }
    switch (activeTab) {
      case 'hospitals':
        return mdmAPI.getHospitals(params)
      case 'doctors':
        return mdmAPI.getDoctors(params)
      case 'products':
        return mdmAPI.getProducts(params)
      case 'zones':
        return mdmAPI.getZones({ page: 1, page_size: 20 })
      default:
        return mdmAPI.getHospitals(params)
    }
  }

  const { data, loading } = useFetch<PageRes<MdmRow>>(fetcher, [activeTab, keyword])

  const rows = data?.items ?? []

  return (
    <div>
      <PageHeader
        title="主数据"
        description="医院、医生、产品与区域管理"
        breadcrumbs={[{ label: '主数据' }]}
        icon={<Grid3x3 className="w-5 h-5" />}
        gradient
      />

      <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
        {/* Tab 导航 */}
        <div className="flex items-center border-b border-slate-200 dark:border-slate-700">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => {
                setActiveTab(tab.key)
                setKeyword('')
              }}
              className={`px-5 py-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === tab.key
                  ? 'border-brand-600 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* 搜索框 */}
        {currentTab.hasKeyword && (
          <div className="px-5 py-3 border-b border-slate-200 dark:border-slate-700">
            <div className="relative max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder={`搜索${currentTab.label}...`}
                className="w-full h-10 rounded-xl border border-slate-300 bg-white pl-9 pr-3 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100 dark:placeholder-slate-500"
              />
            </div>
          </div>
        )}

        {/* 数据表格 */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/80">
              <tr>
                {currentTab.columns.map((col) => (
                  <th
                    key={col.key}
                    className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap"
                  >
                    {col.title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={currentTab.columns.length} className="px-4 py-8 text-center text-slate-400">
                    加载中...
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={currentTab.columns.length}>
                    <Empty description={`暂无${currentTab.label}数据`} />
                  </td>
                </tr>
              ) : (
                rows.map((row, idx) => (
                  <tr key={String(row.id ?? idx)} className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
                    {currentTab.columns.map((col) => {
                      const value = row[col.key]
                      // 等级/层级/分类 显示为 Badge
                      const isBadge = col.key === 'level' || col.key === 'category'
                      return (
                        <td key={col.key} className="px-4 py-3 text-slate-700 dark:text-slate-200 whitespace-nowrap">
                          {isBadge && value ? (
                            <Badge variant="info">{String(value)}</Badge>
                          ) : (
                            (value === undefined || value === null || value === '') ? '-' : String(value)
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 总数 */}
        {data?.total !== undefined && (
          <div className="px-5 py-3 border-t border-slate-200 dark:border-slate-700 text-xs text-slate-500 dark:text-slate-400">
            共 {data.total} 条记录
          </div>
        )}
      </div>

      <AIInsightPanel domain="mdm" title="AI 数据治理洞察" className="mt-6" />
    </div>
  )
}
