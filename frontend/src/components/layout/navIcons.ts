// F9：Sidebar 导航图标集中映射表
// 避免在 Sidebar.tsx 中散落 40+ 个 lucide 图标导入
import {
  LayoutGrid, BarChart3, CalendarCheck, FileText, MessageSquare,
  Map, Award, Grid3x3, TrendingUp, GraduationCap, Lightbulb,
  Users, BookOpen, HeartHandshake, UsersRound, Wrench, Bot,
  Settings, Shield, Activity, Layers, Route, UserCheck, Target, ShieldCheck,
  Gauge, AlertTriangle, CheckSquare, FileCheck, Megaphone,
  HelpCircle, Network, Database, ListTodo, Trophy, Bell,
  Wand2, Presentation, Crown, GitBranch, FileUp, ClipboardCheck,
  FileSignature, AlertOctagon, Ban, BadgeCheck, CalendarDays, Package,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

// path -> 图标组件 映射
export const navIconMap: Record<string, LucideIcon> = {
  // 工作台
  '/portal': LayoutGrid,
  '/profile': Target,
  '/notification-center': Bell,
  // 销售执行
  '/sales': BarChart3,
  '/collection': Database,
  '/collection/todos': ListTodo,
  '/sales/plans': CalendarCheck,
  '/sales/records': FileText,
  '/sales/feedback': MessageSquare,
  '/sales/coverage': Map,
  '/sales/scoring': Award,
  '/sales/matrix': Grid3x3,
  '/sales/roi': TrendingUp,
  // 智能培训
  '/training': GraduationCap,
  '/training/onboarding': BadgeCheck,
  '/training/activities': Trophy,
  '/training/personas': Users,
  '/training/scenario-parse': Wand2,
  '/training/practice': MessageSquare,
  '/training/ppt-speech': Presentation,
  '/training/experience': Crown,
  '/training/courses': BookOpen,
  '/training/exams': FileText,
  '/training/paths': Route,
  '/training/my-learning': UserCheck,
  '/training/certificates': Award,
  '/training/effect': TrendingUp,
  // 决策支持
  '/decision': Lightbulb,
  '/decision/kpi': Gauge,
  '/decision/attribution': TrendingUp,
  '/decision/simulation': Lightbulb,
  '/decision/alerts': AlertTriangle,
  '/decision/executions': TrendingUp,
  '/decision/followup': GitBranch,
  '/decision/paradigms': BookOpen,
  '/decision/loop': GitBranch,
  '/decision/diagnosis': Shield,
  // 协同办公
  '/collab': Users,
  '/collab/academic-chat': MessageSquare,
  '/collab/academic-board': CalendarDays,
  '/collab/tasks': CheckSquare,
  '/collab/approvals': FileCheck,
  '/collab/announcements': Megaphone,
  // 知识库
  '/knowledge': BookOpen,
  '/knowledge/documents': FileText,
  '/knowledge/faqs': HelpCircle,
  // 业务应用
  '/crm': HeartHandshake,
  '/cfm': UsersRound,
  '/tools': Wrench,
  '/ai': Bot,
  // 系统管理
  '/platform': Layers,
  '/mdm': Grid3x3,
  '/ontology': Network,
  '/settings': Settings,
  '/audit': Shield,
  '/observability': Activity,
  '/compliance': ShieldCheck,
  '/compliance/profile': UserCheck,
  '/compliance/commitment': FileSignature,
  '/compliance/violation': AlertOctagon,
  '/compliance/audit-pack': Package,
  '/compliance/forbidden': Ban,
  '/compliance/disclosure': Megaphone,
  '/compliance/submission': FileUp,
  '/compliance/audit': ClipboardCheck,
}

export default navIconMap
