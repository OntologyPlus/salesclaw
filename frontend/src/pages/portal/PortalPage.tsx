import { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  GraduationCap, Sparkles, CalendarCheck, FileText, Map,
  Award, TrendingUp, BookOpen, Send, Loader2, Bot,
  ChevronRight, Zap, Link2, BadgeCheck, MessageSquarePlus, CalendarDays, Package,
} from 'lucide-react'
import useAuthStore from '@/stores/auth'
import StatCard from '@/components/data/StatCard'
import { useFetch } from '@/hooks/useFetch'
import { portalAPI } from '@/services/sales'
import { chatSend } from '@/services/ai'
import Skeleton from '@/components/ui/Skeleton'
import ErrorState from '@/components/ui/ErrorState'
import PageAIContextBar from '@/components/ai/PageAIContextBar'
import SectionCard from '@/components/layout/SectionCard'
import PageGrid from '@/components/layout/PageGrid'
import api from '@/services/api'

// 门户概览数据结构
interface PortalOverview {
  visit_count?: number
  plan_count?: number
  total_points?: number
  coverage_rate?: number
  training_courses?: number
  enrolled_courses?: number
  certificates?: number
  credits?: number
  knowledge_docs?: number
  pending_tasks?: number
}

// 活动项结构
interface Activity {
  id?: number | string
  type?: string
  title?: string
  content?: string
  description?: string
  created_at?: string
  time?: string
  date?: string
}

// AI 简报数据
interface AIBriefing {
  greeting: string
  summary: string
  actions: { label: string; prompt: string }[]
}

// AI 洞察数据
interface InsightData {
  summary: string
  insights: { level: string; message: string; type?: string }[]
  risk_alerts: { level?: string; message: string }[]
}

// 生成时间问候
function getTimeGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

// 获取 AI 简报
async function fetchAIBriefing(overview: PortalOverview | undefined): Promise<AIBriefing> {
  try {
    // 后端没有 /portal/ai-insights 端点，门户复用 decision 内容（综合销售+培训）
    const res = await api.post<InsightData>('/decision/ai-insights')
    const data = res.data
    const actions: { label: string; prompt: string }[] = []
    if (data.risk_alerts?.length > 0) {
      actions.push({ label: '查看风险项', prompt: '今天有哪些需要关注的风险项？' })
    }
    if ((overview?.plan_count ?? 0) > 0) {
      actions.push({ label: '执行今日计划', prompt: '帮我规划今天的拜访路线' })
    }
    actions.push({ label: '问 AI 更多', prompt: '关于今天的工作数据，有什么建议？' })
    return {
      greeting: `${getTimeGreeting()}，${data.summary || 'AI 已为你整理好今日工作要点'}`,
      summary: data.summary || 'AI 正在分析你的数据...',
      actions: actions.slice(0, 3),
    }
  } catch {
    // Fallback 静态文案
    return {
      greeting: getTimeGreeting(),
      summary: 'AI 正在学习你的工作模式，稍后将为你生成个性化简报。',
      actions: [
        { label: '查看今日计划', prompt: '今天有哪些拜访计划？' },
        { label: 'AI 工作建议', prompt: '今天应该优先做什么？' },
        { label: '问 AI 更多', prompt: '关于今天的工作，有什么建议？' },
      ],
    }
  }
}

// 获取 AI 洞察用于 StatCard
async function fetchInsightsForCards(domain: string): Promise<Record<string, string>> {
  try {
    const res = await api.post<{ data?: InsightData }>(`/${domain}/ai-insights`)
    const insights = res.data?.data?.insights ?? []
    const map: Record<string, string> = {}
    insights.forEach((ins, i) => {
      // 按顺序映射到卡片
      const keys = ['本月拜访', '已批计划', '覆盖率', '行为积分', '可用课程', '已选课程', '证书数', '累计学分']
      if (keys[i]) map[keys[i]] = ins.message
    })
    return map
  } catch {
    return {}
  }
}

// =================== PortalAIChat 子组件 ===================
interface ChatMsg {
  id: string
  role: 'user' | 'assistant'
  content: string
  loading?: boolean
}

