import { useState } from 'react'
import { Wand2, FileText, Save, AlertCircle, Check, ChevronRight, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import PageHeader from '@/components/data/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Input from '@/components/ui/Input'
import Skeleton from '@/components/ui/Skeleton'
import useToast from '@/hooks/useToast'
import { scenarioAPI } from '@/services/scenario'

type Step = 'input' | 'parsing' | 'review' | 'saving' | 'done'

interface ParsedScenario {
  title: string
  description: string
  scenario_type: string
  difficulty: string
  target_skills: string[]
  ai_roles: any[]
  scoring_rules: any[]
  standard_scripts: any[]
  knowledge_needs: string[]
  persona_id?: number
  persona_name?: string
}

const SAMPLE_TEXT = `### 场景：心内科主任拜访
某三甲医院心内科张主任，55 岁，主任医师，擅长冠心病介入治疗。
近期关注 PCI 术后抗血小板治疗的长期安全性，对新型 P2Y12 抑制剂有兴趣，
但担心出血风险。本次拜访目标：介绍产品 X 的长期安全性数据，推动进入处方流程。

### 关键话术要点
- 开场：基于近期 ESC 指南更新切入
- 洞察：询问当前处方习惯与顾虑
- 专业：呈现 12 个月随访数据
- 风控：出血风险管理策略
- 推进：建议小范围试用 5 例

### 评分维度
- 开场建立信任（20 分）
- 痛点洞察深度（25 分）
- 专业数据呈现（25 分）
- 风险应对（15 分）
- 推动行动（15 分）`

export default function ScenarioParsePage() {
  const toast = useToast()
  const [step, setStep] = useState<Step>('input')
  const [rawText, setRawText] = useState('')
  const [parsed, setParsed] = useState<ParsedScenario | null>(null)
  const [savedId, setSavedId] = useState<number | null>(null)

  // 编辑用本地状态
  const [editTitle, setEditTitle] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editType, setEditType] = useState('visit')
  const [editDifficulty, setEditDifficulty] = useState('medium')

  const handleParse = async () => {
    if (!rawText.trim()) {
      toast('请输入剧本文本', 'warning')
      return
    }
    setStep('parsing')
    try {
      const res = await scenarioAPI.parse(rawText)
      setParsed(res)
      setEditTitle(res.title ?? '')
      setEditDescription(res.description ?? '')
      setEditType(res.scenario_type ?? 'visit')
      setEditDifficulty(res.difficulty ?? 'medium')
      setStep('review')
      toast('解析完成，请确认并保存', 'success')
    } catch (e) {
      toast(`解析失败：${(e as Error).message}`, 'error')
      setStep('input')
    }
  }

  const handleSave = async () => {
    if (!parsed) return
    if (!editTitle.trim()) {
      toast('请输入场景标题', 'warning')
      return
    }
    setStep('saving')
    try {
      const payload = {
        title: editTitle.trim(),
        description: editDescription.trim(),
        scenario_type: editType,
        difficulty: editDifficulty,
        target_skills: parsed.target_skills ?? [],
        ai_roles: parsed.ai_roles ?? [],
        scoring_rules: parsed.scoring_rules ?? [],
        standard_scripts: parsed.standard_scripts ?? [],
        knowledge_needs: parsed.knowledge_needs ?? [],
        persona_id: parsed.persona_id ?? null,
        is_published: 0,
      }
      const res = await scenarioAPI.save(payload)
      setSavedId(res?.id ?? null)
      setStep('done')
      toast('场景已保存', 'success')
    } catch (e) {
      toast(`保存失败：${(e as Error).message}`, 'error')
      setStep('review')
    }
  }

  const handleReset = () => {
    setStep('input')
    setParsed(null)
    setSavedId(null)
    setRawText('')
  }

  const handleLoadSample = () => {
    setRawText(SAMPLE_TEXT)
    toast('已加载示例剧本', 'info')
  }

  const steps: { key: Step; label: string }[] = [
    { key: 'input', label: '粘贴剧本' },
    { key: 'review', label: '确认解析' },
    { key: 'done', label: '保存完成' },
  ]
  const currentIdx = steps.findIndex((s) => s.key === step || (step === 'parsing' && s.key === 'input') || (step === 'saving' && s.key === 'review'))

  return (
    <div>
      <PageHeader
        title="剧本解析三步创建"
        description="粘贴原始剧本 → AI 解析为结构化场景 → 确认保存为可演练场景"
        breadcrumbs={[{ label: '智能培训' }, { label: '剧本解析' }]}
        icon={<Wand2 className="w-5 h-5" />}
      />

      {/* 步骤指示器 */}
      <div className="mb-6 flex items-center gap-2">
        {steps.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs transition-colors ${
              i <= currentIdx
                ? 'bg-brand-500 text-white'
                : 'bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
            }`}>
              <span className="w-5 h-5 rounded-full bg-white/30 flex items-center justify-center text-xs font-bold">
                {i + 1}
              </span>
              {s.label}
            </div>
            {i < steps.length - 1 && <ChevronRight className="w-3 h-3 text-slate-300" />}
          </div>
        ))}
      </div>

      {/* 步骤 1：输入剧本 */}
      {(step === 'input' || step === 'parsing') && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-brand-500" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">原始剧本</h3>
              </div>
              <button onClick={handleLoadSample} className="text-xs text-brand-600 hover:underline">
                加载示例
              </button>
            </div>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="粘贴包含场景描述、话术要点、评分维度的原始剧本...支持 ### 章节标题分块解析"
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/30 dark:text-slate-100 min-h-[280px] font-mono resize-y"
              disabled={step === 'parsing'}
            />
            <div className="mt-3 flex items-center justify-between">
              <span className="text-xs text-slate-400">{rawText.length} 字</span>
              <Button onClick={handleParse} loading={step === 'parsing'} disabled={!rawText.trim()}>
                <Sparkles className="w-4 h-4" /> AI 解析剧本
              </Button>
            </div>
          </div>

          {/* 解析提示 */}
          <div className="rounded-xl bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800 p-4">
            <p className="text-xs text-brand-700 dark:text-brand-300">
              <strong>解析规则：</strong>
              AI 将自动识别剧本中的场景标题、目标技能、AI 角色配置、评分维度、标准话术分块，
              并基于关键词匹配自动关联角色画像库。无法识别时将使用默认模板。
            </p>
          </div>
        </motion.div>
      )}

      {/* 步骤 2：确认解析结果 */}
      {(step === 'review' || step === 'saving') && parsed && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          {step === 'saving' && <Skeleton lines={2} />}

          <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-500" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">解析结果确认</h3>
              </div>
              {parsed.persona_name && (
                <Badge variant="info">已匹配画像：{parsed.persona_name}</Badge>
              )}
            </div>

            {/* 基础信息编辑 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">场景标题 *</label>
                <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} disabled={step === 'saving'} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">类型</label>
                  <select
                    value={editType}
                    onChange={(e) => setEditType(e.target.value)}
                    disabled={step === 'saving'}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 dark:text-slate-100"
                  >
                    <option value="visit">拜访</option>
                    <option value="speech">演讲</option>
                    <option value="qa">问答</option>
                    <option value="negotiation">谈判</option>
                  </select>
                </div>
                <div>
                  <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">难度</label>
                  <select
                    value={editDifficulty}
                    onChange={(e) => setEditDifficulty(e.target.value)}
                    disabled={step === 'saving'}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 dark:text-slate-100"
                  >
                    <option value="easy">入门</option>
                    <option value="medium">中级</option>
                    <option value="hard">高级</option>
                  </select>
                </div>
              </div>
            </div>

            <div>
              <label className="block mb-1 text-xs font-medium text-slate-600 dark:text-slate-300">场景描述</label>
              <textarea
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                disabled={step === 'saving'}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 dark:text-slate-100 min-h-[60px] resize-y"
              />
            </div>

            {/* 目标技能 */}
            {parsed.target_skills?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">目标技能</p>
                <div className="flex flex-wrap gap-1">
                  {parsed.target_skills.map((s, i) => (
                    <span key={i} className="px-2 py-0.5 rounded text-xs bg-brand-50 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300">#{s}</span>
                  ))}
                </div>
              </div>
            )}

            {/* 评分维度 */}
            {parsed.scoring_rules?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">评分维度（共 {parsed.scoring_rules.length} 项）</p>
                <div className="space-y-1">
                  {parsed.scoring_rules.map((r, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-900/30 text-xs">
                      <span className="text-slate-700 dark:text-slate-300">{r.dimension ?? r.name ?? `维度 ${i + 1}`}</span>
                      <span className="text-slate-500">{r.weight ?? r.score ?? 0} 分</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 标准话术分块 */}
            {parsed.standard_scripts?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">标准话术分块（{parsed.standard_scripts.length} 段）</p>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {parsed.standard_scripts.map((s, i) => (
                    <div key={i} className="px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-900/30 text-xs text-slate-600 dark:text-slate-400">
                      <span className="text-slate-400 mr-1">[{i + 1}]</span>
                      {typeof s === 'string' ? s : s.content ?? JSON.stringify(s)}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* AI 角色 */}
            {parsed.ai_roles?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-600 dark:text-slate-300 mb-1.5">AI 角色（{parsed.ai_roles.length} 个）</p>
                <div className="flex flex-wrap gap-1">
                  {parsed.ai_roles.map((r, i) => (
                    <Badge key={i} variant="info">{r.role ?? r.name ?? `角色 ${i + 1}`}</Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <Button variant="secondary" onClick={() => setStep('input')} disabled={step === 'saving'}>
                返回修改
              </Button>
              <Button onClick={handleSave} loading={step === 'saving'}>
                <Save className="w-4 h-4" /> 保存为场景
              </Button>
            </div>
          </div>
        </motion.div>
      )}

      {/* 步骤 3：保存完成 */}
      {step === 'done' && (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
          <div className="rounded-2xl bg-gradient-to-r from-emerald-50 to-brand-50 dark:from-emerald-900/20 dark:to-brand-900/20 border border-emerald-200 dark:border-emerald-800 p-8 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-brand-500 text-white mb-4">
              <Check className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-2">场景已保存</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              场景「{editTitle}」已成功创建{savedId ? `（ID: ${savedId}）` : ''}，可前往「场景演练」开始对练。
            </p>
            <div className="flex items-center justify-center gap-2">
              <Button variant="secondary" onClick={handleReset}>
                继续解析下一个
              </Button>
              <a href="/training/practice" className="inline-flex items-center gap-1 px-4 py-2 rounded-lg bg-brand-500 hover:bg-brand-600 text-white text-sm transition-colors">
                前往演练 <ChevronRight className="w-4 h-4" />
              </a>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
