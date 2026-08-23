/**
 * 消息内容渲染（Markdown + 代码高亮）
 *
 * F13：替代原 WorkflowChatLayout 中的纯文本渲染 `{m.content}`。
 * - react-markdown + remark-gfm：支持 GFM（表格/任务列表/删除线等）
 * - rehype-highlight：代码块语法高亮
 * - 流式时尾部显示光标
 */
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'

interface Props {
  content: string
  streaming?: boolean
}

export default function MessageContent({ content, streaming }: Props) {
  if (!content) return null
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-pre:my-2 prose-pre:bg-slate-900 prose-pre:p-3 prose-pre:rounded-lg prose-code:before:content-none prose-code:after:content-none prose-code:bg-slate-100 dark:prose-code:bg-slate-700 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-[0.85em]">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
      {streaming && (
        <span className="inline-block w-1.5 h-4 ml-0.5 bg-brand-500 animate-pulse align-middle" />
      )}
    </div>
  )
}
