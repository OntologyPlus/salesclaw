import { forwardRef } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'prefix'> {
  label?: string
  prefix?: ReactNode
  suffix?: ReactNode
  error?: string
}

// 输入框组件，支持 label / prefix / suffix / error
const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, prefix, suffix, error, className = '', id, ...props }, ref) => {
    const inputId = id || props.name
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block mb-1.5 text-sm font-medium text-slate-700 dark:text-slate-300">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {prefix && (
            <span className="absolute left-3 text-slate-400 pointer-events-none">{prefix}</span>
          )}
          <input
            ref={ref}
            id={inputId}
            className={`w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100 dark:placeholder-slate-500 ${prefix ? 'pl-9' : ''} ${suffix ? 'pr-9' : ''} ${error ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-500/20' : ''} ${className}`}
            {...props}
          />
          {suffix && <span className="absolute right-3 text-slate-400">{suffix}</span>}
        </div>
        {error && <p className="mt-1 text-xs text-rose-500">{error}</p>}
      </div>
    )
  }
)

Input.displayName = 'Input'
export default Input
