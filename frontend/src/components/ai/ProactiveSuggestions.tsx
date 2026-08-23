import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MapPin,
  GraduationCap,
  MessageSquare,
  AlertCircle,
  BookOpen,
  Lightbulb,
  Loader2,
  ArrowRight,
  Check,
  X,
  Clock,
  Bot,
} from 'lucide-react'
import { useFetch } from '@/hooks/useFetch'
import api from '@/services/api'

// 建议类型
type SuggestionType =
  | 'coverage_reminder'
  | 'training_reminder'
  | 'feedback_followup'
  | 'kpi_alert'
  | 'knowledge_rec'

// 优先级
type Priority = 'high' | 'medium' | 'low'

// 主动建议（导出供其他组件复用）
export interface Suggestion {
  id: string | number
  type: SuggestionType
  title: string
  description?: string
  priority: Priority
  action_url?: string
  action_label?: string
  // N+4: 降权标记
  _demoted_by_effectiveness?: boolean
  _effectiveness_score?: number
}

// 后端原始建议结构（与 /ai/suggestions 接口对齐）
interface RawSuggestion {
  type?: string
  title?: string
  description?: string
  priority?: string
  action?: { type?: string; target?: string; label?: string }
  target_id?: number
  _demoted_by_effectiveness?: boolean
  _effectiveness_score?: number
  [key: string]: unknown
}

interface ProactiveSuggestionsProps {
  className?: string
  maxItems?: number
  /** 业务域过滤：仅显示该域相关建议（后端按 type 映射） */
  domain?: string
  /** 嵌入模式：作为侧栏时使用紧凑样式 */
  embedded?: boolean
  /** 自定义采纳回调：替代默认路由跳转 */
  onAction?: (suggestion: Suggestion) => void
}

// 建议类型 -> 图标
const iconMap: Record<SuggestionType, typeof MapPin> = {
  coverage_reminder: MapPin,
  training_reminder: GraduationCap,
  feedback_followup: MessageSquare,
  kpi_alert: AlertCircle,
  knowledge_rec: BookOpen,
}

// 域 → 建议 type 映射（客户端过滤）
// key 用 page 完整子路径（slug），与 AIEnhancedPage 的 domain 计算一致
const DOMAIN_TYPE_MAP: Record<string, SuggestionType[]> = {
  // 销售域子页差异化
  'sales-visit-plans':  ['coverage_reminder', 'kpi_alert', 'feedback_followup'],
  'sales-visit-records': ['feedback_followup', 'kpi_alert', 'knowledge_rec'],
  'sales-coverage':     ['coverage_reminder', 'kpi_alert', 'knowledge_rec'],
  'sales-roi':          ['kpi_alert', 'coverage_reminder', 'feedback_followup'],
  'sales-scoring':      ['kpi_alert', 'training_reminder'],
  // 培训域
  'training-courses':   ['training_reminder', 'knowledge_rec', 'kpi_alert'],
  // 决策/知识/CRM 域（顶级路径）
  'decision':           ['kpi_alert', 'feedback_followup'],
  'knowledge':          ['knowledge_rec', 'feedback_followup'],
  'crm':                ['coverage_reminder', 'feedback_followup'],
  // 兜底（用户用顶级路径）
  sales:                ['coverage_reminder', 'kpi_alert', 'feedback_followup'],
  training:             ['training_reminder', 'knowledge_rec'],
  collab:               ['feedback_followup', 'knowledge_rec'],
  // 门户
  portal:               ['coverage_reminder', 'kpi_alert', 'feedback_followup', 'training_reminder', 'knowledge_rec'],
}

// 优先级排序权重（high > medium > low）
const priorityOrder: Record<Priority, number> = { high: 0, medium: 1, low: 2 }

// 优先级样式：high=rose, medium=amber, low=slate
const priorityStyles: Record<
  Priority,
  { bg: string; text: string; border: string; dot: string }
> = {
  high: {
    bg: 'bg-rose-50 dark:bg-rose-900/20',
    text: 'text-rose-600 dark:text-rose-400',
    border: 'border-rose-200 dark:border-rose-800',
    dot: 'bg-rose-500',
  },
  medium: {
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    text: 'text-amber-600 dark:text-amber-400',
    border: 'border-amber-200 dark:border-amber-800',
    dot: 'bg-amber-500',
  },
  low: {
    bg: 'bg-slate-50 dark:bg-slate-900/40',
    text: 'text-slate-600 dark:text-slate-400',
    border: 'border-slate-200 dark:border-slate-800',
    dot: 'bg-slate-400',
  },
}

