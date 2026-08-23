import { useState, useRef, useCallback, useMemo } from 'react'
import type { ReactNode } from 'react'
import { Sparkles, X, AlertCircle, Check, Copy } from 'lucide-react'
import api from '@/services/api'
import type { ApiResponse } from '@/types'
import Button from '@/components/ui/Button'
import { useToast } from '@/hooks/useToast'

// AI 聊天响应（包含推理链等扩展字段）
interface AIChatResult {
  response: string
  agent_used?: string
  intent?: string
  reasoning_chain?: unknown
  [key: string]: unknown
}

// 可采纳建议项（从 AI 响应文本中解析）
interface AdoptableSuggestion {
  text: string          // 建议原文
  label: string         // 短标签（默认取首句前 20 字）
}

interface AIActionButtonProps {
  label: string
  prompt: string
  onResult?: (result: string) => void
  /** 用户采纳某条建议时回调（采纳闭环入口） */
  onApplyAction?: (suggestion: AdoptableSuggestion, allText: string) => void
  variant?: 'primary' | 'ghost'
  size?: 'sm' | 'md'
  icon?: ReactNode
}

// 从 AI 响应中抽取"可采纳建议"——
function extractSuggestions(text: string): AdoptableSuggestion[] {
  if (!text) return []
  // 模式 1：编号列表 "1. xxx" / "2. xxx" / "① xxx"
  const numbered = text.match(/(?:^|\n)\s*(?:\d+[.、]|[-*•])\s*(.{4,80}?)(?=\n|$)/g)
  if (numbered && numbered.length >= 1) {
    return numbered.slice(0, 5).map(line => {
      const cleaned = line.replace(/^\s*(?:\d+[.、]|[-*•])\s*/, '').trim()
      return { text: cleaned, label: cleaned.slice(0, 18) + (cleaned.length > 18 ? '…' : '') }
    })
  }
  // 模式 2：包含"建议"或"推荐"关键词的短句
  const keywordMatch = text.match(/[^。\n]{4,60}(?:建议|推荐|应该|可以|试试|考虑)[^。\n]{0,40}/g)
  if (keywordMatch && keywordMatch.length >= 1) {
    return keywordMatch.slice(0, 5).map(s => ({ text: s.trim(), label: s.trim().slice(0, 18) + (s.length > 18 ? '…' : '') }))
  }
  return []
}

// AI 操作按钮：点击后调用 AI 聊天接口，结果在浮动卡片中展示
export default function AIActionButton({
  label,
  prompt,
  onResult,
  onApplyAction,
  variant = 'primary',
  size = 'md',
  icon,
}: AIActionButtonProps) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showCard, setShowCard] = useState(false)
  const [adoptedIdx, setAdoptedIdx] = useState<Set<number>>(new Set())
  const containerRef = useRef<HTMLDivElement>(null)
  const toast = useToast()

  const suggestions = useMemo(() => result ? extractSuggestions(result) : [], [result])

  const handleClick = useCallback(async () => {
    if (loading) return
    setLoading(true)
    setError(null)
    setShowCard(true)
    setAdoptedIdx(new Set())
    try {
      const res = await api.post<ApiResponse<AIChatResult>>('/ai/chat/send', {
        message: prompt,
      })
      const data = res.data.data
      const text = data?.response ?? ''
      setResult(text)
      onResult?.(text)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'AI 请求失败'
      setError(msg)
      toast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }, [loading, prompt, onResult, toast])

  const handleClose = useCallback(() => {
    setShowCard(false)
    setTimeout(() => {
      setResult(null)
      setError(null)
      setAdoptedIdx(new Set())
    }, 200)
  }, [])

  const handleAdopt = useCallback((s: AdoptableSuggestion, idx: number) => {
    if (adoptedIdx.has(idx)) return
    setAdoptedIdx(prev => new Set(prev).add(idx))
    if (onApplyAction && result) {
      onApplyAction(s, result)
      toast('已采纳建议', 'success')
    } else {
      // 默认行为：复制到剪贴板
      navigator.clipboard?.writeText(s.text).then(() => {
        toast('已复制建议到剪贴板', 'success')
      }).catch(() => {
        toast('采纳失败', 'error')
      })
    }
  }, [adoptedIdx, onApplyAction, result, toast])

  return (
    <div ref={containerRef} className="relative inline-block">
      <Button
        type="button"
        variant={variant === 'ghost' ? 'ghost' : 'primary'}
        size={size}
        loading={loading}
        onClick={handleClick}
      >
        {icon ?? <Sparkles className="w-4 h-4" />}
        {label}
      </Button>

      {/* 浮动结果卡片：底部居中 Modal 式展示（fixed 定位，不被父容器裁切，也不挡按钮区） */}
      {showCard && (
        <div
          className="fixed left-1/2 -translate-x-1/2 bottom-6 z-[60] w-[28rem] max-w-[calc(100vw-2rem)] rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xl overflow-hidden"
        >
          {/* 头部 */}
          <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40">
            <Sparkles className="w-3.5 h-3.5 text-brand-500 shrink-0" />
            <span className="flex-1 text-xs font-medium text-slate-600 dark:text-slate-300 truncate">
              AI 结果 · {suggestions.length > 0 && `${suggestions.length} 条可采纳`}
            </span>
            <button
              type="button"
              onClick={handleClose}
              className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              aria-label="关闭"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* 内容 */}
          <div className="p-3 max-h-64 overflow-y-auto">
            {loading && (
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <Sparkles className="w-4 h-4 animate-pulse" />
                <span>AI 思考中...</span>
              </div>
            )}

            {!loading && error && (
              <div className="flex items-start gap-2 text-sm text-rose-500">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {!loading && !error && result && (
              <>
                {/* 完整文字 */}
                <p className="text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap break-words leading-relaxed mb-3">
                  {result}
                </p>

                {/* 可采纳建议列表（采纳闭环） */}
                {suggestions.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                    <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">
                      一键采纳
                    </div>
                    <div className="space-y-1.5">
                      {suggestions.map((s, idx) => {
                        const adopted = adoptedIdx.has(idx)
                        return (
                          <div
                            key={idx}
                            className={`flex items-center gap-2 px-2 py-1.5 rounded-lg border text-xs transition-colors ${
                              adopted
                                ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800'
                                : 'bg-slate-50 dark:bg-slate-900/40 border-slate-200 dark:border-slate-800 hover:border-brand-300'
                            }`}
                          >
                            <span className="flex-1 text-slate-700 dark:text-slate-200 truncate">
                              {s.label}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleAdopt(s, idx)}
                              disabled={adopted}
                              className={`shrink-0 flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors ${
                                adopted
                                  ? 'bg-emerald-500 text-white cursor-default'
                                  : 'bg-brand-500 hover:bg-brand-600 text-white'
                              }`}
                            >
                              {adopted ? <><Check className="w-3 h-3" />已采纳</> : <><Copy className="w-3 h-3" />采纳</>}
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
