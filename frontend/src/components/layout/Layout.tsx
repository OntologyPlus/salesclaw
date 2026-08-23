import type { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import AIAssistantPanel from '@/components/ai/AIAssistantPanel'

// 主布局：Sidebar + Header + Content + AIAssistantPanel
export default function Layout({ children }: { children?: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto bg-surface-app dark:bg-surface-app-dark p-6">
          {children || <Outlet />}
        </main>
      </div>
      <AIAssistantPanel />
    </div>
  )
}
