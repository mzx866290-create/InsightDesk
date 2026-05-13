import React from 'react'

import type { DocStats } from '../../api/client'

export interface DocumentStatsPanelProps {
  stats: DocStats
}

export const DocumentStatsPanel: React.FC<DocumentStatsPanelProps> = ({ stats }) => (
  <div data-testid="settings-documents-stats" className="bg-bg-tertiary rounded-lg p-3 text-xs space-y-1.5">
    <div className="flex justify-between">
      <span className="text-text-secondary">状态</span>
      <span data-testid="settings-documents-stats-status" className="text-text-primary">{stats.status}</span>
    </div>
    {stats.total_docs !== undefined && (
      <div className="flex justify-between">
        <span className="text-text-secondary">文档切片数</span>
        <span data-testid="settings-documents-stats-total-docs" className="text-text-primary">{stats.total_docs}</span>
      </div>
    )}
    {stats.store_path && (
      <div className="flex justify-between">
        <span className="text-text-secondary">存储路径</span>
        <span data-testid="settings-documents-stats-store-path" className="text-text-primary truncate max-w-[200px]">{stats.store_path}</span>
      </div>
    )}
  </div>
)
