import {
  Wrench, FileText, Presentation, Image, Video, PenTool, BarChart3, Mail,
  type LucideIcon,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Empty from '@/components/ui/Empty'
import Badge from '@/components/ui/Badge'
import { useFetch } from '@/hooks/useFetch'
import { toolsAPI } from '@/services/tools'

// 工具项
interface ToolItem {
  id: number | string
  name: string
  description: string
  category: string
  icon: string
}

// 总览数据
interface ToolsOverview {
  tools: ToolItem[]
  total: number
}

// 图标字符串到 lucide 组件的映射
const iconMap: Record<string, LucideIcon> = {
  FileText,
  Presentation,
  Image,
  Video,
  PenTool,
  BarChart3,
  Mail,
  Wrench,
}

function getIcon(name?: string): LucideIcon {
  if (!name) return Wrench
  return iconMap[name] ?? Wrench
}

// 分类颜色映射
const categoryColorMap: Record<string, 'default' | 'info' | 'success' | 'warning'> = {
  content: 'info',
  design: 'warning',
  analytics: 'success',
  marketing: 'default',
}

export default function ToolsPage() {
  const { data, loading } = useFetch<ToolsOverview>(() => toolsAPI.getOverview(), [])

  if (loading) return <div className="p-6 text-slate-500">加载中...</div>
  if (!data) return <Empty description="暂无数据" />

  const tools = data.tools ?? []

  return (
    <div>
      <PageHeader
        title="内容工具"
        description="营销内容生成与效率工具"
        breadcrumbs={[{ label: '内容工具' }]}
        icon={<Wrench className="w-5 h-5" />}
        gradient
      />

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">工具列表</h2>
        <span className="text-xs text-slate-500 dark:text-slate-400">共 {data.total ?? tools.length} 个工具</span>
      </div>

      {tools.length === 0 ? (
        <Empty description="暂无可用工具" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tools.map((tool) => {
            const Icon = getIcon(tool.icon)
            const variant = categoryColorMap[tool.category] ?? 'default'
            return (
              <div
                key={tool.id}
                className="p-5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 transition-shadow hover:shadow-md cursor-pointer"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-brand-100 text-brand-600 dark:bg-brand-900/40 dark:text-brand-300">
                    <Icon className="w-5 h-5" />
                  </div>
                  <Badge variant={variant}>{tool.category || '通用'}</Badge>
                </div>
                <h3 className="mt-3 text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {tool.name || '-'}
                </h3>
                <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                  {tool.description || '暂无描述'}
                </p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
