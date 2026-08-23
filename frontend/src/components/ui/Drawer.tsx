import type { ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'

type Side = 'right' | 'left'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title?: string
  side?: Side
  children: ReactNode
  width?: string
}

// 抽屉组件，支持左右侧滑出
export default function Drawer({ open, onClose, title, side = 'right', children, width = 'w-96' }: DrawerProps) {
  const xHidden = side === 'right' ? '100%' : '-100%'
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: xHidden }}
            animate={{ x: 0 }}
            exit={{ x: xHidden }}
            transition={{ duration: 0.25, ease: [0.19, 1, 0.22, 1] }}
            className={`absolute top-0 ${side === 'right' ? 'right-0' : 'left-0'} bottom-0 ${width} bg-white dark:bg-slate-800 shadow-2xl flex flex-col`}
          >
            {title && (
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700 shrink-0">
                <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
                <button
                  onClick={onClose}
                  className="p-1 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            )}
            <div className="flex-1 overflow-auto">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
