/**
 * 会话历史侧边栏
 *
 * F14：配合 useChatSessions Hook，展示当前 pageKey 下的历史会话列表。
 * - 点击会话项：调用 onLoad(id) 加载
 * - 删除按钮：调用 onRemove(id)
 * - 新建按钮：调用 onCreateNew()
 *
 * 形态：右侧抽屉（fixed），由父组件控制 open 状态。
 */
import { AnimatePresence, motion } from 'framer-motion'
import { Plus, Trash2, MessageSquare, X, Clock } from 'lucide-react'
import type { ChatSessionMeta } from '@/hooks/useChatSessions'

interface Props {
  open: boolean
  sessions: ChatSessionMeta[]
  currentId: string | null
  onClose: () => void
  onLoad: (id: string) => void
  onRemove: (id: string) => void
  onCreateNew: () => void
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  const now = Date.now()
  const diff = now - ts
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function ChatSessionsSidebar({
  open,
  sessions,
  currentId,
  onClose,
  onLoad,
  onRemove,
  onCreateNew,
}: Props) {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* 遮罩 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-30 bg-black/20"
            onClick={onClose}
          />
          {/* 抽屉 */}
          <motion.aside
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.2, ease: [0.19, 1, 0.22, 1] }}
            className="fixed top-0 right-0 z-40 h-full w-80 bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 flex flex-col"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                历史会话
              </h3>
              <button
                onClick={onClose}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 border-b border-slate-200 dark:border-slate-800">
              <button
                onClick={() => {
                  onCreateNew()
                  onClose()
                }}
                className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-brand-600 text-white text-sm hover:bg-brand-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                新建会话
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {sessions.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center text-slate-400 py-10">
                  <MessageSquare className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-xs">暂无历史会话</p>
                </div>
              ) : (
                sessions.map((s) => (
                  <div
                    key={s.id}
                    className={`group flex items-start gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                      currentId === s.id
                        ? 'bg-brand-50 dark:bg-brand-900/30'
                        : 'hover:bg-slate-100 dark:hover:bg-slate-700'
                    }`}
                    onClick={() => {
                      onLoad(s.id)
                      onClose()
                    }}
                  >
                    <MessageSquare
                      className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                        currentId === s.id ? 'text-brand-600' : 'text-slate-400'
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <p
                        className={`text-xs font-medium truncate ${
                          currentId === s.id
                            ? 'text-brand-700 dark:text-brand-300'
                            : 'text-slate-700 dark:text-slate-200'
                        }`}
                      >
                        {s.title}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400">
                        <span className="flex items-center gap-0.5">
                          <Clock className="w-2.5 h-2.5" />
                          {formatTime(s.updatedAt)}
                        </span>
                        <span>·</span>
                        <span>{s.messageCount} 条</span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onRemove(s.id)
                      }}
                      className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-500 transition-all p-0.5"
                      title="删除"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
