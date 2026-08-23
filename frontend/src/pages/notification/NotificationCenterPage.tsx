import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Bell, Plus, Power, Eye, Download, AlertCircle, RefreshCw, Clock, Send,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import DataTable, { type Column } from '@/components/data/DataTable'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Drawer from '@/components/ui/Drawer'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import FormField from '@/components/forms/FormField'
import Tabs from '@/components/ui/Tabs'
import Empty from '@/components/ui/Empty'
import api from '@/services/api'
import { notificationAPI } from '@/services/notification'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'

// 规则
interface NotificationRule extends Record<string, unknown> {
  id: number
  activity_id?: number
  scenario_id?: number
  rule_name?: string
  deadline?: string
  windows?: string[]
  frequency?: string
  send_times?: string[]
  channel?: string
  target_user_type?: string
  enabled?: number
}

// 批次
interface NotificationBatch extends Record<string, unknown> {
  id: number
  rule_id?: number
  trigger_at?: string
  window?: string
  target_count?: number
  success_count?: number
  failed_count?: number
  message_title?: string
  message_body?: string
}

// 收件人
interface NotificationRecipient {
  id: number
  batch_id?: number
  learner_id?: number
  status?: string
  reason?: string
  sent_at?: string
}

// 批次详情
interface BatchDetail extends NotificationBatch {
  recipients?: NotificationRecipient[]
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

const tabList = [
  { key: 'rules', label: '规则记录' },
  { key: 'batches', label: '发送记录' },
]

const channelMap: Record<string, string> = {
  in_app: '站内信',
  sms: '短信',
  email: '邮件',
  wechat: '企业微信',
}

const recipientStatusMap: Record<string, { label: string; variant: 'default' | 'success' | 'error' }> = {
  success: { label: '成功', variant: 'success' },
  failed: { label: '失败', variant: 'error' },
  pending: { label: '待发送', variant: 'default' },
}

export default function NotificationCenterPage() {
  const toast = useToast()
  const [tab, setTab] = useState('rules')

  // ── 规则列表 ──
  const [ruleKeyword, setRuleKeyword] = useState('')
  const [rulePage, setRulePage] = useState(1)
  const pageSize = 10

  const { data: ruleData, loading: ruleLoading, error: ruleError, refetch: refetchRules } = useFetch<PageRes<NotificationRule>>(
    () => notificationAPI.listRules({ keyword: ruleKeyword || undefined, page: rulePage, page_size: pageSize }),
    [ruleKeyword, rulePage]
  )
  const rules = ruleData?.items ?? []
  const ruleTotal = ruleData?.total ?? 0

  // 创建规则
  const [modalOpen, setModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    rule_name: '',
    activity_id: '',
    deadline: '',
    windows: 'D-3, D-2, D-1',
    send_times: '10:00, 16:00',
    channel: 'in_app',
    target_user_type: 'all',
  })

  // 状态切换
  const [togglingId, setTogglingId] = useState<number | null>(null)

