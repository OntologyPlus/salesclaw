import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, X, Loader2 } from 'lucide-react'
import { chatSend } from '@/services/ai'

interface AIValueExplainerProps {
  /** 要解释的值（字符串、数字、或简要描述） */
  value: string | number
  /** 字段名（让 AI 知道上下文） */
  fieldName?: string
  /** 额外上下文（如页面、域） */
  context?: string
  /** 触发方式 */
  trigger?: 'hover' | 'click'
  /** 是否隐藏值本身（仅显示 💡 图标） */
  hideValue?: boolean
}

/**
 * AI 值解释器
 *
 * 形态：值旁 💡 图标，悬停或点击弹 popover 显示 AI 解释
 * 适用：统计卡数值、字段值、KPI 数字、状态标签
 */
const cache = new Map<string, string>()

export default function AIValueExplainer({
  value,
  fieldName,
  context,
  trigger = 'hover',
  hideValue = false,
}: AIValueExplainerProps) {
  const [open, setOpen] = useState(false)
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchExplain = async () => {
    const key = `${fieldName ?? ''}::${value}::${context ?? ''}`
    if (cache.has(key)) {
      setContent(cache.get(key)!)
      return
    }
    setLoading(true)
    try {
      const prompt = `请简洁解释这个值：\n${fieldName ? `字段：${fieldName}\n` : ''}值：${value}\n${context ? `上下文：${context}\n` : ''}\n用 2 句话以内说明它代表什么、为什么是这个值、有什么业务含义。`
      const res = await chatSend(prompt)
      const text = res.response || '（AI 未返回）'
      cache.set(key, text)
      setContent(text)
    } catch (e) {
      setContent(e instanceof Error ? `失败：${e.message}` : '失败')
    } finally {
      setLoading(false)
    }
  }

  const handleOpen = () => {
    setOpen(true)
    if (!content && !loading) fetchExplain()
  }

  return (
    <span className="relative inline-flex items-center">
      {!hideValue && (
        <span
          onMouseEnter={trigger === 'hover' ? handleOpen : undefined}
          onClick={trigger === 'click' ? handleOpen : undefined}
          className="cursor-help"
        >
          {value}
        </span>
      )}
      <button
        type="button"
        onClick={handleOpen}
        onMouseEnter={handleOpen}
        className={`${hideValue ? '' : 'ml-0.5'} p-0.5 rounded text-slate-300 hover:text-brand-500 transition-colors`}
        title="AI 解释此值"
      >
        <Sparkles className="w-3 h-3" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.95 }}
            className="absolute z-50 left-0 top-full mt-1 w-64 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl p-3 text-xs"
          >
            <div className="flex items-center gap-1.5 mb-1.5 pb-1.5 border-b border-slate-100 dark:border-slate-800">
              <Sparkles className="w-3 h-3 text-brand-500" />
              <span className="font-medium text-slate-700 dark:text-slate-200">AI 解释</span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="ml-auto p-0.5 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
            {loading ? (
              <div className="flex items-center gap-1.5 text-slate-400">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>AI 正在分析…</span>
              </div>
            ) : (
              <div className="text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
                {content}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  )
}
