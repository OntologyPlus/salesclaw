import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react'
import { useToastStore } from '@/hooks/useToast'

const iconMap = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: AlertCircle,
}

const colorMap = {
  info: 'text-sky-500',
  success: 'text-emerald-500',
  warning: 'text-amber-500',
  error: 'text-rose-500',
}

// 全局 Toast 容器，从 useToast 读取队列
export default function Toast() {
  const items = useToastStore((s) => s.items)
  const remove = useToastStore((s) => s.remove)

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 w-80 pointer-events-none">
      <AnimatePresence>
        {items.map((item) => {
          const Icon = iconMap[item.type]
          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: 32, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 32, scale: 0.95 }}
              transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
              className="flex items-start gap-2.5 p-3 rounded-xl bg-white dark:bg-slate-800 shadow-lg border border-slate-200 dark:border-slate-700 pointer-events-auto"
            >
              <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${colorMap[item.type]}`} />
              <p className="flex-1 text-sm text-slate-700 dark:text-slate-200 break-words">{item.message}</p>
              <button
                onClick={() => remove(item.id)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
