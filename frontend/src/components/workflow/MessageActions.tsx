/**
 * 消息响应操作（复制/重新生成/反馈）
 * 反馈按钮仅在传入 onFeedback（已接后端）时展示，避免占位误导。
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
    if (!onFeedback || feedback) return
    setFeedback(type)
    onFeedback(type)
    toast(type === 'up' ? '感谢好评' : '已记录反馈', 'info')
  }

  const btnClass = 'msg-action-btn'

  return (
    <div className="flex items-center gap-0.5 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
      <button type="button" onClick={handleCopy} className={btnClass} title="复制" aria-label="复制">
        {copied ? (
          <Check className="w-3.5 h-3.5 text-emerald-500" />
        ) : (
          <Copy className="w-3.5 h-3.5" />
        )}
      </button>
      {onRegenerate && (
        <button type="button" onClick={onRegenerate} className={btnClass} title="重新生成" aria-label="重新生成">
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      )}
      {onFeedback && (
        <>
          <button
            type="button"
            onClick={() => handleFeedback('up')}
            className={btnClass}
            title="赞"
            aria-label="有用"
            disabled={feedback !== null}
          >
            <ThumbsUp
              className={`w-3.5 h-3.5 ${feedback === 'up' ? 'text-emerald-500' : ''}`}
            />
          </button>
          <button
            type="button"
            onClick={() => handleFeedback('down')}
            className={btnClass}
            title="踩"
            aria-label="无用"
            disabled={feedback !== null}
          >
            <ThumbsDown
              className={`w-3.5 h-3.5 ${feedback === 'down' ? 'text-rose-500' : ''}`}
            />
          </button>
        </>
      )}
    </div>
  )
}
