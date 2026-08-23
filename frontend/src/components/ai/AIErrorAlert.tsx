import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertCircle, X, Sparkles, Loader2 } from 'lucide-react'
import { chatSend } from '@/services/ai'

interface AIErrorAlertProps {
  /** 错误信息 */
  error: string
  /** 错误上下文（如：哪个接口、哪个操作） */
  context?: string
  /** 关闭回调（可选） */
  onClose?: () => void
  className?: string
}

/**
 * AI 化错误提示
 *
 * 替代基础 alert：显示错误 + "AI 解释"按钮
 * 点击 AI 解释 → 弹底部小卡片，给出可能原因 + 解决建议
 */
export default function AIErrorAlert({
  error,
  context,
  onClose,
  className = '',
}: AIErrorAlertProps) {
  const [cardOpen, setCardOpen] = useState(false)
  const [explanation, setExplanation] = useState('')
  const [loading, setLoading] = useState(false)

  const askAI = async () => {
    setCardOpen(true)
    setLoading(true)
    setExplanation('')
    try {
      const prompt = `请帮我分析这个系统错误，给出可能原因和解决建议：\n错误：${error}\n${context ? `场景：${context}\n` : ''}\n要求：列出 3 个最可能的原因和对应的解决方法，简洁可操作。`
      const res = await chatSend(prompt)
      setExplanation(res.response)
    } catch (e) {
      setExplanation(e instanceof Error ? `AI 解释失败：${e.message}` : 'AI 解释失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className={`flex items-start gap-2 px-3 py-2.5 rounded-lg border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-900/20 ${className}`}>
        <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-rose-700 dark:text-rose-300 break-words">{error}</p>
          <button
            type="button"
            onClick={askAI}
            className="mt-1 inline-flex items-center gap-1 text-xs text-brand-600 dark:text-brand-400 hover:underline"
          >
            <Sparkles className="w-3 h-3" />
            让 AI 解释这个错误
          </button>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-0.5 rounded text-rose-400 hover:text-rose-600 hover:bg-rose-100 dark:hover:bg-rose-900/40"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

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
              className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[80] w-[30rem] max-w-[calc(100vw-2rem)] max-h-[80vh] rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col"
            >
              <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-800">
                <Sparkles className="w-4 h-4 text-brand-500" />
                <span className="flex-1 text-sm font-medium text-slate-800 dark:text-slate-100">AI 错误诊断</span>
                <button onClick={() => setCardOpen(false)} className="p-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700">
                  <X className="w-4 h-4 text-slate-500" />
                </button>
              </div>
              <div className="flex-1 overflow-auto p-4 text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
                {loading ? (
                  <div className="flex items-center gap-2 text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>AI 正在诊断…</span>
                  </div>
                ) : (
                  explanation
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
