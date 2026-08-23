import { useState } from 'react'
import { motion } from 'framer-motion'
import { Brain, Star, AlertTriangle, ChevronDown, Loader2, Send } from 'lucide-react'
import { useFetch } from '@/hooks/useFetch'
import useAuthStore from '@/stores/auth'

// API 基础地址：优先使用 VITE_API_URL，回退到 /v1（与 services/api.ts 一致）
const API_BASE: string =
  ((import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_API_URL) ??
  '/v1'

// 推理步骤类型
type ReasoningStepType = 'deduction' | 'induction' | 'abduction'

// 推理步骤
interface ReasoningStep {
  type: ReasoningStepType
  premise: string
  conclusion: string
  confidence: number
}

// 推理链详情
interface ReasoningChainDetail {
  id: number
  steps?: ReasoningStep[]
  hallucination_score?: number
  [key: string]: unknown
}

interface ReasoningChainViewProps {
  chainId?: number
  className?: string
}

// 步骤类型样式：deduction=blue, induction=emerald, abduction=violet
const stepTypeStyles: Record<ReasoningStepType, { label: string; badge: string }> = {
  deduction: {
    label: '演绎',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  },
  induction: {
    label: '归纳',
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  },
  abduction: {
    label: '溯因',
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
  },
}

// 置信度归一化为百分比（兼容 0-1 与 0-100）
function toPercent(confidence: number): number {
  if (Number.isNaN(confidence)) return 0
  return confidence <= 1 ? confidence * 100 : confidence
}

// 置信度颜色：绿色>70%, 黄色40-70%, 红色<40%
function confidenceBarColor(pct: number): string {
  if (pct > 70) return 'bg-emerald-500'
  if (pct >= 40) return 'bg-amber-500'
  return 'bg-rose-500'
}

// 获取推理链详情
async function fetchReasoningChain(id: number): Promise<ReasoningChainDetail> {
  const token = useAuthStore.getState().token
  const res = await fetch(`${API_BASE}/ai/reasoning/chains/${id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`获取推理链失败: ${res.status}`)
  const json = await res.json()
  return (json?.data ?? json) as ReasoningChainDetail
}

// 推理链可视化组件
export default function ReasoningChainView({
  chainId,
  className = '',
}: ReasoningChainViewProps) {
  const [expanded, setExpanded] = useState(false)
  const [rating, setRating] = useState(0)
  const [hoverRating, setHoverRating] = useState(0)
  const [feedback, setFeedback] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const { data, loading, error } = useFetch<ReasoningChainDetail | null>(
    () => (chainId ? fetchReasoningChain(chainId) : Promise.resolve(null)),
    [chainId]
  )

  const steps = data?.steps ?? []
  const hallucinationScore = data?.hallucination_score

  // 提交用户反馈
  async function handleSubmitFeedback() {
    if (!chainId || rating <= 0 || submitting) return
    setSubmitting(true)
    try {
      const token = useAuthStore.getState().token
      const res = await fetch(`${API_BASE}/ai/reasoning/chains/${chainId}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ rating, feedback_text: feedback }),
      })
      if (!res.ok) throw new Error(`提交反馈失败: ${res.status}`)
      setSubmitted(true)
    } catch (err) {
      console.error(err)
    } finally {
      setSubmitting(false)
    }
  }

  // 无 chainId 时不渲染
  if (!chainId) return null

  return (
    <div
      className={`rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 ${className}`}
    >
      {/* 头部：折叠/展开 */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center w-full gap-2 px-4 py-3 text-left"
      >
        <Brain className="w-4 h-4 text-brand-500 shrink-0" />
        <span className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-200">
          推理链 #{chainId}
        </span>
        {loading && <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />}
        <ChevronDown
          className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
        />
      </button>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="px-4 pb-4 space-y-3 border-t border-slate-200 dark:border-slate-700 overflow-hidden"
        >
          {error && (
            <div className="flex items-center gap-2 mt-3 text-sm text-rose-500">
              <AlertTriangle className="w-4 h-4" />
              {error.message}
            </div>
          )}

          {/* 幻觉检测分数 */}
          {typeof hallucinationScore === 'number' && (
            <div className="mt-3 flex items-center gap-2 text-xs">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
              <span className="text-slate-500 dark:text-slate-400">幻觉检测分数</span>
              <span
                className={`font-medium ${
                  hallucinationScore > 0.5 ? 'text-rose-500' : 'text-emerald-500'
                }`}
              >
                {toPercent(hallucinationScore).toFixed(1)}%
              </span>
            </div>
          )}

          {/* 推理步骤列表 */}
          {steps.length > 0 ? (
            <div className="mt-3 space-y-3">
              {steps.map((step, idx) => {
                const style = stepTypeStyles[step.type] ?? stepTypeStyles.deduction
                const pct = toPercent(step.confidence ?? 0)
                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-700"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${style.badge}`}
                      >
                        {style.label}
                      </span>
                      <span className="text-xs text-slate-400">步骤 {idx + 1}</span>
                    </div>
                    <div className="space-y-1 text-sm">
                      <div className="text-slate-600 dark:text-slate-300">
                        <span className="text-slate-400">前提：</span>
                        {step.premise}
                      </div>
                      <div className="text-slate-700 dark:text-slate-200">
                        <span className="text-slate-400">结论：</span>
                        {step.conclusion}
                      </div>
                    </div>
                    {/* 置信度条形图 */}
                    <div className="mt-2">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400">置信度</span>
                        <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
                          {pct.toFixed(0)}%
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${confidenceBarColor(pct)}`}
                          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                        />
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          ) : (
            !loading &&
            !error && <p className="mt-3 text-sm text-slate-400">暂无推理步骤</p>
          )}

          {/* 用户评分与反馈 */}
          <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-slate-500 dark:text-slate-400">为这条推理链评分</span>
              <div className="flex items-center gap-0.5">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(0)}
                    className="p-0.5"
                    aria-label={`${star} 星`}
                  >
                    <Star
                      className={`w-4 h-4 ${
                        (hoverRating || rating) >= star
                          ? 'fill-amber-400 text-amber-400'
                          : 'text-slate-300 dark:text-slate-600'
                      }`}
                    />
                  </button>
                ))}
              </div>
            </div>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={2}
              placeholder="反馈（可选）"
              className="w-full max-h-32 resize-none rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
            <div className="flex items-center justify-end gap-2 mt-2">
              {submitted && <span className="text-xs text-emerald-500">反馈已提交</span>}
              <button
                type="button"
                onClick={handleSubmitFeedback}
                disabled={rating <= 0 || submitting}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-sm hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {submitting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                提交反馈
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