function PortalAIChat() {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const quickQuestions = [
    '覆盖率为什么下降了？',
    '本周最佳拜访是哪个？',
    '有哪些待跟进的任务？',
  ]

  const handleSend = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return
    const userId = Math.random().toString(36).slice(2)
    const aiId = Math.random().toString(36).slice(2)
    setMessages(prev => [...prev, { id: userId, role: 'user', content: trimmed }])
    setMessages(prev => [...prev, { id: aiId, role: 'assistant', content: '', loading: true }])
    setLoading(true)
    setInput('')
    try {
      const res = await chatSend(trimmed, undefined, undefined)
      setMessages(prev => prev.map(m => m.id === aiId ? { ...m, content: res.response || '（AI 未返回）', loading: false } : m))
    } catch (e) {
      setMessages(prev => prev.map(m => m.id === aiId ? { ...m, content: `抱歉，发生错误：${e instanceof Error ? e.message : '请求失败'}`, loading: false } : m))
    } finally {
      setLoading(false)
    }
  }, [loading])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden">
      {/* 头部 */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-200 dark:border-surface-border-subtle-dark">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-500 to-violet-500 flex items-center justify-center ai-pulse">
          <Bot className="w-3.5 h-3.5 text-white" />
        </div>
        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">关于今天的数据，你想了解什么？</span>
      </div>

      {/* 消息区 */}
      {messages.length > 0 && (
        <div ref={scrollRef} className="max-h-64 overflow-y-auto px-5 py-3 space-y-3">
          {messages.map(msg => (
            <div key={msg.id} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                msg.role === 'user' ? 'bg-brand-600 text-white' : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
              }`}>
                {msg.role === 'user' ? <span className="text-xs">U</span> : <Bot className="w-3 h-3" />}
              </div>
              <div className={`max-w-[85%] px-3 py-2 rounded-xl text-sm ${
                msg.role === 'user'
                  ? 'bg-brand-600 text-white rounded-tr-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-tl-sm'
              }`}>
                {msg.loading ? (
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Loader2 className="w-3 h-3 animate-spin" /> 思考中...
                  </span>
                ) : (
                  <span className="whitespace-pre-wrap break-words">{msg.content}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 快捷问题 */}
      {messages.length === 0 && (
        <div className="px-5 py-3 flex items-center gap-2 flex-wrap">
          {quickQuestions.map(q => (
            <button
              key={q}
              onClick={() => handleSend(q)}
              className="px-3 py-1.5 rounded-full text-xs bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300 hover:bg-brand-100 dark:hover:bg-brand-900/50 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* 输入框 */}
      <div className="px-5 py-3 border-t border-slate-200 dark:border-surface-border-subtle-dark">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(input) } }}
            placeholder="输入你的问题..."
            disabled={loading}
            className="flex-1 h-9 rounded-xl border border-slate-200 dark:border-surface-border-subtle-dark bg-white dark:bg-surface-card-dark px-3 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:opacity-50"
          />
          <button
            onClick={() => handleSend(input)}
            disabled={!input.trim() || loading}
            className="flex items-center justify-center w-9 h-9 rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// =================== 主组件 ===================
export default function PortalPage() {
  const user = useAuthStore((s) => s.user)

  // 获取门户概览数据
  const { data: overview, loading: overviewLoading, error: overviewError, refetch: refetchOverview } = useFetch<PortalOverview>(
    () => portalAPI.getOverview(),
    []
  )
  // 获取最近活动
  const { data: activitiesResp, loading: activitiesLoading, error: activitiesError, refetch: refetchActivities } = useFetch<{ items: Activity[] } | Activity[]>(
    () => portalAPI.getActivities(),
    []
  )
  const portalError = overviewError || activitiesError

  // AI 简报
  const [briefing, setBriefing] = useState<AIBriefing | null>(null)
  const [briefingLoading, setBriefingLoading] = useState(true)
  const [insightMap, setInsightMap] = useState<Record<string, string>>({})

  // 加载 AI 简报和洞察
  useEffect(() => {
    fetchAIBriefing(overview ?? undefined).then(data => {
      setBriefing(data)
      setBriefingLoading(false)
    })
    fetchInsightsForCards('decision').then(setInsightMap)
  }, [overview])

  // 活动列表
  const activityList = Array.isArray(activitiesResp)
    ? activitiesResp.slice(0, 8)
    : (activitiesResp?.items ?? []).slice(0, 8)

  // 活动图标和颜色
  const activityIcon = (type?: string) => {
    if (type === 'visit') return <CalendarCheck className="w-4 h-4 text-brand-600" />
    if (type === 'course_completed') return <GraduationCap className="w-4 h-4 text-emerald-600" />
    if (type === 'exam_submitted') return <Award className="w-4 h-4 text-amber-600" />
    return <FileText className="w-4 h-4 text-slate-400" />
  }

  const activityBg = (type?: string) => {
    if (type === 'visit') return 'bg-brand-100 dark:bg-brand-900/30'
    if (type === 'course_completed') return 'bg-emerald-100 dark:bg-emerald-900/30'
    if (type === 'exam_submitted') return 'bg-amber-100 dark:bg-amber-900/30'
    return 'bg-slate-100 dark:bg-slate-700'
  }

  // AI 观察节点（插入在活动流中）
  const aiObservations = [
    { afterIndex: 1, message: 'AI 注意到：本周拜访频率较上周有所变化' },
    { afterIndex: 4, message: 'AI 建议：部分客户已超过 2 周未跟进' },
  ]

  // N+AI原生闭环：AI 决策流（四类编排器意图聚合，可解释/可追溯）
  interface FlowNode {
    key: string
    label: string
    summary?: string
    source?: string
    reasoning_chain_id?: string | number | null
    count?: number
    icon: React.ReactNode
  }
  const [aiFlow, setAiFlow] = useState<FlowNode[]>([])
  const [aiFlowLoading, setAiFlowLoading] = useState(true)
  useEffect(() => {
    let alive = true
    ;(async () => {
      setAiFlowLoading(true)
      const nodes: FlowNode[] = []
      // 主动建议（suggest）
      try {
        const r = await api.get('/ai/suggestions/ai')
        const d = r.data?.data ?? r.data
        nodes.push({
          key: 'suggest', label: '主动建议', summary: d?.summary, source: d?.source,
          reasoning_chain_id: d?.reasoning_chain_id, count: d?.suggestions?.length,
          icon: <Sparkles className="w-4 h-4" />,
        })
      } catch { /* 忽略单链路失败 */ }
      // AI 洞察（insight）
      try {
        const r = await api.get('/ai/insight/ai?domain=sales')
        const d = r.data?.data ?? r.data
        nodes.push({
          key: 'insight', label: '智能洞察', summary: d?.summary, source: d?.source,
          reasoning_chain_id: d?.reasoning_chain_id, count: d?.insights?.length,
          icon: <TrendingUp className="w-4 h-4" />,
        })
      } catch { /* 忽略单链路失败 */ }
      // 效果归因评估（evaluate）—取最近一条已完成执行
      try {
        const r = await api.get('/decision/executions?limit=1&status=completed')
        const items = r.data?.data?.items ?? r.data?.items ?? []
        const execId = items[0]?.execution_id
        if (execId != null) {
          const e = await api.post('/decision/effect/evaluate', { execution_id: execId })
          const d = e.data?.data ?? e.data
          nodes.push({
            key: 'evaluate', label: '效果归因', summary: d?.summary, source: d?.source,
            reasoning_chain_id: d?.reasoning_chain_id,
            icon: <Zap className="w-4 h-4" />,
          })
        }
      } catch { /* 忽略单链路失败 */ }
      // 范式沉淀（derive_paradigm）—取最近一条
      try {
        const r = await api.get('/decision/paradigms')
        const items = r.data?.data ?? r.data ?? []
        if (Array.isArray(items) && items.length > 0) {
          const p = items[0]
          nodes.push({
            key: 'paradigm', label: '范式沉淀', summary: p.title, source: p.reasoning_chain_id ? 'ai' : 'rule',
            reasoning_chain_id: p.reasoning_chain_id,
            icon: <BookOpen className="w-4 h-4" />,
          })
        }
      } catch { /* 忽略单链路失败 */ }
      if (alive) {
        setAiFlow(nodes)
        setAiFlowLoading(false)
      }
    })()
    return () => { alive = false }
  }, [])

  // 统计卡片配置（带 AI 洞察）
  const stats = [
    { title: '本月拜访', value: overview?.visit_count ?? '-', icon: <CalendarCheck className="w-5 h-5" />, color: 'brand' as const, trend: 12, aiExplainable: true },
    { title: '已批计划', value: overview?.plan_count ?? '-', icon: <FileText className="w-5 h-5" />, color: 'blue' as const, trend: 8, aiExplainable: true },
    { title: '覆盖率', value: overview?.coverage_rate != null ? `${overview.coverage_rate}%` : '-', icon: <Map className="w-5 h-5" />, color: 'emerald' as const, trend: 5, aiExplainable: true },
    { title: '行为积分', value: overview?.total_points ?? '-', icon: <Award className="w-5 h-5" />, color: 'amber' as const, trend: -3, aiExplainable: true },
    { title: '可用课程', value: overview?.training_courses ?? '-', icon: <BookOpen className="w-5 h-5" />, color: 'emerald' as const, trend: 0, aiExplainable: false },
    { title: '已选课程', value: overview?.enrolled_courses ?? '-', icon: <GraduationCap className="w-5 h-5" />, color: 'brand' as const, trend: 0, aiExplainable: true },
    { title: '证书数', value: overview?.certificates ?? '-', icon: <Award className="w-5 h-5" />, color: 'violet' as const, trend: 0, aiExplainable: false },
    { title: '累计学分', value: overview?.credits ?? '-', icon: <TrendingUp className="w-5 h-5" />, color: 'blue' as const, trend: 0, aiExplainable: true },
  ]

  return (
    <div className="space-y-6">
      {/* AI 状态条 */}
      <PageAIContextBar />

      {portalError && (
        <ErrorState
          message={portalError.message}
          onRetry={() => {
            refetchOverview()
            refetchActivities()
          }}
        />
      )}

      {/* 合规与学术快捷入口 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { to: '/training/onboarding', label: '对话式上岗备案', desc: '培训-考核-承诺', icon: BadgeCheck },
          { to: '/collab/academic-chat', label: '对话式学术活动', desc: '门禁驱动全流程', icon: MessageSquarePlus },
          { to: '/collab/academic-board', label: '学术三流看板', desc: '协议·签到·费用', icon: CalendarDays },
          { to: '/compliance/audit-pack', label: '稽查包导出', desc: '三流合一证据', icon: Package },
        ].map((item) => {
          const Icon = item.icon
          return (
            <Link
              key={item.to}
              to={item.to}
              className="flex items-start gap-3 rounded-2xl border border-slate-200 dark:border-surface-border-subtle-dark bg-white dark:bg-surface-card-dark p-4 hover:border-brand-300 dark:hover:border-brand-700 transition-colors"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300 shrink-0">
                <Icon className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{item.label}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{item.desc}</div>
              </div>
            </Link>
          )
        })}
      </div>

      {/* ====== A1: AI 晨间简报卡片 ====== */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark p-6"
      >
        {/* 顶部柔和渐变装饰，保留晨报质感但统一边框 */}
        <div className="absolute inset-0 bg-gradient-to-r from-brand-500/5 via-transparent to-violet-500/5 dark:from-brand-500/10 dark:to-violet-500/10 pointer-events-none" />

        <div className="relative">
          <div className="flex items-start gap-4">
            {/* AI 脉冲指示器 */}
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-br from-brand-500 to-violet-500 text-white shrink-0 ai-pulse">
              <Sparkles className="w-6 h-6" />
            </div>

            <div className="flex-1 min-w-0">
              {/* 问候语 */}
              <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                {briefingLoading ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {getTimeGreeting()}，{user?.display_name || user?.username || 'User'}
                  </span>
                ) : (
                  `${briefing?.greeting}，${user?.display_name || user?.username || 'User'}`
                )}
              </h1>

              {/* AI 简报摘要 */}
              <div className="mt-3 flex items-start gap-2 max-w-2xl rounded-xl bg-slate-50 dark:bg-slate-800 p-3 border border-slate-200 dark:border-surface-border-subtle-dark">
                <Zap className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" />
                <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                  {briefingLoading ? (
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      AI 正在生成今日简报...
                    </span>
                  ) : (
                    briefing?.summary
                  )}
                </p>
              </div>

              {/* AI 推荐操作 */}
              {briefing?.actions && (
                <div className="mt-3 flex items-center gap-2 flex-wrap">
                  {briefing.actions.map((action, i) => (
                    <button
                      key={i}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300 hover:bg-brand-100 dark:hover:bg-brand-900/50 transition-colors"
                    >
                      <Sparkles className="w-3 h-3" />
                      {action.label}
                      <ChevronRight className="w-3 h-3" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      {/* ====== N+AI原生闭环: AI 决策流（四类编排器意图聚合，可解释/可追溯） ====== */}
      <SectionCard
        title={
          <span className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-brand-500" />
            AI 决策流
          </span>
        }
        icon={null}
        action={<span className="text-xs font-normal text-slate-400">编排器七步状态机 · 可解释/可追溯</span>}
      >
        {aiFlowLoading ? (
          <p className="px-5 py-4 text-sm text-slate-400 flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> 正在汇聚 AI 推理链路…
          </p>
        ) : aiFlow.length === 0 ? (
          <p className="px-5 py-4 text-sm text-slate-400">暂无 AI 决策流数据</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 p-5">
            {aiFlow.map((node) => (
              <div
                key={node.key}
                className="rounded-xl border border-slate-200 dark:border-surface-border-subtle-dark bg-slate-50 dark:bg-slate-800 p-4"
              >
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200">
                    {node.icon}
                    {node.label}
                  </span>
                  {node.source && (
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                      node.source === 'ai'
                        ? 'bg-brand-500/15 text-brand-600 dark:text-brand-300'
                        : 'bg-slate-500/15 text-slate-400'
                    }`}>
                      {node.source === 'ai' ? 'AI 编排' : '规则'}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                  {node.summary || '—'}
                  {node.count != null && `（${node.count} 条）`}
                </p>
                {node.reasoning_chain_id && (
                  <Link
                    to={`/decision/reasoning-chain/${node.reasoning_chain_id}`}
                    className="mt-2 inline-flex items-center gap-1 text-xs text-brand-500 hover:underline"
                  >
                    <Link2 className="w-3.5 h-3.5" />
                    来源推理链
                  </Link>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* ====== A2: 统计概览（带 AI 解读） ====== */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            销售概览
            {Object.keys(insightMap).length > 0 && (
              <span className="flex items-center gap-1 text-xs font-normal text-brand-600 dark:text-brand-400">
                <Sparkles className="w-3 h-3" />
                AI 已解读
              </span>
            )}
          </h2>
        </div>
        <PageGrid loading={overviewLoading} skeletonCount={4}>
          {stats.slice(0, 4).map((stat, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <StatCard
                {...stat}
                aiInsight={insightMap[stat.title]}
                aiAlert={stat.trend !== undefined && stat.trend < 0}
              />
            </motion.div>
          ))}
        </PageGrid>

        <div className="flex items-center justify-between mb-3 mt-6">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">培训概览</h2>
        </div>
        <PageGrid loading={overviewLoading} skeletonCount={4}>
          {stats.slice(4).map((stat, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <StatCard
                {...stat}
                aiInsight={insightMap[stat.title]}
                aiAlert={false}
              />
            </motion.div>
          ))}
        </PageGrid>
      </div>

      {/* ====== A3: AI 活动时间线 ====== */}
      <SectionCard
        title={
          <span className="flex items-center gap-2">
            最近活动
            <span className="text-xs font-normal text-slate-400">（销售 + 培训）</span>
          </span>
        }
        icon={null}
        action={
          <span className="flex items-center gap-1 text-xs text-brand-600 dark:text-brand-400">
            <Sparkles className="w-3 h-3" />
            AI 排序
          </span>
        }
      >
        {activitiesLoading ? (
          <div className="p-5"><Skeleton lines={4} /></div>
        ) : activityList.length === 0 ? (
          <p className="p-5 text-sm text-slate-500 dark:text-slate-400 text-center">暂无活动</p>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-surface-border-subtle-dark">
            {activityList.map((act, i) => {
              const aiObs = aiObservations.find(obs => obs.afterIndex === i)
              return (
                <div key={act.id ?? i}>
                  <motion.div
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-start gap-3 px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                  >
                    <div className={`flex items-center justify-center w-8 h-8 rounded-lg ${activityBg(act.type)} shrink-0`}>
                      {activityIcon(act.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                        {act.title || act.content || '活动记录'}
                      </p>
                      {(act.description || act.content) && (
                        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 truncate">
                          {act.description || act.content}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {(act.type === 'visit' || act.type === 'course_completed') && (
                        <span className="flex items-center gap-1 text-[10px] text-brand-600 dark:text-brand-400">
                          <Sparkles className="w-2.5 h-2.5" />
                          相关
                        </span>
                      )}
                      {(act.date || act.created_at || act.time) && (
                        <span className="text-xs text-slate-400">
                          {act.date || act.created_at || act.time}
                        </span>
                      )}
                    </div>
                  </motion.div>
                  {aiObs && (
                    <div className="px-5 py-2">
                      <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-brand-300 dark:border-brand-700 bg-brand-50/50 dark:bg-brand-900/10">
                        <Sparkles className="w-3.5 h-3.5 text-brand-500 shrink-0" />
                        <span className="text-xs text-brand-700 dark:text-brand-300">{aiObs.message}</span>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </SectionCard>

      {/* ====== A4: 底部 AI 对话入口 ====== */}
      <PortalAIChat />
    </div>
  )
}
