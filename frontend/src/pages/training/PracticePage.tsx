import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare, AlertCircle, Send, Sparkles, Square, Trophy, Bot, User, Stethoscope, Building2,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Input from '@/components/ui/Input'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { trainingAPI } from '@/services/training'

// 演练场景
interface Scenario extends Record<string, unknown> {
  id: number | string
  title?: string
  description?: string
  scenario_type?: string
  difficulty?: string
  target_skills?: string[]
  is_published?: boolean
  doctor_id?: number
  doctor_name?: string
  hospital_id?: number
  hospital_name?: string
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 聊天消息
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

// 难度映射
const difficultyMap: Record<string, { label: string; variant: 'default' | 'warning' | 'success' | 'error' | 'info' }> = {
  easy: { label: '入门', variant: 'success' },
  medium: { label: '中级', variant: 'warning' },
  hard: { label: '高级', variant: 'error' },
}

export default function PracticePage() {
  const toast = useToast()
  const location = useLocation()
  const { data, loading, error } = useFetch<PageRes<Scenario>>(
    () => trainingAPI.listScenarios({ page: 1 }),
    []
  )

  const scenarios = data?.items ?? []

  // 当前会话
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [starting, setStarting] = useState(false)
  const [sending, setSending] = useState(false)
  const [ending, setEnding] = useState(false)

  // 评分结果
  const [result, setResult] = useState<{ score?: number; feedback?: string } | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 从覆盖分管页跳转来时，自动启动场景
  const autoStartHandled = useRef(false)
  useEffect(() => {
    if (autoStartHandled.current) return
    const state = location.state as { autoStartScenario?: Scenario; fromDoctorName?: string } | null
    if (state?.autoStartScenario) {
      autoStartHandled.current = true
      if (state.fromDoctorName) {
        toast(`已基于医生「${state.fromDoctorName}」生成场景，正在启动演练`, 'info')
      }
      handleStart(state.autoStartScenario)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  // 开始演练
  const handleStart = async (scenario: Scenario) => {
    setActiveScenario(scenario)
    setSessionId(null)
    setMessages([])
    setResult(null)
    setInput('')
    setStarting(true)
    try {
      const res = await trainingAPI.startPractice(scenario.id as number)
      setSessionId(res.session_id ?? null)
      setMessages([
        { id: Date.now().toString(), role: 'assistant', content: res.opening ?? '您好，让我们开始演练吧！' },
      ])
    } catch (e) {
      toast(`启动演练失败：${(e as Error).message}`, 'error')
      setActiveScenario(null)
    } finally {
      setStarting(false)
    }
  }

  // 发送消息
  const handleSend = async () => {
    if (!input.trim() || !sessionId) return
    const text = input.trim()
    const userMsg: ChatMessage = { id: Date.now().toString(), role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setSending(true)
    try {
      const res = await trainingAPI.practiceMessage(sessionId, text)
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', content: res.reply ?? '' },
      ])
    } catch (e) {
      toast(`发送失败：${(e as Error).message}`, 'error')
    } finally {
      setSending(false)
    }
  }

  // 结束演练
  const handleEnd = async () => {
    if (!sessionId) return
    if (!confirm('确认结束本次演练？结束后将获得 AI 评分。')) return
    setEnding(true)
    try {
      const res = await trainingAPI.endPractice(sessionId)
      setResult({ score: res.score, feedback: res.feedback })
      toast('演练已结束', 'success')
    } catch (e) {
      toast(`结束失败：${(e as Error).message}`, 'error')
    } finally {
      setEnding(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="场景演练"
        description="AI 驱动的销售场景对练，提升实战话术与应变能力"
        breadcrumbs={[{ label: '智能培训' }, { label: '场景演练' }]}
        icon={<MessageSquare className="w-5 h-5" />}
        actions={<AIActionButton label="AI生成演练" prompt="为我生成一个拜访演练场景" variant="ghost" size="sm" />}
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：场景列表 */}
        <div className="lg:col-span-1">
          <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-700">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">演练场景</h2>
            </div>
            <div className="divide-y divide-slate-100 dark:divide-slate-700 max-h-[600px] overflow-y-auto">
              {loading ? (
                <div className="p-5"><Skeleton lines={4} /></div>
              ) : scenarios.length === 0 ? (
                <Empty description="暂无演练场景" />
              ) : (
                scenarios.map((scenario, i) => {
                  const diff = difficultyMap[scenario.difficulty ?? 'medium'] ?? difficultyMap.medium
                  const active = activeScenario?.id === scenario.id
                  return (
                    <motion.button
                      key={scenario.id ?? i}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.04 }}
                      onClick={() => handleStart(scenario)}
                      className={`w-full text-left px-5 py-3 transition-colors ${
                        active
                          ? 'bg-brand-50 dark:bg-brand-900/20 border-l-2 border-brand-500'
                          : 'hover:bg-slate-50 dark:hover:bg-slate-700/40'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                          {scenario.title ?? '-'}
                        </span>
                        <Badge variant={diff.variant}>{diff.label}</Badge>
                      </div>
                      {scenario.description && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                          {scenario.description}
                        </p>
                      )}
                      {Array.isArray(scenario.target_skills) && scenario.target_skills.length > 0 && (
                        <div className="mt-1.5 flex items-center gap-1 flex-wrap">
                          {scenario.target_skills.slice(0, 3).map((s, si) => (
                            <span key={si} className="text-xs text-slate-400">#{s}</span>
                          ))}
                        </div>
                      )}
                      {/* 关联医生/医院标签 */}
                      {(scenario.doctor_name || scenario.hospital_name) && (
                        <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
                          {scenario.doctor_name && (
                            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs bg-sky-50 text-sky-600 dark:bg-sky-900/30 dark:text-sky-300">
                              <Stethoscope className="w-3 h-3" />
                              {scenario.doctor_name}
                            </span>
                          )}
                          {scenario.hospital_name && (
                            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-300">
                              <Building2 className="w-3 h-3" />
                              {scenario.hospital_name}
                            </span>
                          )}
                        </div>
                      )}
                    </motion.button>
                  )
                })
              )}
            </div>
          </div>
        </div>

        {/* 右侧：对话区 */}
        <div className="lg:col-span-2">
          <div className="rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 overflow-hidden flex flex-col h-[600px]">
            {/* 对话头部 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
              <div className="flex items-center gap-2 min-w-0">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-500 text-white shrink-0">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                    {activeScenario ? (activeScenario.title ?? '演练中') : 'AI 对练助手'}
                  </p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-xs text-slate-400">
                      {sessionId ? '会话进行中' : '请选择左侧场景开始演练'}
                    </p>
                    {activeScenario?.doctor_name && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs bg-sky-50 text-sky-600 dark:bg-sky-900/30 dark:text-sky-300">
                        <Stethoscope className="w-3 h-3" />
                        {activeScenario.doctor_name}
                      </span>
                    )}
                    {activeScenario?.hospital_name && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-300">
                        <Building2 className="w-3 h-3" />
                        {activeScenario.hospital_name}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              {sessionId && !result && (
                <Button size="sm" variant="danger" loading={ending} onClick={handleEnd}>
                  <Square className="w-3.5 h-3.5" /> 结束演练
                </Button>
              )}
            </div>

            {/* 消息区 */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-slate-50/50 dark:bg-slate-900/20">
              {!activeScenario && !starting && (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-100 to-violet-100 dark:from-brand-900/40 dark:to-violet-900/40 mx-auto mb-4">
                      <Sparkles className="w-8 h-8 text-brand-500" />
                    </div>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">选择场景，开始 AI 对练</p>
                    <p className="mt-1 text-xs text-slate-400">系统将模拟真实销售场景，与您进行对话式演练</p>
                  </div>
                </div>
              )}
              {starting && (
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Sparkles className="w-4 h-4 animate-pulse text-brand-500" />
                  AI 正在准备演练场景...
                </div>
              )}
              <AnimatePresence>
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                  >
                    <div className={`flex items-center justify-center w-8 h-8 rounded-lg shrink-0 ${
                      msg.role === 'user'
                        ? 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                        : 'bg-gradient-to-br from-brand-500 to-violet-500 text-white'
                    }`}>
                      {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>
                    <div className={`max-w-[75%] px-4 py-2.5 rounded-2xl text-sm ${
                      msg.role === 'user'
                        ? 'bg-brand-600 text-white rounded-tr-sm'
                        : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-tl-sm'
                    }`}>
                      {msg.content}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              {/* 评分结果 */}
              {result && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="p-5 rounded-2xl bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20 border border-brand-200 dark:border-brand-800"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 text-white">
                      <Trophy className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">演练评分</p>
                      <p className="text-2xl font-bold text-brand-600 dark:text-brand-400">{result.score ?? '-'} 分</p>
                    </div>
                  </div>
                  {result.feedback && (
                    <div>
                      <p className="text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">AI 反馈</p>
                      <p className="text-sm text-slate-600 dark:text-slate-300">{result.feedback}</p>
                    </div>
                  )}
                </motion.div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* 输入区 */}
            <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-700">
              {result ? (
                <div className="flex items-center justify-center">
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setActiveScenario(null)
                      setSessionId(null)
                      setMessages([])
                      setResult(null)
                    }}
                  >
                    选择新场景
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Input
                    placeholder={sessionId ? '输入您的回复...' : '请先选择场景开始演练'}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                    disabled={!sessionId || sending}
                  />
                  <Button onClick={handleSend} disabled={!sessionId || !input.trim() || sending} loading={sending}>
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
