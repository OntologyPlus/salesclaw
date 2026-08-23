import { useState, useEffect, useCallback } from 'react'
import api from '@/services/api'

/**
 * AI 行标注 hook
 *
 * 接受一批数据行的摘要信息，调用后端 AI 获取每行的标注。
 * 返回每行对应的 AI 观察（如"该客户 30 天未拜访"）。
 *
 * 用法：
 *   const { annotations, loading } = useAIRowAnnotation({
 *     domain: 'sales',
 *     rows: records.map(r => ({ id: r.id, summary: `${r.hospital} - ${r.visit_date}` })),
 *   })
 *
 *   // 在表格中：
 *   {annotations[row.id] && (
 *     <span className="text-xs text-brand-600">{annotations[row.id]}</span>
 *   )}
 */

interface RowInput {
  id: string | number
  summary: string
}

interface UseAIRowAnnotationOptions {
  /** 业务域（用于路由到正确的 AI 端点） */
  domain: string
  /** 数据行摘要列表 */
  rows: RowInput[]
  /** 是否启用（默认 true） */
  enabled?: boolean
}

interface UseAIRowAnnotationResult {
  /** 每行 ID → AI 标注文本 */
  annotations: Record<string, string>
  /** 是否正在加载 */
  loading: boolean
  /** 重新获取 */
  refetch: () => void
}

export function useAIRowAnnotation({
  domain,
  rows,
  enabled = true,
}: UseAIRowAnnotationOptions): UseAIRowAnnotationResult {
  const [annotations, setAnnotations] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)

  const fetchAnnotations = useCallback(async () => {
    if (!enabled || rows.length === 0) return
    setLoading(true)
    try {
      // 构建批量请求：将行摘要发送给 AI 获取标注
      const summaries = rows.map(r => r.summary).join('\n')
      const prompt = `请对以下${domain}业务数据行进行简要的 AI 标注（每行一句话，指出值得注意的点）。如果某行没有特别之处，返回"正常"即可。\n\n数据行：\n${summaries}`

      const res = await api.post<{ data?: { response?: string } }>('/ai/chat/send', {
        message: prompt,
        stream: false,
      })

      const responseText = res.data?.data?.response || ''
      const lines = responseText.split('\n').filter(Boolean)

      // 尝试将 AI 返回的行与原始行一一对应
      const result: Record<string, string> = {}
      rows.forEach((row, i) => {
        if (lines[i]) {
          // 清理 AI 返回的序号前缀
          const cleaned = lines[i].replace(/^\d+[\.\)]\s*/, '').trim()
          if (cleaned && cleaned !== '正常') {
            result[String(row.id)] = cleaned
          }
        }
      })
      setAnnotations(result)
    } catch {
      // 静默失败：标注是增强功能，不应阻塞主流程
      setAnnotations({})
    } finally {
      setLoading(false)
    }
  }, [domain, rows, enabled])

  useEffect(() => {
    fetchAnnotations()
  }, [fetchAnnotations])

  return { annotations, loading, refetch: fetchAnnotations }
}

export default useAIRowAnnotation
