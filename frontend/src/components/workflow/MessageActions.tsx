/**
 * 消息响应操作（复制/重新生成/反馈）
 *
 * F15：挂在 assistant 消息气泡下方，hover 时显示。
 * - 复制：写入剪贴板，Toast 提示
 * - 重新生成：调用 onRegenerate（由父组件提供）
 * - 反馈：赞/踩，调用 onFeedback（v5.0 仅 console.log 占位）
 */
import { useState } from 'react'
import { Copy, Check, RotateCcw, ThumbsUp, ThumbsDown } from 'lucide-react'
import { useToast } from '@/hooks/useToast'

interface Props {
  content: string
  onRegenerate?: () => void
  onFeedback?: (type: 'up' | 'down') => void
}

export default function MessageActions({ content, onRegenerate, onFeedback }: Props) {
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)
  const toast = useToast()

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      toast('已复制到剪贴板', 'success')
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast('复制失败，请手动选择文本', 'error')
    }
  }

  const handleFeedback = (type: 'up' | 'down') => {
    if (feedback) return // 已反馈过，避免重复
    setFeedback(type)
    onFeedback?.(type)
    toast(type === 'up' ? '感谢好评' : '已记录反馈', 'info')
  }

  const btnClass = 'msg-action-btn'

  return (
    <div className="flex items-center gap-0.5 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
      <button onClick={handleCopy} className={btnClass} title="复制">
        {copied ? (
          <Check className="w-3.5 h-3.5 text-emerald-500" />
        ) : (
          <Copy className="w-3.5 h-3.5" />
        )}
      </button>
      {onRegenerate && (
        <button onClick={onRegenerate} className={btnClass} title="重新生成">
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      )}
      <button
        onClick={() => handleFeedback('up')}
        className={btnClass}
        title="赞"
        disabled={feedback !== null}
      >
        <ThumbsUp
          className={`w-3.5 h-3.5 ${feedback === 'up' ? 'text-emerald-500' : ''}`}
        />
      </button>
      <button
        onClick={() => handleFeedback('down')}
        className={btnClass}
        title="踩"
        disabled={feedback !== null}
      >
        <ThumbsDown
          className={`w-3.5 h-3.5 ${feedback === 'down' ? 'text-rose-500' : ''}`}
        />
      </button>
    </div>
  )
}