  const handleCreateRule = async () => {
    if (!form.rule_name || !form.deadline) {
      toast('请填写规则名称与截止时间', 'warning')
      return
    }
    setSaving(true)
    try {
      await notificationAPI.createRule({
        rule_name: form.rule_name,
        activity_id: form.activity_id ? Number(form.activity_id) : null,
        deadline: form.deadline,
        windows: form.windows ? form.windows.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
        send_times: form.send_times ? form.send_times.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
        channel: form.channel,
        target_user_type: form.target_user_type,
      })
      toast('创建成功', 'success')
      setModalOpen(false)
      setForm({ rule_name: '', activity_id: '', deadline: '', windows: 'D-3, D-2, D-1', send_times: '10:00, 16:00', channel: 'in_app', target_user_type: 'all' })
      refetchRules()
    } catch (e) {
      toast(`创建失败：${(e as Error).message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleToggleRule = async (r: NotificationRule) => {
    const next = r.enabled ? 0 : 1
    setTogglingId(r.id)
    try {
      await notificationAPI.updateRuleStatus(r.id, next)
      toast(next ? '已启用' : '已停用', 'success')
      refetchRules()
    } catch (e) {
      toast(`操作失败：${(e as Error).message}`, 'error')
    } finally {
      setTogglingId(null)
    }
  }

  // ── 批次列表 ──
  const [batchPage, setBatchPage] = useState(1)
  const { data: batchData, loading: batchLoading, error: batchError, refetch: refetchBatches } = useFetch<PageRes<NotificationBatch>>(
    () => notificationAPI.listBatches({ page: batchPage, page_size: pageSize }),
    [batchPage]
  )
  const batches = batchData?.items ?? []
  const batchTotal = batchData?.total ?? 0

  // 批次详情抽屉
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [detail, setDetail] = useState<BatchDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [exporting, setExporting] = useState(false)

  const handleViewBatch = async (b: NotificationBatch) => {
    setDrawerOpen(true)
    setDetail(null)
    setDetailLoading(true)
    try {
      const res = await notificationAPI.getBatch(b.id)
      setDetail(res)
    } catch (e) {
      toast(`加载失败：${(e as Error).message}`, 'error')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleExportFailed = async (batchId: number) => {
    setExporting(true)
    try {
      const url = notificationAPI.exportFailedUrl(batchId)
      const res = await api.get(url, { responseType: 'blob' })
      const blob = res.data as Blob
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `failed_batch_${batchId}.csv`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(link.href)
      toast('导出成功', 'success')
    } catch (e) {
      toast(`导出失败：${(e as Error).message}`, 'error')
    } finally {
      setExporting(false)
    }
  }

  // 规则列
  const ruleColumns: Column<NotificationRule>[] = [
    {
      key: 'rule_name', title: '规则名',
      render: (r) => <span className="font-medium text-slate-900 dark:text-slate-100">{r.rule_name ?? '-'}</span>,
    },
    {
      key: 'deadline', title: '截止时间',
      render: (r) => (
        <span className="inline-flex items-center gap-1 text-slate-500">
          <Clock className="w-3.5 h-3.5" /> {r.deadline?.slice(0, 16) ?? '-'}
        </span>
      ),
    },
    {
      key: 'windows', title: '催促窗口',
      render: (r) => (
        <div className="flex items-center gap-1 flex-wrap">
          {(r.windows ?? []).map((w, i) => (
            <Badge key={i} variant="info">{w}</Badge>
          ))}
          {(r.windows ?? []).length === 0 && <span className="text-slate-400">-</span>}
        </div>
      ),
    },
    {
      key: 'channel', title: '渠道',
      render: (r) => <Badge variant="default">{channelMap[r.channel ?? 'in_app'] ?? r.channel}</Badge>,
    },
    {
      key: 'enabled', title: '状态',
      render: (r) => <Badge variant={r.enabled ? 'success' : 'default'}>{r.enabled ? '启用' : '停用'}</Badge>,
    },
    {
      key: 'actions', title: '操作', width: '120px',
      render: (r) => (
        <button
          onClick={() => handleToggleRule(r)}
          disabled={togglingId === r.id}
          className={`p-1.5 rounded-lg transition-colors disabled:opacity-40 ${
            r.enabled
              ? 'text-slate-500 hover:bg-slate-100 hover:text-rose-600 dark:hover:bg-slate-700'
              : 'text-slate-500 hover:bg-slate-100 hover:text-emerald-600 dark:hover:bg-slate-700'
          }`}
          title={r.enabled ? '停用' : '启用'}
        >
          <Power className="w-4 h-4" />
        </button>
      ),
    },
  ]

  // 批次列
  const batchColumns: Column<NotificationBatch>[] = [
    {
      key: 'message_title', title: '消息标题',
      render: (b) => <span className="font-medium text-slate-900 dark:text-slate-100">{b.message_title ?? `批次 ${b.id}`}</span>,
    },
    {
      key: 'window', title: '窗口',
      render: (b) => <Badge variant="info">{b.window ?? '-'}</Badge>,
    },
    {
      key: 'target_count', title: '目标数',
      render: (b) => <span>{b.target_count ?? 0}</span>,
    },
    {
      key: 'success_count', title: '成功',
      render: (b) => <span className="text-emerald-600">{b.success_count ?? 0}</span>,
    },
    {
      key: 'failed_count', title: '失败',
      render: (b) => <span className={b.failed_count ? 'text-rose-600' : 'text-slate-500'}>{b.failed_count ?? 0}</span>,
    },
    {
      key: 'trigger_at', title: '触发时间',
      render: (b) => <span className="text-slate-500">{b.trigger_at?.slice(0, 16) ?? '-'}</span>,
    },
    {
      key: 'actions', title: '操作', width: '80px',
      render: (b) => (
        <button
          onClick={() => handleViewBatch(b)}
          className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-700 transition-colors"
          title="查看详情"
        >
          <Eye className="w-4 h-4" />
        </button>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="通知中心"
        description="催促规则管理与发送记录查询"
        breadcrumbs={[{ label: '通知中心' }]}
        icon={<Bell className="w-5 h-5" />}
        actions={
          tab === 'rules' ? (
            <Button onClick={() => setModalOpen(true)}>
              <Plus className="w-4 h-4" />
              新建规则
            </Button>
          ) : (
            <Button variant="secondary" onClick={refetchBatches}>
              <RefreshCw className="w-4 h-4" />
              刷新
            </Button>
          )
        }
      />

      <div className="mb-4">
        <Tabs tabs={tabList} activeKey={tab} onChange={setTab} />
      </div>

      {(tab === 'rules' ? ruleError : batchError) && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{(tab === 'rules' ? ruleError : batchError)?.message}</span>
        </div>
      )}

      {tab === 'rules' ? (
        <>
          <div className="mb-4">
            <div className="w-72">
              <Input
                placeholder="搜索规则名"
                value={ruleKeyword}
                onChange={(e) => { setRuleKeyword(e.target.value); setRulePage(1) }}
              />
            </div>
          </div>
          <DataTable<NotificationRule>
            columns={ruleColumns}
            data={rules}
            loading={ruleLoading}
            total={ruleTotal}
            page={rulePage}
            pageSize={pageSize}
            onPageChange={setRulePage}
            rowKey="id"
          />
        </>
      ) : (
        <DataTable<NotificationBatch>
          columns={batchColumns}
          data={batches}
          loading={batchLoading}
          total={batchTotal}
          page={batchPage}
          pageSize={pageSize}
          onPageChange={setBatchPage}
          rowKey="id"
        />
      )}

      {/* 创建规则 Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="新建催促规则"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>取消</Button>
            <Button loading={saving} onClick={handleCreateRule}>创建</Button>
          </>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <FormField label="规则名称" required>
              <Input placeholder="如：培训活动 D-3 催促" value={form.rule_name} onChange={(e) => setForm(p => ({ ...p, rule_name: e.target.value }))} />
            </FormField>
          </div>
          <FormField label="关联活动 ID">
            <Input type="number" placeholder="可选" value={form.activity_id} onChange={(e) => setForm(p => ({ ...p, activity_id: e.target.value }))} />
          </FormField>
          <FormField label="截止时间" required>
            <Input type="datetime-local" value={form.deadline} onChange={(e) => setForm(p => ({ ...p, deadline: e.target.value }))} />
          </FormField>
          <FormField label="催促窗口" hint="英文逗号分隔，如 D-3, D-2, D-1">
            <Input value={form.windows} onChange={(e) => setForm(p => ({ ...p, windows: e.target.value }))} />
          </FormField>
          <FormField label="发送时间" hint="英文逗号分隔，如 10:00, 16:00">
            <Input value={form.send_times} onChange={(e) => setForm(p => ({ ...p, send_times: e.target.value }))} />
          </FormField>
          <FormField label="通知渠道">
            <Select
              options={[
                { label: '站内信', value: 'in_app' },
                { label: '短信', value: 'sms' },
                { label: '邮件', value: 'email' },
                { label: '企业微信', value: 'wechat' },
              ]}
              value={form.channel}
              onChange={(e) => setForm(p => ({ ...p, channel: e.target.value }))}
            />
          </FormField>
          <FormField label="目标用户">
            <Select
              options={[
                { label: '全部', value: 'all' },
                { label: '学员', value: 'learner' },
                { label: '主管', value: 'manager' },
              ]}
              value={form.target_user_type}
              onChange={(e) => setForm(p => ({ ...p, target_user_type: e.target.value }))}
            />
          </FormField>
        </div>
      </Modal>

      {/* 批次详情抽屉 */}
      <Drawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="批次详情"
        width="w-[640px]"
      >
        <div className="p-5 space-y-4">
          {detailLoading ? (
            <div className="text-sm text-slate-400">加载中...</div>
          ) : !detail ? (
            <Empty description="暂无详情" />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                  <p className="text-xs text-slate-400">消息标题</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">{detail.message_title ?? '-'}</p>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                  <p className="text-xs text-slate-400">窗口</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">{detail.window ?? '-'}</p>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                  <p className="text-xs text-slate-400">目标 / 成功 / 失败</p>
                  <p className="mt-0.5 text-sm">
                    <span className="text-slate-900 dark:text-slate-100">{detail.target_count ?? 0}</span>
                    <span className="mx-1 text-slate-300">/</span>
                    <span className="text-emerald-600">{detail.success_count ?? 0}</span>
                    <span className="mx-1 text-slate-300">/</span>
                    <span className="text-rose-600">{detail.failed_count ?? 0}</span>
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-700/40">
                  <p className="text-xs text-slate-400">触发时间</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">{detail.trigger_at ?? '-'}</p>
                </div>
              </div>

              {detail.message_body && (
                <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-700">
                  <p className="text-xs text-slate-400 mb-1">消息内容</p>
                  <p className="text-sm text-slate-700 dark:text-slate-200">{detail.message_body}</p>
                </div>
              )}

              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">人员明细</h4>
                {detail.failed_count ? (
                  <Button size="sm" variant="secondary" loading={exporting} onClick={() => handleExportFailed(detail.id)}>
                    <Download className="w-3.5 h-3.5" />
                    导出失败名单
                  </Button>
                ) : null}
              </div>

              <div className="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800/80">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300">学员ID</th>
                      <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300">状态</th>
                      <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300">失败原因</th>
                      <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-300">时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                    {(detail.recipients ?? []).length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-slate-400">暂无明细</td>
                      </tr>
                    ) : (
                      (detail.recipients ?? []).slice(0, 50).map((r) => {
                        const s = recipientStatusMap[r.status ?? 'pending'] ?? recipientStatusMap.pending
                        return (
                          <motion.tr key={r.id}>
                            <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{r.learner_id ?? '-'}</td>
                            <td className="px-3 py-2"><Badge variant={s.variant}>{s.label}</Badge></td>
                            <td className="px-3 py-2 text-slate-500 truncate max-w-[200px]">{r.reason || '-'}</td>
                            <td className="px-3 py-2 text-slate-400">{r.sent_at?.slice(0, 16) ?? '-'}</td>
                          </motion.tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>
              {(detail.recipients?.length ?? 0) > 50 && (
                <p className="text-xs text-slate-400 text-center">仅展示前 50 条，可导出失败名单查看完整列表</p>
              )}
            </>
          )}
        </div>
      </Drawer>
    </div>
  )
}
