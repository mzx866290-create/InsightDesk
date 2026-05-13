import React from 'react'
import { ChevronDown, ChevronUp, Database, FileText, HardDrive } from 'lucide-react'
import type { KBHealthData } from '../../api/client'
import { formatCount, formatUnixSecondsDate } from './kbMonitorModel'

interface KbHealthSummaryPanelProps {
  health: KBHealthData
  documentsVisible: boolean
  onToggleDocuments: () => void
}

function StatusDot({ status }: { status: 'healthy' | 'empty' | 'not_found' | 'error' }) {
  const color = status === 'healthy' ? 'bg-accent-green' : status === 'empty' ? 'bg-yellow-400' : 'bg-accent-red'
  const label = status === 'healthy' ? '健康' : status === 'empty' ? '空库' : status === 'not_found' ? '未找到' : '异常'

  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-xs">{label}</span>
    </span>
  )
}

export function KbHealthSummaryPanel({
  health,
  documentsVisible,
  onToggleDocuments,
}: KbHealthSummaryPanelProps) {
  return (
    <>
      <div
        className="bg-bg-tertiary rounded-xl p-4 space-y-3 border border-bg-border"
        data-testid="settings-kb-health-summary"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-secondary">索引状态</span>
          <span data-testid="settings-kb-health-status">
            <StatusDot status={health.index_status} />
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-secondary flex items-center gap-1.5">
            <Database size={11} />
            切片总数
          </span>
          <span className="text-sm font-semibold text-text-primary" data-testid="settings-kb-health-total-chunks">
            {formatCount(health.total_chunks)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-secondary flex items-center gap-1.5">
            <HardDrive size={11} />
            占用磁盘
          </span>
          <span className="text-xs text-text-primary">{health.store_size_mb} MB</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-secondary">向量模型</span>
          <span className="text-[11px] text-text-primary/70 truncate max-w-[180px]">{health.embedding_model}</span>
        </div>
        {health.last_updated && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-secondary">最后更新</span>
            <span className="text-[11px] text-text-primary/70">
              {formatUnixSecondsDate(health.last_updated)}
            </span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-secondary">存储路径</span>
          <span className="text-[11px] text-text-primary/70 truncate max-w-[180px]">{health.store_path}</span>
        </div>
      </div>

      {health.documents.length > 0 && (
        <div>
          <button
            onClick={onToggleDocuments}
            className="flex items-center gap-1.5 text-xs text-accent-blue/80 hover:text-accent-blue transition-colors mb-2"
            data-testid="settings-kb-documents-toggle"
          >
            {documentsVisible ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            文档（{health.documents.length}）
          </button>
          {documentsVisible && (
            <div
              className="rounded-lg border border-bg-border overflow-hidden text-xs"
              data-testid="settings-kb-documents-list"
            >
              <div className="bg-bg-tertiary/60 px-3 py-1.5 grid grid-cols-2 border-b border-bg-border">
                <span className="text-text-secondary/70 font-medium">文件</span>
                <span className="text-text-secondary/70 font-medium text-right">切片数</span>
              </div>
              {health.documents.map((doc, index) => (
                <div
                  key={`${doc.name}-${index}`}
                  className="px-3 py-1.5 grid grid-cols-2 border-b border-bg-border/50 last:border-0 hover:bg-bg-hover/10"
                >
                  <span className="text-text-primary/80 truncate flex items-center gap-1.5">
                    <FileText size={10} className="text-text-secondary/50 shrink-0" />
                    {doc.name}
                  </span>
                  <span className="text-text-secondary text-right">{doc.chunks}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  )
}
