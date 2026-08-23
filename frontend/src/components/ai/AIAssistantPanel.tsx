import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import {
  Bot, X, Send, Pin, PinOff, Plus, Sparkles, Loader2, AlertCircle, User as UserIcon,
} from 'lucide-react'
import useAIAssistantStore from '@/stores/aiAssistant'
import { useAI } from '@/hooks/useAI'
import Badge from '@/components/ui/Badge'
import Select from '@/components/ui/Select'
import type { SelectOption } from '@/components/ui/Select'

// Agent 选项
const agentOptions: SelectOption[] = [
  { label: 'Supervisor（默认）', value: 'supervisor' },
  { label: '销售助手', value: 'visit' },
  { label: '培训助手', value: 'course' },
  { label: '决策助手', value: 'kpi' },
  { label: '知识助手', value: 'rag' },
]

// 右侧可收起 AI 助手面板
export default function AIAssistantPanel() {
  const location = useLocation()
  // 在 /ai 独立 AI 页面，隐藏常驻 AIAssistantPanel（避免遮挡右侧"主动建议"面板）
  // 同时也与 App.tsx 的全局 AISidebar 保持单一入口
  const isAIPage = location.pathname.startsWith('/ai')

  const open = useAIAssistantStore((s) => s.open)
  const pinned = useAIAssistantStore((s) => s.pinned)
  const toggle = useAIAssistantStore((s) => s.toggle)
  const pin = useAIAssistantStore((s) => s.pin)
  const setOpen = useAIAssistantStore((s) => s.setOpen)
  const currentAgent = useAIAssistantStore((s) => s.currentAgent)
  const setAgent = useAIAssistantStore((s) => s.setAgent)
  const messages = useAIAssistantStore((s) => s.messages)
  const newSession = useAIAssistantStore((s) => s.newSession)

  const { loading, sendMessage } = useAI()
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  // 消息更新时滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    sendMessage(input)
    setInput('')
  }

  return (
    <>
      {isAIPage ? null : (
        <>
      {/* 悬浮触发按钮（面板收起时） */}
      <AnimatePresence>
        {!open && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            onClick={toggle}
            className="fixed bottom-6 right-6 z-40 flex items-center justify-center w-14 h-14 rounded-full bg-gradient-to-br from-brand-500 to-violet-500 text-white shadow-lg shadow-brand-500/30 hover:shadow-xl hover:scale-105 transition-all"
            title="打开 AI 助手"
          >
            <Sparkles className="w-6 h-6" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* 面板 */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.25, ease: [0.19, 1, 0.22, 1] }}
            className={`fixed top-0 right-0 bottom-0 z-40 w-96 flex flex-col bg-white dark:bg-slate-900 shadow-2xl border-l border-slate-200 dark:border-slate-800`}
          >
            {/* 顶部：Agent 选择 + 操作 */}
            <div className="flex items-center gap-2 px-4 h-14 border-b border-slate-200 dark:border-slate-800 shrink-0">
              <Bot className="w-5 h-5 text-brand-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <Select
                  value={currentAgent}
                  onChange={(e) => setAgent(e.target.value)}
                  options={agentOptions}
                  className="!h-8 !text-sm"
                />
              </div>
              <button
                onClick={newSession}
                title="新会话"
                className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
              <button
                onClick={pin}
                title={pinned ? '取消固定' : '固定面板'}
                className={`p-1.5 rounded-lg transition-colors ${
                  pinned
                    ? 'text-brand-500 bg-brand-50 dark:bg-brand-900/30'
                    : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                {pinned ? <Pin className="w-4 h-4" /> : <PinOff className="w-4 h-4" />}
              </button>
              <button
                onClick={() => setOpen(false)}
                title="关闭"
                className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* 消息列表 */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-100 to-violet-100 dark:from-brand-900/30 dark:to-violet-900/30 mb-3">
                    <Sparkles className="w-8 h-8 text-brand-500" />
                  </div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200">AI 助手已就绪</p>
                  <p className="mt-1 text-xs text-slate-400">输入你的问题，让我来帮你</p>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                  >
                    <div
                      className={`flex items-center justify-center w-8 h-8 rounded-lg shrink-0 ${
                        msg.role === 'user'
                          ? 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                          : 'bg-gradient-to-br from-brand-500 to-violet-500 text-white'
                      }`}
                    >
                      {msg.role === 'user' ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>
                    <div className={`flex-1 min-w-0 ${msg.role === 'user' ? 'flex flex-col items-end' : ''}`}>
                      <div
                        className={`inline-block px-3 py-2 rounded-2xl text-sm ${
                          msg.role === 'user'
                            ? 'bg-brand-600 text-white rounded-tr-sm'
                            : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-tl-sm'
                        }`}
                      >
                        {msg.pending ? (
                          <span className="flex items-center gap-1.5 text-slate-400">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" /> 思考中...
                          </span>
                        ) : msg.error ? (
                          <span className="flex items-center gap-1.5 text-rose-500">
                            <AlertCircle className="w-3.5 h-3.5" /> {msg.error}
                          </span>
                        ) : (
                          <span className="whitespace-pre-wrap break-words">{msg.content}</span>
                        )}
                      </div>
                      {/* Agent 与 Action 标签 */}
                      {msg.agent_used && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          <Badge variant="info">agent: {msg.agent_used}</Badge>
                          {msg.actions_called?.map((a) => (
                            <Badge key={a} variant="default">{a}</Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* 底部输入 */}
            <form onSubmit={handleSubmit} className="p-3 border-t border-slate-200 dark:border-slate-800 shrink-0">
              <div className="flex items-end gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSubmit(e)
                    }
                  }}
                  rows={1}
                  placeholder="输入消息，Enter 发送..."
                  className="flex-1 max-h-32 resize-none rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || loading}
                  className="flex items-center justify-center w-10 h-10 rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
        </>
      )}
    </>
  )
}
