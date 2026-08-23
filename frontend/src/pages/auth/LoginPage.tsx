import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useTranslation } from 'react-i18next'
import { Building2, User as UserIcon, Lock, Sparkles, AlertCircle } from 'lucide-react'
import { useState } from 'react'
import useAuthStore from '@/stores/auth'
import { login as loginApi } from '@/services/auth'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

// 表单校验 schema
const loginSchema = z.object({
  tenant_code: z.string().min(1, '租户码不能为空'),
  username: z.string().min(1, '用户名不能为空'),
  password: z.string().min(1, '密码不能为空'),
})

type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const loginStore = useAuthStore((s) => s.login)
  const [serverError, setServerError] = useState('')

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      tenant_code: 'demo',
      username: 'admin',
      password: 'demo123',
    },
  })

  const onSubmit = async (values: LoginForm) => {
    setServerError('')
    try {
      const data = await loginApi(values.username, values.password, values.tenant_code)
      loginStore(data)
      navigate('/portal')
    } catch (err) {
      const message = err instanceof Error ? err.message : '登录失败，请重试'
      setServerError(message)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden bg-slate-50 dark:bg-slate-900">
      {/* 渐变背景装饰 */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-brand-300/30 dark:bg-brand-700/20 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-violet-300/30 dark:bg-violet-700/20 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-sky-200/20 dark:bg-sky-800/10 blur-3xl" />
      </div>

      {/* 登录卡片 */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.19, 1, 0.22, 1] }}
        className="relative w-full max-w-md"
      >
        <div className="rounded-2xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-xl shadow-2xl border border-white/40 dark:border-slate-700/50 p-8">
          {/* Logo 与标题 */}
          <div className="flex flex-col items-center mb-8">
            <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-500 to-violet-500 text-white shadow-lg shadow-brand-500/30 mb-4">
              <Sparkles className="w-7 h-7" />
            </div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100 text-center">
              {t('login.title')}
            </h1>
            <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400 text-center">
              {t('login.subtitle')}
            </p>
          </div>

          {/* 服务器错误提示 */}
          {serverError && (
            <div className="flex items-start gap-2 mb-4 p-3 rounded-xl bg-rose-50 dark:bg-rose-900/30 border border-rose-200 dark:border-rose-800 text-sm text-rose-600 dark:text-rose-400">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{serverError}</span>
            </div>
          )}

          {/* 表单 */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label={t('login.tenant')}
              placeholder={t('login.tenantPlaceholder')}
              prefix={<Building2 className="w-4 h-4" />}
              error={errors.tenant_code?.message}
              {...register('tenant_code')}
            />
            <Input
              label={t('login.username')}
              placeholder={t('login.usernamePlaceholder')}
              prefix={<UserIcon className="w-4 h-4" />}
              error={errors.username?.message}
              {...register('username')}
            />
            <Input
              label={t('login.password')}
              type="password"
              placeholder={t('login.passwordPlaceholder')}
              prefix={<Lock className="w-4 h-4" />}
              error={errors.password?.message}
              {...register('password')}
            />

            <Button
              type="submit"
              size="lg"
              loading={isSubmitting}
              className="w-full !rounded-xl"
            >
              {isSubmitting ? t('login.loggingIn') : t('login.submit')}
            </Button>
          </form>

          {/* 演示提示 */}
          <p className="mt-6 text-center text-xs text-slate-400 dark:text-slate-500">
            {t('login.demoHint')} · tenant=demo / user=admin / password=demo123
          </p>
        </div>
      </motion.div>
    </div>
  )
}
