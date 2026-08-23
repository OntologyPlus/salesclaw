import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Wand2, X, Loader2, Check } from 'lucide-react'
import { chatSend } from '@/services/ai'
import { useToast } from '@/hooks/useToast'

interface AIFormFillerProps {
  /** 表单 schema 描述（让 AI 知道要填什么字段） */
  formSchema: string
  /** 上下文：当前用户/页面/业务对象 */
  context?: string
  /** 填入回调：AI 返回结构化数据 */
  onFill: (data: Record<string, string>) => void
  /** 按钮文字 */
  label?: string
}

/**
 * 表单 AI 智能预填
 *
 * 形态：表单顶部"AI 帮我填"按钮
 * - 点击 → AI 根据 schema + 上下文生成推荐值
 * - 用户确认 → 调 onFill 注入到表单
 * - 不破坏现有 onChange 模式（由业务页处理 onFill）
 */
export default function AIFormFiller({
  formSchema,
  context,
  onFill,
  label = 'AI 帮我填',
}: AIFormFillerProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [suggestion, setSuggestion] = useState<Record<string, string> | null>(null)
  const [reasoning, setReasoning] = useState<string>('')
  const toast = useToast()

  const handleGenerate = async () => {
    setOpen(true)
    setLoading(true)
    setSuggestion(null)
    try {
      const prompt = `你是一个销售/培训系统助手。基于以下信息，为表单生成推荐填入值。

【表单字段】
${formSchema}

【上下文】
${context || '无'}

要求：
1. 输出严格 JSON 格式：{ "字段名": "推荐值", "字段名": "推荐值" }
2. 推荐值要合理、可执行（如日期用 ISO 格式、数字合理范围）
3. 不要解释，只输出 JSON

示例输出：
{ "doctor_name": "张主任", "visit_date": "2026-01-20", "priority": "高" }`
      const res = await chatSend(prompt)
      const text = res.response
      // 尝试从响应中提取 JSON
      const jsonMatch = text.match(/\{[\s\S]*\}/)
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0])
        setSuggestion(parsed)
        // 提取 reasoning（JSON 之外的部分）
        setReasoning(text.replace(jsonMatch[0], '').trim() || '基于您的画像和当前场景生成')
      } else {
        toast('AI 未能生成结构化建议', 'error')
        setReasoning(text)
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'AI 失败'
      toast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = () => {
    if (suggestion) {
      onFill(suggestion)
      toast('已填入推荐值', 'success')
      setOpen(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={handleGenerate}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-brand-500 to-violet-500 hover:from-brand-600 hover:to-violet-600 text-white text-xs font-medium shadow-sm hover:shadow transition-all"
      >
        <Wand2 className="w-3.5 h-3.5" />
        {label}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/30 z-[70]"
              onClick={() => setOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.97 }}
              className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[80] w-[28rem] max-w-[calc(100vw-2rem)] max-h-[80vh] rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col"
            >
              <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20">
                <Wand2 className="w-4 h-4 text-brand-500" />
                <span className="flex-1 text-sm font-medium text-slate-800 dark:text-slate-100">
                  AI 智能预填
                </span>
                <button onClick={() => setOpen(false)} className="p-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700">
                  <X className="w-4 h-4 text-slate-500" />
                </button>
              </div>

              <div className="flex-1 overflow-auto p-4">
                {loading ? (
                  <div className="flex items-center gap-2 text-sm text-slate-400 py-8 justify-center">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>AI 正在为表单生成推荐值…</span>
                  </div>
                ) : suggestion ? (
                  <>
                    <div className="mb-3 p-2 rounded-lg bg-slate-50 dark:bg-slate-900/40 text-xs text-slate-500">
                      {reasoning}
                    </div>
                    <div className="space-y-2">
                      {Object.entries(suggestion).map(([key, value]) => (
                        <div key={key} className="flex items-start gap-2 px-3 py-2 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                          <span className="shrink-0 text-xs text-slate-500 dark:text-slate-400 w-24 truncate font-mono" title={key}>
                            {key}
                          </span>
                          <span className="text-xs text-slate-700 dark:text-slate-200 break-all">
                            {String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-slate-500 py-8 text-center">暂无推荐</p>
                )}
              </div>

              {suggestion && !loading && (
                <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-800 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleGenerate}
                    className="px-3 py-1.5 rounded-lg text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
                  >
                    重新生成
                  </button>
                  <div className="flex-1" />
                  <button
                    type="button"
                    onClick={handleApply}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-xs font-medium"
                  >
                    <Check className="w-3.5 h-3.5" />
                    采纳填入
                  </button>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
