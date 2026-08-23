import type { ReactNode } from 'react'
import AIFieldExplainer from '@/components/ai/AIFieldExplainer'

interface FormFieldProps {
  label?: string
  required?: boolean
  hint?: string
  error?: string
  children: ReactNode
  /** 字段名（用于 AI 解释上下文） */
  fieldName?: string
  /** 字段是否需要 AI 解释（默认 false） */
  aiExplainable?: boolean
}

// 表单字段容器，统一 label / required / hint / error
export default function FormField({
  label,
  required,
  hint,
  error,
  children,
  fieldName,
  aiExplainable = false,
}: FormFieldProps) {
  return (
    <div className="w-full">
      {label && (
        <div className="flex items-center gap-1 mb-1.5">
          <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {label}
            {required && <span className="ml-0.5 text-rose-500">*</span>}
          </label>
          {aiExplainable && fieldName && (
            <AIFieldExplainer fieldName={fieldName} hint={hint} />
          )}
        </div>
      )}
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
      {error && <p className="mt-1 text-xs text-rose-500">{error}</p>}
    </div>
  )
}
