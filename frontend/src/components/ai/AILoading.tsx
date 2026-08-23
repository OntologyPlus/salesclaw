import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles } from 'lucide-react'

interface AILoadingProps {
  /** 文案列表（循环切换） */
  messages?: string[]
  className?: string
}

// 默认 AI 化加载文案（让用户感知"AI 在思考"而非"死板加载"）
const DEFAULT_MESSAGES = [
  'AI 正在理解你的需求…',
  'AI 正在检索相关数据…',
  'AI 正在组织答复…',
  'AI 即将生成…',
]

/**
 * AI 化加载组件
 *
 * 替代纯骨架屏：动态切换的 AI 思考文案 + 脉冲动画
 * 让用户感知"AI 在工作"而非"系统在卡"
 */
export default function AILoading({
  messages = DEFAULT_MESSAGES,
  className = '',
}: AILoadingProps) {
  const [idx, setIdx] = useState(0)

  useEffect(() => {
    const t = setInterval(() => {
      setIdx(i => (i + 1) % messages.length)
    }, 1800)
    return () => clearInterval(t)
  }, [messages.length])

  return (
    <div className={`flex flex-col items-center justify-center py-8 ${className}`}>
      {/* 脉冲光晕 */}
      <div className="relative mb-4">
        <motion.div
          className="absolute inset-0 rounded-full bg-gradient-to-br from-brand-400 to-violet-400 blur-xl"
          animate={{ scale: [1, 1.4, 1], opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
        <div className="relative flex items-center justify-center w-12 h-12 rounded-full bg-gradient-to-br from-brand-500 to-violet-500 text-white">
          <Sparkles className="w-5 h-5" />
        </div>
      </div>

      {/* 动态文案 */}
      <AnimatePresence mode="wait">
        <motion.div
          key={idx}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.25 }}
          className="text-sm text-slate-600 dark:text-slate-300"
        >
          {messages[idx]}
        </motion.div>
      </AnimatePresence>

      {/* 三个点 */}
      <div className="flex items-center gap-1 mt-2">
        {[0, 1, 2].map(i => (
          <motion.span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-brand-500"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
          />
        ))}
      </div>
    </div>
  )
}
