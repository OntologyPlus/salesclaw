import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, Inbox, X, Loader2, Lightbulb, Wand2 } from 'lucide-react'
import { chatSend } from '@/services/ai'
import { useToast } from '@/hooks/useToast'

interface AIEmptyProps {
  /** 资源名（用于 prompt 上下文） */
  resource?: string
  /** 描述文本 */
  description?: string
  /** 自定义图标 */
  icon?: React.ReactNode
  /** 场景上下文（让 AI 给出更精准建议） */
  context?: string
  /** 自定义问题模板 */
  questionTemplate?: string
  className?: string
}

/**
 * AI 化空态组件
 *
 * 替代普通 Empty 组件，让空态也具备 AI 出口。
 * - 没数据时：主图标 + 描述 + 3 个 AI 引导问题 chip
 * - 点 chip 或"问 AI"按钮 → 弹底部 mini 卡片显示回答
 */
export default function AIEmpty({
  resource = '数据',
  description,
  icon,
  context,
  questionTemplate,
  className = '',
}: AIEmptyProps) {
  const [cardOpen, setCardOpen] = useState(false)
  const [cardTitle, setCardTitle] = useState('')
  const [cardContent, setCardContent] = useState('')
  const [loading, setLoading] = useState(false)
  const toast = useToast()

  // 智能生成引导问题（基于 resource 推断）
  const defaultQuestions = [
    `我现在还没有${resource}，应该怎么开始？`,
    `能给我推荐创建${resource}的最佳实践吗？`,
    `基于我的画像，建议我先创建哪些${resource}？`,
  ]
  const questions = questionTemplate ? [questionTemplate] : defaultQuestions

  const askAI = async (q: string) => {
    setCardTitle(q.length > 30 ? q.slice(0, 30) + '…' : q)
    setCardOpen(true)
    setCardContent('')
    setLoading(true)
    try {
      const fullPrompt = context
        ? `${q}\n\n【上下文】${context}\n【当前页面】${location.pathname}`
        : `${q}\n\n【当前页面】${location.pathname}`
      const res = await chatSend(fullPrompt)
      setCardContent(res.response || '（AI 暂无回答）')
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'AI 请求失败'
      setCardContent(`请求失败：${msg}`)
      toast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className={`flex flex-col items-center justify-center py-16 px-4 text-center ${className}`}>
        {/* 图标 + 渐变光环 */}
        <div className="relative mb-4">
          <div className="absolute inset-0 rounded-full bg-gradient-to-br from-brand-400/20 to-violet-400/20 blur-xl" />
          <div className="relative flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-50 to-violet-50 dark:from-brand-900/30 dark:to-violet-900/30 text-brand-500">
            {icon || <Inbox className="w-8 h-8" />}
          </div>
        </div>

        <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
          {description || `暂无${resource}`}
        </p>
        <p className="text-xs text-slate-400 dark:text-slate-500 mb-4 max-w-md">
          {`别担心，让 AI 帮你迈出第一步`}
        </p>

        {/* 引导问题 chip */}
        <div className="flex flex-wrap items-center justify-center gap-2 max-w-2xl">
          {questions.map((q, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => askAI(q)}
              className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-brand-300 hover:shadow-sm text-xs text-slate-700 dark:text-slate-200 transition-all"
            >
              <Wand2 className="w-3 h-3 text-brand-500 group-hover:rotate-12 transition-transform" />
              <span className="line-clamp-1">{q.replace(/^我.*?[？?]/, '').trim() || q}</span>
            </button>
          ))}
        </div>
      </div>

      {/* AI 回答弹窗（底部居中） */}
      <AnimatePresence>
        {cardOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/30 z-[70]"
              onClick={() => setCardOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.97 }}
              className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[80] w-[32rem] max-w-[calc(100vw-2rem)] max-h-[80vh] rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col"
            >
              <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-800">
                <Sparkles className="w-4 h-4 text-brand-500" />
                <span className="flex-1 text-sm font-medium text-slate-800 dark:text-slate-100 truncate">
                  {cardTitle}
                </span>
                <button onClick={() => setCardOpen(false)} className="p-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700">
                  <X className="w-4 h-4 text-slate-500" />
                </button>
              </div>
              <div className="flex-1 overflow-auto p-4 text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
                {loading ? (
                  <div className="flex items-center gap-2 text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>AI 正在思考…</span>
                  </div>
                ) : (
                  cardContent
                )}
              </div>
              {!loading && cardContent && (
                <div className="px-4 py-2 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 text-xs text-slate-500 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Lightbulb className="w-3 h-3" />
                    基于你的画像和当前页面生成
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard?.writeText(cardContent)
                      toast('已复制', 'success')
                    }}
                    className="text-brand-600 hover:underline"
                  >
                    复制
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
