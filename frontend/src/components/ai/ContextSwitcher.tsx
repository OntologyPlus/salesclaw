import { useEffect, useState } from 'react'
import { Building2, Calendar, Layers, RotateCcw, ChevronDown } from 'lucide-react'
import { useContextStore } from '@/stores/context'
import useToast from '@/hooks/useToast'

type ScopeType = 'post' | 'zone' | 'region' | 'area'
type PeriodType = 'day' | 'week' | 'month' | 'quarter' | 'year'
type Perspective = 'management' | 'customer_development' | 'report'

const SCOPE_OPTIONS: { value: ScopeType; label: string; desc: string }[] = [
  { value: 'post', label: '我的岗位', desc: '仅查看个人数据' },
  { value: 'zone', label: '辖区', desc: '查看所辖辖区汇总' },
  { value: 'region', label: '大区', desc: '查看大区汇总' },
  { value: 'area', label: '事业部', desc: '查看事业部全局' },
]

const PERIOD_OPTIONS: { value: PeriodType; label: string }[] = [
  { value: 'day', label: '日' },
  { value: 'week', label: '周' },
  { value: 'month', label: '月' },
  { value: 'quarter', label: '季度' },
  { value: 'year', label: '年' },
]

const PERSPECTIVE_OPTIONS: { value: Perspective; label: string; icon: string }[] = [
  { value: 'management', label: '管理视角', icon: '📊' },
  { value: 'customer_development', label: '客户开发', icon: '🎯' },
  { value: 'report', label: '报表视角', icon: '📋' },
]

interface Props {
  compact?: boolean
  className?: string
  onChange?: () => void
}

/**
 * 全局上下文切换器：空间 / 时间 / 视角 三维联动
 * - 空间：岗位 / 辖区 / 大区 / 事业部
 * - 时间：日 / 周 / 月 / 季度 / 年 + 历史周期游标（period_end）
 * - 视角：管理 / 客户开发 / 报表
 */
export default function ContextSwitcher({ compact = false, className = '', onChange }: Props) {
  const toast = useToast()
  const ctx = useContextStore()
  const [showPeriodPicker, setShowPeriodPicker] = useState(false)

  useEffect(() => {
    if (!ctx.loaded) ctx.load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleScopeChange = async (scope: ScopeType) => {
    await ctx.setScope(scope, null, SCOPE_OPTIONS.find((o) => o.value === scope)?.label ?? '')
    toast(`已切换至：${SCOPE_OPTIONS.find((o) => o.value === scope)?.label}`, 'info')
    onChange?.()
  }

  const handlePeriodTypeChange = async (period_type: PeriodType) => {
    await ctx.setPeriod(period_type, ctx.period_end)
    onChange?.()
  }

  const handlePeriodEndChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value || null
    await ctx.setPeriod(ctx.period_type, value)
    onChange?.()
  }

  const handlePerspectiveChange = async (perspective: Perspective) => {
    await ctx.setPerspective(perspective)
    onChange?.()
  }

  const handleReset = async () => {
    await ctx.reset()
    toast('已重置为默认上下文', 'info')
    onChange?.()
  }

  const today = new Date().toISOString().slice(0, 10)

  return (
    <div className={`rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 ${compact ? 'p-3' : 'p-4'} ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-brand-500" />
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">全局上下文</span>
        </div>
        <button
          onClick={handleReset}
          className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-brand-600 transition-colors"
          title="重置上下文"
        >
          <RotateCcw className="w-3 h-3" />
          {!compact && '重置'}
        </button>
      </div>

      <div className={`grid ${compact ? 'grid-cols-1 gap-2' : 'grid-cols-1 md:grid-cols-3 gap-3'}`}>
        {/* 空间维度 */}
        <div>
          <div className="flex items-center gap-1 mb-1.5 text-xs text-slate-500 dark:text-slate-400">
            <Building2 className="w-3 h-3" />
            空间
          </div>
          <div className="flex flex-wrap gap-1">
            {SCOPE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handleScopeChange(opt.value)}
                title={opt.desc}
                className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                  ctx.scope_type === opt.value
                    ? 'bg-brand-500 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* 时间维度 */}
        <div>
          <div className="flex items-center gap-1 mb-1.5 text-xs text-slate-500 dark:text-slate-400">
            <Calendar className="w-3 h-3" />
            时间
          </div>
          <div className="flex flex-wrap gap-1">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handlePeriodTypeChange(opt.value)}
                className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                  ctx.period_type === opt.value
                    ? 'bg-brand-500 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {/* 历史周期游标 */}
          <div className="mt-1.5 relative">
            <button
              onClick={() => setShowPeriodPicker((v) => !v)}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs text-slate-500 hover:text-brand-600 border border-slate-200 dark:border-slate-800 dark:text-slate-400"
              title="历史周期游标（留空=当前周期）"
            >
              <ChevronDown className="w-3 h-3" />
              {ctx.period_end ? `截至 ${ctx.period_end}` : '当前周期'}
            </button>
            {showPeriodPicker && (
              <div className="absolute z-50 mt-1 p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-lg">
                <label className="block text-xs text-slate-500 mb-1">历史周期截止日</label>
                <input
                  type="date"
                  value={ctx.period_end ?? ''}
                  max={today}
                  onChange={handlePeriodEndChange}
                  className="block w-44 px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
                />
                {ctx.period_end && (
                  <button
                    onClick={() => handlePeriodEndChange({ target: { value: '' } } as any)}
                    className="mt-1 text-xs text-brand-600 hover:underline"
                  >
                    回到当前周期
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* 视角维度 */}
        <div>
          <div className="flex items-center gap-1 mb-1.5 text-xs text-slate-500 dark:text-slate-400">
            <Layers className="w-3 h-3" />
            视角
          </div>
          <div className="flex flex-wrap gap-1">
            {PERSPECTIVE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handlePerspectiveChange(opt.value)}
                className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                  ctx.perspective === opt.value
                    ? 'bg-violet-500 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                }`}
              >
                <span className="mr-0.5">{opt.icon}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
