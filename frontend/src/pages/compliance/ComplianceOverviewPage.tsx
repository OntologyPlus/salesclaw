import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Megaphone, Send, ClipboardCheck, ArrowRight } from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import { useFetch } from '@/hooks/useFetch'
import { complianceAPI, type PageRes, type PublicDisclosure, type RegulatorySubmission, type AnnualComplianceAudit } from '@/services/compliance'

interface ModuleCard {
  key: string
  title: string
  description: string
  icon: typeof Megaphone
  to: string
  total?: number
  accent: string
}

export default function ComplianceOverviewPage() {
  const navigate = useNavigate()

  const { data: disclosureRes } = useFetch<PageRes<PublicDisclosure>>(
    () => complianceAPI.listDisclosures({ page: 1, page_size: 1 }),
    []
  )
  const { data: submissionRes } = useFetch<PageRes<RegulatorySubmission>>(
    () => complianceAPI.listSubmissions({ page: 1, page_size: 1 }),
    []
  )
  const { data: auditRes } = useFetch<PageRes<AnnualComplianceAudit>>(
    () => complianceAPI.listAnnualAudits({ page: 1, page_size: 1 }),
    []
  )

  const cards: ModuleCard[] = [
    {
      key: 'disclosure',
      title: '合规公示',
      description: '将违规处置、备案异常、承诺违约等需监督的信息登记并对外公示（《医药代表管理办法》第 13 条）。',
      icon: Megaphone,
      to: '/compliance/disclosure',
      total: disclosureRes?.total,
      accent: 'from-amber-500 to-orange-500',
    },
    {
      key: 'submission',
      title: '监管报送',
      description: '按周期生成并向监管平台报送拜访、费用等合规数据，支持预览、导出与推送。',
      icon: Send,
      to: '/compliance/submission',
      total: submissionRes?.total,
      accent: 'from-sky-500 to-blue-500',
    },
    {
      key: 'audit',
      title: '年度审计',
      description: '年度合规审计结论与证据链完整性评估，沉淀专项审计档案。',
      icon: ClipboardCheck,
      to: '/compliance/audit',
      total: auditRes?.total,
      accent: 'from-violet-500 to-purple-500',
    },
  ]

  return (
    <div>
      <PageHeader
        title="合规总览"
        description="医药代表合规专项工作台：公示、监管报送与年度审计的统一入口。"
        breadcrumbs={[{ label: '合规专项' }, { label: '总览' }]}
        icon={<ShieldCheck className="w-5 h-5" />}
        gradient
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {cards.map((c) => {
          const Icon = c.icon
          return (
            <button
              key={c.key}
              onClick={() => navigate(c.to)}
              className="group text-left rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-md transition-all"
            >
              <div className="flex items-center justify-between">
                <div className={`flex items-center justify-center w-11 h-11 rounded-xl bg-gradient-to-br ${c.accent} text-white`}>
                  <Icon className="w-5 h-5" />
                </div>
                <span className="text-xs text-slate-400 dark:text-slate-500">
                  {c.total != null ? `${c.total} 条记录` : ''}
                </span>
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1">
                {c.title}
                <ArrowRight className="w-4 h-4 text-slate-300 dark:text-slate-600 group-hover:text-brand-500 transition-colors" />
              </h3>
              <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
                {c.description}
              </p>
            </button>
          )
        })}
      </div>

      <div className="mt-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">合规专项说明</h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
          合规专项围绕《医药代表管理办法》要求，覆盖「公示监督—监管报送—年度审计」三个闭环：
          公示用于内部与外部监督；报送用于向监管平台定期提供合规数据；审计用于年度证据链与结论归档。
          点击上方卡片进入对应模块。
        </p>
      </div>
    </div>
  )
}
