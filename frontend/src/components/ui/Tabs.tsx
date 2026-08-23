export interface TabItem {
  key: string
  label: string
}

interface TabsProps {
  tabs: TabItem[]
  activeKey: string
  onChange: (key: string) => void
}

// 标签页组件，underline 风格
export default function Tabs({ tabs, activeKey, onChange }: TabsProps) {
  return (
    <div className="border-b border-slate-200 dark:border-slate-700">
      <nav className="flex gap-1 -mb-px">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={`px-4 py-2.5 text-sm font-medium rounded-t-xl border-b-2 transition-colors ${
              activeKey === tab.key
                ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
