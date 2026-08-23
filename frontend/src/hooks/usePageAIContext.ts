import { useMemo, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import {
  Sparkles, MapPin, Calendar, TrendingUp, BookOpen, BarChart3,
  GraduationCap, Lightbulb, MessageSquare, AlertCircle, Users, Award,
  type LucideIcon,
} from 'lucide-react'

// 页面 AI 上下文类型
export interface PageAIAction {
  id: string
  label: string              // 用户看到的按钮文字
  prompt: string             // 发给 LLM 的完整 prompt
  icon: LucideIcon
  variant?: 'primary' | 'ghost'
  // 是否需要数据快照（如 plan_count）作为 prompt 上下文
  needSnapshot?: boolean
}

export interface PageAIContext {
  page: string                // 路径
  domain: string              // 业务域
  pageTitle: string           // 友好标题
  actions: PageAIAction[]     // 该页可用的 AI 操作
  dataSnapshot?: Record<string, unknown>  // 页面关键数据
}

// 路径 → 域 + 动作注册表
const PAGE_REGISTRY: Record<string, { domain: string; pageTitle: string; actions: () => PageAIAction[] }> = {
  '/sales/visit-plans': {
    domain: 'sales',
    pageTitle: '拜访计划',
    actions: () => [
      { id: 'plan-optimize', label: 'AI 优化我的计划', prompt: '基于当前用户的拜访计划列表，分析优先级、覆盖空白、节奏合理性，输出可执行的调整建议（建议具体到计划项）', icon: Calendar, variant: 'primary', needSnapshot: true },
      { id: 'plan-priority', label: 'AI 优先级重排', prompt: '重新计算当前用户所有拜访计划的优先级（按覆盖缺口、KOL 重要性、近期反馈），输出前 5 个应优先拜访的医生', icon: TrendingUp, needSnapshot: true },
      { id: 'plan-gap', label: 'AI 覆盖空白', prompt: '基于用户当前覆盖矩阵，找出 30 天未拜访且有 KOL 潜力的医生', icon: MapPin },
    ],
  },
  '/sales/visit-records': {
    domain: 'sales',
    pageTitle: '拜访记录',
    actions: () => [
      { id: 'visit-summarize', label: 'AI 汇总本周拜访', prompt: '汇总当前用户最近 7 天的拜访记录：总量、覆盖医院数、关键反馈、未跟进事项', icon: Sparkles, needSnapshot: true },
      { id: 'visit-anomaly', label: 'AI 检测异常', prompt: '基于当前用户的拜访记录，检测异常：连续 30 天未拜访的客户、反馈下滑、计划完成率低', icon: AlertCircle, needSnapshot: true },
      { id: 'visit-feedback', label: 'AI 反馈跟进', prompt: '从拜访记录中提取负面反馈和未跟进事项，生成行动建议', icon: MessageSquare },
    ],
  },
  '/sales/coverage': {
    domain: 'sales',
    pageTitle: '覆盖分析',
    actions: () => [
      { id: 'cov-gap', label: 'AI 覆盖空白', prompt: '基于覆盖矩阵，找出应优先覆盖但当前未覆盖的医院/医生', icon: MapPin, variant: 'primary' },
      { id: 'cov-kol', label: 'AI KOL 推荐', prompt: '基于当前覆盖范围，推荐潜在 KOL 医生并给出理由', icon: Users },
      { id: 'cov-roi', label: 'AI 覆盖 ROI', prompt: '分析当前覆盖策略的投入产出比，给出资源优化建议', icon: TrendingUp },
    ],
  },
  '/sales/roi': {
    domain: 'sales',
    pageTitle: 'ROI 分析',
    actions: () => [
      { id: 'roi-analyze', label: 'AI ROI 分析', prompt: '分析当前用户的投入产出比，识别高 ROI 和低 ROI 客户/产品', icon: TrendingUp, variant: 'primary' },
      { id: 'roi-optimize', label: 'AI 优化建议', prompt: '基于 ROI 趋势，给出可执行的资源重新分配建议', icon: Lightbulb },
    ],
  },
  '/sales/scoring': {
    domain: 'sales',
    pageTitle: '积分管理',
    actions: () => [
      { id: 'score-recommend', label: 'AI 积分建议', prompt: '分析当前用户积分情况，推荐可快速达成的积分项', icon: Award, variant: 'primary' },
      { id: 'score-path', label: 'AI 进阶路径', prompt: '基于当前积分和业绩，生成未来 3 个月积分进阶路径', icon: TrendingUp },
    ],
  },
  '/training/courses': {
    domain: 'training',
    pageTitle: '课程中心',
    actions: () => [
      { id: 'train-recommend', label: 'AI 推荐课程', prompt: '基于当前用户角色、近期业绩缺口、合规要求，推荐 3 门最值得学习的课程', icon: GraduationCap, variant: 'primary' },
      { id: 'train-compliance', label: 'AI 合规提醒', prompt: '检查当前用户合规培训到期情况，识别 30 天内需完成的培训', icon: AlertCircle },
    ],
  },
  '/decision/alert-disposition': {
    domain: 'decision',
    pageTitle: '异常预警',
    actions: () => [
      { id: 'alert-dispatch', label: 'AI 处置建议', prompt: '基于当前预警项，给出分级处置建议（高/中/低风险）', icon: AlertCircle, variant: 'primary' },
      { id: 'alert-impact', label: 'AI 影响评估', prompt: '评估每条预警对销售业绩的潜在影响', icon: BarChart3 },
    ],
  },
  '/knowledge': {
    domain: 'knowledge',
    pageTitle: '知识库',
    actions: () => [
      { id: 'kb-recommend', label: 'AI 推荐文档', prompt: '基于当前用户最近浏览和拜访话题，推荐相关知识文档', icon: BookOpen, variant: 'primary' },
      { id: 'kb-similar', label: 'AI 相似文档', prompt: '基于当前查看的文档，找 3 篇最相似的内部资料', icon: Sparkles },
    ],
  },
  '/crm': {
    domain: 'crm',
    pageTitle: '客户管理',
    actions: () => [
      { id: 'crm-segment', label: 'AI 客户分群', prompt: '基于客户画像和近期互动，自动分群（活跃/沉默/流失风险）', icon: Users, variant: 'primary' },
      { id: 'crm-followup', label: 'AI 跟进建议', prompt: '基于客户最近互动历史，推荐下次最佳跟进时间和话题', icon: MessageSquare },
    ],
  },
  '/portal': {
    domain: 'decision',  // portal 复用 decision 域的 ai-insights（综合销售+培训）
    pageTitle: '工作台',
    actions: () => [
      { id: 'portal-brief', label: 'AI 今日简报', prompt: '基于用户画像和近 7 天活动，生成今日重点 3 件事', icon: Sparkles, variant: 'primary' },
      { id: 'portal-summary', label: 'AI 本周小结', prompt: '汇总本周关键指标、待办、风险，输出小结', icon: BarChart3 },
    ],
  },
}

/**
 * 页面 AI 上下文 Hook
 *
 * 根据当前路由返回该页可用的 AI 能力和上下文。
 * 让任何业务页都能"开箱即用"地知道：我是谁、我在哪、用户是谁、能调哪些 AI。
 */
export function usePageAIContext() {
  const location = useLocation()

  const context = useMemo<PageAIContext | null>(() => {
    // 找到最长的前缀匹配
    const matchedPath = Object.keys(PAGE_REGISTRY)
      .filter(p => location.pathname === p || location.pathname.startsWith(p + '/'))
      .sort((a, b) => b.length - a.length)[0]

    if (!matchedPath) return null

    const def = PAGE_REGISTRY[matchedPath]
    return {
      page: matchedPath,
      domain: def.domain,
      pageTitle: def.pageTitle,
      actions: def.actions(),
    }
  }, [location.pathname])

  // 注册页面数据快照（业务页可在 useEffect 中调用）
  const setDataSnapshot = useCallback((_data: Record<string, unknown>) => {
    // 简化：快照通过 context.dataSnapshot 透传，由 PageAIContextBar 维护
  }, [])

  return { context, setDataSnapshot }
}