// 获取主动建议列表
async function fetchSuggestions(domain?: string): Promise<Suggestion[]> {
  const res = await api.get('/ai/suggestions', { params: domain ? { domain } : undefined })
  // api 拦截器已统一处理 401 与业务错误；成功时 data 为 ApiResponse
  // 后端多版本返回结构动态，用 any 兼容 {data:[...]} / {data:{items:[...]}} / {items:[...]}
  const json = res.data as any
  // 兼容三种返回结构：{data: {items: [...]}} / {data: [...]} / {items: [...]}
  const rawList: unknown =
    (json?.data && Array.isArray(json.data) ? json.data : null) ??
    (json?.data?.items && Array.isArray(json.data.items) ? json.data.items : null) ??
    (json?.items && Array.isArray(json.items) ? json.items : null) ??
    []
  return (rawList as RawSuggestion[]).map((raw, idx) => {
    // 类型归一化：未知类型回退为 knowledge_rec（兼容后端扩展）
    const validTypes: SuggestionType[] = [
      'coverage_reminder',
      'training_reminder',
      'feedback_followup',
      'kpi_alert',
      'knowledge_rec',
    ]
    const type = (validTypes as string[]).includes(raw.type ?? '')
      ? (raw.type as SuggestionType)
      : 'knowledge_rec'
    // 优先级归一化：未知值回退为 low
    const validPriorities: Priority[] = ['high', 'medium', 'low']
    const priority = (validPriorities as string[]).includes(raw.priority ?? '')
      ? (raw.priority as Priority)
      : 'low'
    // id 使用稳定唯一键：idx 保证唯一，type 作为命名空间避免与 target_id 冲突
    return {
      id: `${idx}-${type}`,
      type,
      title: raw.title ?? '未命名建议',
      description: raw.description,
      priority,
      action_url: raw.action?.target,
      action_label: raw.action?.label,
      _demoted_by_effectiveness: raw._demoted_by_effectiveness,
      _effectiveness_score: raw._effectiveness_score,
    }
  })
}

// N+4: 记录用户对建议的行动
async function recordSuggestionAction(
  suggestionId: string,
  actionType: 'accepted' | 'ignored' | 'dismissed',
  suggestionType?: SuggestionType,
): Promise<void> {
  const params: Record<string, string> = { action_type: actionType }
  if (suggestionType) params.suggestion_type = suggestionType
  await api.post(`/ai/suggestions/${encodeURIComponent(suggestionId)}/action`, null, { params })
}

// N+AI原生闭环：经编排器 suggest 意图获取 AI 原生建议
async function fetchAiSuggestions(domain?: string): Promise<Suggestion[]> {
  const res = await api.get('/ai/suggestions/ai', { params: domain ? { domain } : undefined })
  const json = res.data as any
  const payload = json?.data ?? json
  const rawList: RawSuggestion[] = Array.isArray(payload?.suggestions)
    ? payload.suggestions
    : []
  return rawList.map((raw, idx) => {
    const validTypes: SuggestionType[] = [
      'coverage_reminder', 'training_reminder', 'feedback_followup', 'kpi_alert', 'knowledge_rec',
    ]
    const type = (validTypes as string[]).includes(raw.type ?? '') ? (raw.type as SuggestionType) : 'knowledge_rec'
    const validPriorities: Priority[] = ['high', 'medium', 'low']
    const priority = (validPriorities as string[]).includes(raw.priority ?? '') ? (raw.priority as Priority) : 'low'
    return {
      id: `ai-${idx}-${type}`,
      type,
      title: raw.title ?? '未命名建议',
      description: raw.description,
      priority,
      action_url: raw.action?.target,
      action_label: raw.action?.label,
    }
  })
}

