import React, { useState } from 'react'
import { Activity, Database, RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'
import { KbChunkBrowser } from './KbChunkBrowser'
import { KbDangerZone } from './KbDangerZone'
import { KbHealthSummaryPanel } from './KbHealthSummaryPanel'
import { KbRetrievalTestPanel } from './KbRetrievalTestPanel'
import type { KbMonitorController } from './useKbMonitor'

interface KbMonitorPanelProps {
  monitor: KbMonitorController
}

export function KbMonitorPanel({ monitor }: KbMonitorPanelProps) {
  const [documentsVisible, setDocumentsVisible] = useState(false)
  const hasKnowledgeBase = Boolean(
    monitor.health &&
      monitor.health.index_status !== 'empty' &&
      monitor.health.total_chunks > 0,
  )

  return (
    <div className="space-y-4" data-testid="settings-kb-monitor-panel">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
          <Activity size={14} className="text-accent-blue" />
          知识库监控
        </h3>
        <Button
          variant="ghost"
          onClick={monitor.refreshCurrent}
          loading={monitor.loadingHealth}
          className="gap-1.5 text-xs"
          data-testid="settings-kb-refresh"
        >
          <RefreshCw size={12} />
          刷新
        </Button>
      </div>

      {monitor.actionError && (
        <div
          data-testid="settings-kb-monitor-error"
          className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
        >
          {monitor.actionError}
        </div>
      )}

      {monitor.loadingHealth && !monitor.health && (
        <div className="flex justify-center py-8">
          <span className="w-5 h-5 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {hasKnowledgeBase && monitor.health && (
        <>
          <KbHealthSummaryPanel
            health={monitor.health}
            documentsVisible={documentsVisible}
            onToggleDocuments={() => setDocumentsVisible((value) => !value)}
          />

          <KbChunkBrowser {...monitor.chunkBrowserProps} />

          <KbRetrievalTestPanel {...monitor.retrievalTestProps} />

          <KbDangerZone {...monitor.dangerZoneProps} />
        </>
      )}

      {!hasKnowledgeBase && !monitor.loadingHealth && (
        <div
          className="flex flex-col items-center gap-3 py-8 text-text-secondary/50"
          data-testid="settings-kb-empty-state"
        >
          <Database size={32} />
          <p className="text-sm">知识库未初始化或无法访问</p>
          <Button variant="ghost" onClick={monitor.refreshHealth}>
            重新检查
          </Button>
        </div>
      )}
    </div>
  )
}
