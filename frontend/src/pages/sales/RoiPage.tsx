import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, Legend,
} from 'recharts'
import { TrendingUp, DollarSign, Target, Sparkles, Coins, PiggyBank, BarChart3 } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import AIActionButton from '@/components/ai/AIActionButton'
import AIEnhancedPage from '@/components/ai/AIEnhancedPage'
import StatCard from '@/components/data/StatCard'

// 各产品 ROI 对比 Mock 数据
const productRoi = [
  { name: '心血通', roi: 3.5, input: 120, output: 420 },
  { name: '脑复康', roi: 2.8, input: 80, output: 224 },
  { name: '胃复安', roi: 4.2, input: 60, output: 252 },
]

// 月度 ROI 趋势 Mock 数据
const monthlyRoi = [
  { month: '1月', roi: 2.8 },
  { month: '2月', roi: 3.1 },
  { month: '3月', roi: 3.5 },
  { month: '4月', roi: 3.2 },
  { month: '5月', roi: 3.8 },
  { month: '6月', roi: 4.1 },
]

// AI 洞察 Mock 文本
const aiInsights = [
  '胃复安 ROI 最高（4.2x），建议增加该产品的拜访投入。',
  '脑复康 ROI 偏低（2.8x），可优化目标医院选择以提升效益。',
  '近 6 个月 ROI 呈上升趋势，从 2.8x 提升至 4.1x，增长 46%。',
]

// 统计 Mock 数据
const stats = [
  { title: '总投入', value: '¥260 万', icon: <Coins className="w-5 h-5" />, color: 'amber' as const, trend: 5 },
  { title: '总产出', value: '¥896 万', icon: <PiggyBank className="w-5 h-5" />, color: 'emerald' as const, trend: 18 },
  { title: 'ROI', value: '3.45x', icon: <TrendingUp className="w-5 h-5" />, color: 'rose' as const, trend: 12 },
  { title: '拜访效率', value: '85%', icon: <Target className="w-5 h-5" />, color: 'brand' as const, trend: 8 },
]

// 自定义 Tooltip
function RoiTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 px-3 py-2 shadow-lg text-xs">
      <p className="font-medium text-slate-900 dark:text-slate-100 mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-slate-600 dark:text-slate-300">
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  )
}

export default function RoiPage() {
  return (
    <AIEnhancedPage
      header={
        <PageHeader
          title="ROI 分析"
          description="投入产出分析与效益评估"
          breadcrumbs={[{ label: '销售执行' }, { label: 'ROI 分析' }]}
          icon={<TrendingUp className="w-5 h-5" />}
          gradient
          actions={<AIActionButton label="AI ROI分析" prompt="分析我的投入产出比，给出优化建议" variant="ghost" size="sm" />}
        />
      }
    >
      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((stat, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <StatCard {...stat} />
          </motion.div>
        ))}
      </div>

      {/* 图表区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* 各产品 ROI 对比柱状图 */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">各产品 ROI 对比</h2>
            <BarChart3 className="w-4 h-4 text-slate-400" />
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={productRoi} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:opacity-20" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <Tooltip content={<RoiTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="input" name="投入(万)" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                <Bar dataKey="output" name="产出(万)" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* 月度 ROI 趋势折线图 */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">月度 ROI 趋势</h2>
            <TrendingUp className="w-4 h-4 text-slate-400" />
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={monthlyRoi} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:opacity-20" />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} domain={[2, 5]} />
                <Tooltip content={<RoiTooltip />} />
                <Line
                  type="monotone"
                  dataKey="roi"
                  name="ROI"
                  stroke="#6366f1"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#6366f1' }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </div>

      {/* AI 洞察卡片 */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="rounded-2xl bg-gradient-to-r from-brand-50 to-violet-50 dark:from-brand-900/20 dark:to-violet-900/20 border border-brand-200 dark:border-brand-800 p-5"
      >
        <div className="flex items-center gap-2 mb-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">AI 洞察</h2>
        </div>
        <div className="space-y-2">
          {aiInsights.map((text, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
              <DollarSign className="w-4 h-4 mt-0.5 text-brand-500 shrink-0" />
              <span>{text}</span>
            </div>
          ))}
        </div>
      </motion.div>
    </AIEnhancedPage>
  )
}
