import React from 'react'
import {
  Activity,
  Database,
  Upload,
} from 'lucide-react'

import type { TabKey } from './knowledgeBaseModalModel'

const TABS: Array<{ key: TabKey; icon: React.ReactNode; label: string }> = [
  { key: 'documents', icon: <Database size={14} />, label: '文档列表' },
  { key: 'upload', icon: <Upload size={14} />, label: '上传文档' },
  { key: 'monitor', icon: <Activity size={14} />, label: '监控与检索' },
]

interface KnowledgeBaseTabsProps {
  activeTab: TabKey
  onTabChange: (tab: TabKey) => void
}

export const KnowledgeBaseTabs: React.FC<KnowledgeBaseTabsProps> = ({
  activeTab,
  onTabChange,
}) => (
  <div
    className="mb-5 flex gap-1 rounded-xl border border-bg-border bg-bg-tertiary p-1"
    data-testid="settings-kb-tabs"
  >
    {TABS.map((tab) => (
      <button
        key={tab.key}
        type="button"
        onClick={() => onTabChange(tab.key)}
        aria-label={tab.label}
        title={tab.label}
        className={`flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-all ${
          activeTab === tab.key
            ? 'border border-bg-border bg-bg-secondary text-text-primary shadow-sm'
            : 'text-text-secondary hover:text-text-primary'
        }`}
        data-testid={`settings-kb-tab-${tab.key}`}
      >
        {tab.icon}
        <span className="hidden sm:inline">{tab.label}</span>
      </button>
    ))}
  </div>
)