// 主动建议组件
export default function ProactiveSuggestions({
  className = '',
  maxItems,
  domain,
  embedded = false,
  onAction,
}: ProactiveSuggestionsProps) {
  const [aiMode, setAiMode] = useState(false)
  const { data, loading, error, refetch } = useFetch<Suggestion[]>(
    () => (aiMode ? fetchAiSuggestions(domain) : fetchSuggestions(domain)),
    [domain, aiMode],
  )
  const navigate = useNavigate()
  // N+4: 已行动的建议 ID 集合（本地移除，避免 60s 内重复显示）
  const [actionedIds, setActionedIds] = useState<Set<string>>(new Set())
  const [pendingAction, setPendingAction] = useState<string | null>(null)

  // 60 秒自动刷新
  useEffect(() => {
    const timer = setInterval(() => {
      refetch()
    }, 60000)
    return () => clearInterval(timer)
  }, [refetch])

  // 按优先级排序并截断，排除已行动的；并按 domain 客户端过滤
  const suggestions = useMemo(() => {
    const filtered = (data ?? []).filter((s) => {
      if (!actionedIds.has(String(s.id))) return true
      return false
    }).filter((s) => {
      if (!domain) return true
      // 客户端按建议 type 映射到业务域
      return DOMAIN_TYPE_MAP[domain]?.includes(s.type) ?? true
    })
    const sorted = filtered
      .slice()
      .sort((a, b) => {
        const pa = priorityOrder[a.priority] ?? 99
        const pb = priorityOrder[b.priority] ?? 99
        return pa - pb
      })
    return typeof maxItems === 'number' ? sorted.slice(0, maxItems) : sorted
  }, [data, maxItems, actionedIds, domain])

  function handleAction(s: Suggestion) {
    if (onAction) {
      onAction(s)
      return
    }
    if (s.action_url) {
      navigate(s.action_url)
    }
  }

  // N+4: 记录建议行动
  async function handleSuggestionAction(
    s: Suggestion,
    actionType: 'accepted' | 'ignored' | 'dismissed',
  ) {
    const sid = String(s.id)
    setPendingAction(sid)
    try {
      await recordSuggestionAction(sid, actionType, s.type)
      // 本地移除该建议
      setActionedIds((prev) => new Set(prev).add(sid))
      // 如果是 accepted 且有 action_url，导航到目标页面
      if (actionType === 'accepted' && s.action_url) {
        navigate(s.action_url)
      }
    } catch (e) {
      console.error('记录建议行动失败:', e)
    } finally {
      setPendingAction(null)
    }
  }

  return (
    <div
      className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 ${className}`}
    >
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="w-4 h-4 text-brand-500" />
        <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200">主动建议</h3>
        <button
          type="button"
          onClick={() => setAiMode((v) => !v)}
          className={`ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
            aiMode
              ? 'bg-brand-500/15 text-brand-600 dark:text-brand-300'
              : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 hover:bg-slate-200'
          }`}
          title="经 AI 编排器生成可解释建议"
        >
          <Bot className="w-3 h-3" />
          AI 原生
        </button>
        {loading && <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin" />}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-rose-500">
          <AlertCircle className="w-4 h-4" />
          {error.message}
        </div>
      )}

      {!loading && !error && suggestions.length === 0 && (
        <div className="py-8 text-center text-sm text-slate-400">暂无建议</div>
      )}

      <AnimatePresence mode="popLayout">
        {suggestions.map((s) => {
          const Icon = iconMap[s.type] ?? Lightbulb
          const style = priorityStyles[s.priority] ?? priorityStyles.low
          const isPending = pendingAction === String(s.id)
          return (
            <motion.div
              key={String(s.id)}
              layout
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className={`mb-2 last:mb-0 p-3 rounded-lg border ${style.border} ${style.bg}`}
            >
              <div className="flex items-start gap-2.5">
                <div
                  className={`flex items-center justify-center w-8 h-8 rounded-lg shrink-0 ${style.bg} ${style.text}`}
                >
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`inline-block w-1.5 h-1.5 rounded-full ${style.dot}`} />
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
                      {s.title}
                    </span>
                  </div>
                  {s.description && (
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                      {s.description}
                    </p>
                  )}
                  {s._demoted_by_effectiveness && (
                    <p className="mt-0.5 text-[10px] text-slate-400 dark:text-slate-500 italic">
                      此类建议采纳率较低，已降权显示
                    </p>
                  )}
                  {s.action_url && (
                    <button
                      type="button"
                      onClick={() => handleAction(s)}
                      className={`mt-2 inline-flex items-center gap-1 text-xs font-medium ${style.text} hover:underline`}
                    >
                      {s.action_label ?? '查看'}
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  )}
                  {/* N+4: 三按钮行动闭环 */}
                  <div className="mt-2 flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => handleSuggestionAction(s, 'accepted')}
                      className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded-md bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/20 dark:text-emerald-400 dark:hover:bg-emerald-900/40 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <Check className="w-3 h-3" />
                      接受
                    </button>
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => handleSuggestionAction(s, 'ignored')}
                      className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded-md bg-slate-50 text-slate-600 hover:bg-slate-100 dark:bg-slate-700/40 dark:text-slate-300 dark:hover:bg-slate-700/60 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <X className="w-3 h-3" />
                      忽略
                    </button>
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => handleSuggestionAction(s, 'dismissed')}
                      className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded-md bg-slate-50 text-slate-500 hover:bg-slate-100 dark:bg-slate-700/40 dark:text-slate-400 dark:hover:bg-slate-700/60 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <Clock className="w-3 h-3" />
                      稍后
                    </button>
                    {isPending && (
                      <Loader2 className="w-3 h-3 text-slate-400 animate-spin" />
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
