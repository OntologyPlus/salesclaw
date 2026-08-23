import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Award, AlertCircle, Download, Eye, Calendar, Hash, Trophy, FileText,
} from 'lucide-react'
import PageHeader from '@/components/data/PageHeader'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import Modal from '@/components/ui/Modal'
import Skeleton from '@/components/ui/Skeleton'
import Empty from '@/components/ui/Empty'
import { useFetch } from '@/hooks/useFetch'
import useToast from '@/hooks/useToast'
import { trainingAPI } from '@/services/training'

// 证书
interface Certificate {
  id: number | string
  title?: string
  cert_type?: string
  source_id?: number
  score?: number
  issued_at?: string
  expire_at?: string
  cert_no?: string
}

// 分页响应
interface PageRes<T> {
  items?: T[]
  total?: number
  page?: number
  page_size?: number
}

// 证书类型映射
const certTypeMap: Record<string, { label: string; variant: 'default' | 'success' | 'warning' | 'error' | 'info' }> = {
  exam: { label: '考试证书', variant: 'info' },
  course: { label: '课程证书', variant: 'success' },
  path: { label: '路径证书', variant: 'warning' },
  practice: { label: '演练证书', variant: 'default' },
}

export default function CertificatesPage() {
  const toast = useToast()
  const [page, setPage] = useState(1)
  const pageSize = 12

  const { data, loading, error } = useFetch<PageRes<Certificate>>(
    () => trainingAPI.listCertificates({ page }),
    [page]
  )

  // 详情 Modal
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailCert, setDetailCert] = useState<Certificate | null>(null)

  const items = data?.items ?? []

  // 查看详情
  const handleView = (cert: Certificate) => {
    setDetailCert(cert)
    setDetailOpen(true)
  }

  // 下载（Mock）
  const handleDownload = (cert: Certificate) => {
    toast(`证书 ${cert.cert_no ?? cert.id} 下载已开始（模拟）`, 'success')
  }

  return (
    <div>
      <PageHeader
        title="我的证书"
        description="能力认证与证书管理"
        breadcrumbs={[{ label: '智能培训' }, { label: '我的证书' }]}
        icon={<Award className="w-5 h-5" />}
      />

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-800 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>加载失败：{error.message}</span>
        </div>
      )}

      {/* 证书卡片列表 */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="p-5 rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark">
              <Skeleton lines={4} />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark">
          <Empty description="暂无证书，完成考试或课程即可获得" icon={<Trophy className="w-12 h-12" />} />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((cert, i) => {
            const ct = certTypeMap[cert.cert_type ?? 'exam'] ?? certTypeMap.exam
            const expired = cert.expire_at && new Date(cert.expire_at) < new Date()
            return (
              <motion.div
                key={cert.id ?? i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="rounded-2xl bg-white dark:bg-surface-card-dark border border-slate-200 dark:border-surface-border-subtle-dark overflow-hidden hover:shadow-md dark:hover:shadow-black/20 transition-shadow"
              >
                {/* 证书头部 */}
                <div className="relative p-5 bg-gradient-to-br from-brand-500 via-violet-500 to-sky-500 dark:from-brand-800 dark:via-violet-900 dark:to-sky-950 text-white">
                  <div className="absolute inset-0 bg-black/0 dark:bg-black/40" />
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.2),transparent_60%)] dark:bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.05),transparent_60%)]" />
                  <div className="relative">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-white/20">
                        <Award className="w-5 h-5" />
                      </div>
                      {expired && (
                        <span className="px-2 py-0.5 rounded-md bg-white/20 text-xs">已过期</span>
                      )}
                    </div>
                    <h3 className="text-base font-semibold truncate">{cert.title ?? '-'}</h3>
                    <p className="mt-0.5 text-xs text-white/80">证书编号：{cert.cert_no ?? '-'}</p>
                  </div>
                </div>

                {/* 证书信息 */}
                <div className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <Badge variant={ct.variant}>{ct.label}</Badge>
                    <span className="text-sm font-semibold text-amber-500 inline-flex items-center gap-1">
                      <Trophy className="w-3.5 h-3.5" /> {cert.score ?? '-'} 分
                    </span>
                  </div>
                  <div className="space-y-1.5 text-xs text-slate-500 dark:text-slate-400">
                    <p className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5" /> 颁发：{cert.issued_at ?? '-'}
                    </p>
                    {cert.expire_at && (
                      <p className="flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5" /> 到期：{cert.expire_at}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <Button size="sm" variant="secondary" onClick={() => handleView(cert)}>
                      <Eye className="w-3.5 h-3.5" /> 查看
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => handleDownload(cert)}>
                      <Download className="w-3.5 h-3.5" /> 下载
                    </Button>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      )}

      {/* 分页 */}
      {!loading && items.length > 0 && (
        <div className="mt-4 flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            上一页
          </button>
          <span className="px-3 text-slate-600 dark:text-slate-300">第 {page} 页</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={items.length < pageSize}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            下一页
          </button>
        </div>
      )}

      {/* 详情 Modal */}
      <Modal
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        title="证书详情"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDetailOpen(false)}>关闭</Button>
            {detailCert && (
              <Button onClick={() => handleDownload(detailCert)}>
                <Download className="w-4 h-4" /> 下载证书
              </Button>
            )}
          </>
        }
      >
        {detailCert && (
          <div className="space-y-4">
            {/* 证书预览 */}
            <div className="relative p-6 rounded-2xl bg-gradient-to-br from-brand-500 via-violet-500 to-sky-500 dark:from-brand-800 dark:via-violet-900 dark:to-sky-950 text-white text-center">
              <div className="absolute inset-0 bg-black/0 dark:bg-black/40 rounded-2xl" />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.2),transparent_60%)] dark:bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.05),transparent_60%)] rounded-2xl" />
              <div className="relative">
                <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-white/20 mx-auto mb-3">
                  <Award className="w-7 h-7" />
                </div>
                <p className="text-xs text-white/80 mb-1">证书编号</p>
                <p className="text-sm font-mono mb-3">{detailCert.cert_no ?? '-'}</p>
                <h3 className="text-lg font-semibold">{detailCert.title ?? '-'}</h3>
                <div className="mt-3 inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-white/20 text-sm">
                  <Trophy className="w-4 h-4" /> {detailCert.score ?? '-'} 分
                </div>
              </div>
            </div>

            {/* 详细信息 */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-surface-raised-dark">
                <p className="text-xs text-slate-400 inline-flex items-center gap-1">
                  <FileText className="w-3 h-3" /> 证书类型
                </p>
                <p className="mt-0.5">
                  <Badge variant={(certTypeMap[detailCert.cert_type ?? 'exam'] ?? certTypeMap.exam).variant}>
                    {(certTypeMap[detailCert.cert_type ?? 'exam'] ?? certTypeMap.exam).label}
                  </Badge>
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-surface-raised-dark">
                <p className="text-xs text-slate-400 inline-flex items-center gap-1">
                  <Hash className="w-3 h-3" /> 关联来源
                </p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">
                  #{detailCert.source_id ?? '-'}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-surface-raised-dark">
                <p className="text-xs text-slate-400 inline-flex items-center gap-1">
                  <Calendar className="w-3 h-3" /> 颁发日期
                </p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">
                  {detailCert.issued_at ?? '-'}
                </p>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-surface-raised-dark">
                <p className="text-xs text-slate-400 inline-flex items-center gap-1">
                  <Calendar className="w-3 h-3" /> 到期日期
                </p>
                <p className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">
                  {detailCert.expire_at ?? '长期有效'}
                </p>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
