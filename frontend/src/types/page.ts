// F-重构：页面级共享类型（消除各总览页重复定义）
import type { LucideIcon } from 'lucide-react'

/** 后端分页响应通用结构 */
export interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

/** 统计卡片数据项（与 StatCard props 对齐） */
export interface StatItem {
  title: string
  value: React.ReactNode
  icon: React.ReactNode
  color?: 'brand' | 'blue' | 'emerald' | 'cyan' | 'amber' | 'pink' | 'rose' | 'violet'
  trend?: number
  aiInsight?: string
  aiAlert?: boolean
}

/** Badge 语义变体（与 components/ui/Badge 对齐） */
export type BadgeVariant = 'default' | 'warning' | 'success' | 'error' | 'info'

/** 状态/标签映射项 */
export interface StatusOption {
  label: string
  variant: BadgeVariant
}

export type StatusMap = Record<string, StatusOption>

/** 快捷入口项 */
export interface EntryItem {
  path: string
  label: string
  desc?: string
  icon: React.ReactNode
  color?: StatItem['color']
}

/** 页内 AI 洞察的通用返回结构（兼容 /.../ai-insights 接口） */
export interface AiInsightPayload {
  summary?: string
  insights?: { level?: string; message: string }[]
  risk_alerts?: { message: string }[]
}

export type { LucideIcon }
