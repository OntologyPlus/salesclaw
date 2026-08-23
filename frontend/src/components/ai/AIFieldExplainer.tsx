import { useState, useRef, useEffect } from 'react'
import { Lightbulb, X, Loader2 } from 'lucide-react'
import { chatSend } from '@/services/ai'

interface AIFieldExplainerProps {
  fieldName: string
  hint?: string
}

/**
 * 表单字段 AI 解释器
 *
 * 形态：label 旁 💡 图标，悬停弹 popover 显示字段含义 + 填写建议
 * 1h 缓存（同一字段不重复调 LLM）
 */
const cache = new Map<string, string>()

export default function AIFieldExplainer({ fieldName, hint }: AIFieldExplainerProps) {
  const [open, setOpen] = useState(false)
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const closeTimerRef = useRef<number | null>(null)

  const fetchExplain = async () => {
    const key = `${fieldName}::${hint ?? ''}`
    if (cache.has(key)) {
      setContent(cache.get(key)!)
      return
    }
    setLoading(true)
    try {
      const prompt = `请简洁解释这个表单字段的含义、填写规则和最佳实践：\n字段名："${fieldName}"${hint ? `\n提示信息："${hint}"` : ''}\n\n要求：3 句话以内，使用 Markdown 列表。`
      const res = await chatSend(prompt)
      const text = res.response || '（AI 未返回内容）'
      cache.set(key, text)
      setContent(text)
    } catch (e) {
      setContent(e instanceof Error ? `请求失败：${e.message}` : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  // 悬停延迟触发
  const handleEnter = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
    setOpen(true)
    if (!content && !loading) fetchExplain()
  }
  const handleLeave = () => {
    closeTimerRef.current = window.setTimeout(() => setOpen(false), 150)
  }

  useEffect(() => () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
  }, [])

  return (
    <div className="relative inline-block" onMouseEnter={handleEnter} onMouseLeave={handleLeave}>
      <button
        type="button"
        className="p-0.5 rounded text-slate-300 hover:text-brand-500 transition-colors"
        title="AI 解释"
        aria-label="AI 解释此字段"
      >
        <Lightbulb className="w-3.5 h-3.5" />
      </button>
      {open && (
        <div
          className="absolute z-50 left-0 top-full mt-1 w-72 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl p-3 text-xs text-slate-700 dark:text-slate-200"
        >
          <div className="flex items-center gap-1.5 mb-1.5 pb-1.5 border-b border-slate-100 dark:border-slate-800">
            <Lightbulb className="w-3 h-3 text-brand-500" />
            <span className="font-medium">AI 字段解释</span>
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
              <span>AI 正在分析字段…</span>
            </div>
          ) : (
            <div className="whitespace-pre-wrap leading-relaxed">{content}</div>
          )}
        </div>
      )}
    </div>
  )
}
