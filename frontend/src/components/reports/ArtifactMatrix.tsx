import React, { useEffect, useState } from 'react'
import { Download, FileText, Layers3, Loader2, RefreshCw } from 'lucide-react'

import {
  exportArtifact,
  getArtifact,
  getDeck,
  getSessionArtifacts,
} from '../../api/client'
import type {
  ArtifactExportFormat,
  ArtifactRecord,
  DeckSpec,
  ReportArtifactContent,
} from '../../api/client'

interface ReportArtifactOpenPayload {
  artifactId: string
  title: string
  markdown: string
  answerGroupId?: string
  panelId?: string
}

interface ArtifactMatrixProps {
  sessionId: string
  activeArtifactId?: string
  onOpenReport: (payload: ReportArtifactOpenPayload) => void
  onOpenDeck: (deck: DeckSpec) => void
}

function artifactTypeLabel(type: ArtifactRecord['artifact_type']): string {
  return type === 'deck' ? 'Deck' : '报告'
}

function formatArtifactTime(timestamp: number): string {
  if (!timestamp) return '未知时间'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp * 1000))
}

function inferFilename(title: string, format: ArtifactExportFormat): string {
  const safe = (title || 'artifact').trim().replace(/[\\/:*?"<>|]+/g, '_')
  return `${safe || 'artifact'}.${format}`
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export const ArtifactMatrix: React.FC<ArtifactMatrixProps> = ({
  sessionId,
  activeArtifactId,
  onOpenReport,
  onOpenDeck,
}) => {
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [openingArtifactId, setOpeningArtifactId] = useState('')
  const [exportingKey, setExportingKey] = useState('')

  const refreshArtifacts = async () => {
    if (!sessionId.trim()) {
      setArtifacts([])
      return
    }
    setLoading(true)
    setError('')
    try {
      const nextArtifacts = await getSessionArtifacts(sessionId)
      setArtifacts(nextArtifacts)
    } catch (refreshError) {
      setError((refreshError as Error).message || '加载交付物失败。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refreshArtifacts()
  }, [sessionId, activeArtifactId])

  const handleOpen = async (artifact: ArtifactRecord) => {
    if (!artifact.artifact_id || openingArtifactId) return
    setOpeningArtifactId(artifact.artifact_id)
    setError('')
    try {
      const fullArtifact = await getArtifact(artifact.artifact_id)
      if (fullArtifact.artifact_type === 'report') {
        const content = fullArtifact.content as ReportArtifactContent
        onOpenReport({
          artifactId: fullArtifact.artifact_id,
          title: fullArtifact.title,
          markdown: content.markdown ?? '',
          answerGroupId: content.answer_group_id ?? undefined,
          panelId: content.panel_id ?? undefined,
        })
        return
      }

      const deckId =
        'deck_id' in fullArtifact.content && typeof fullArtifact.content.deck_id === 'string'
          ? fullArtifact.content.deck_id
          : fullArtifact.linked_resource_id ?? ''
      if (!deckId) {
        throw new Error('当前 Deck 交付物缺少 deck_id。')
      }
      const deck = await getDeck(deckId)
      onOpenDeck(deck)
    } catch (openError) {
      setError((openError as Error).message || '打开交付物失败。')
    } finally {
      setOpeningArtifactId('')
    }
  }

  const handleExport = async (
    artifact: ArtifactRecord,
    format: ArtifactExportFormat,
  ) => {
    const key = `${artifact.artifact_id}:${format}`
    if (!artifact.artifact_id || exportingKey) return
    setExportingKey(key)
    setError('')
    try {
      const blob = await exportArtifact(artifact.artifact_id, format)
      downloadBlob(blob, inferFilename(artifact.title, format))
    } catch (exportError) {
      setError((exportError as Error).message || '导出交付物失败。')
    } finally {
      setExportingKey('')
    }
  }

  return (
    <section className="rounded-2xl border border-bg-border bg-bg-secondary/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-text-primary">交付物矩阵</div>
          <div className="mt-1 text-xs text-text-secondary">
            当前会话已生成的报告与 Deck，会持续复用同一套 artifact 入口。
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            void refreshArtifacts()
          }}
          className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          刷新
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-accent-red/20 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
          {error}
        </div>
      )}

      {artifacts.length === 0 && !loading ? (
        <div className="mt-3 rounded-xl border border-dashed border-bg-border px-3 py-5 text-center text-xs text-text-secondary">
          当前会话还没有已持久化的交付物。
        </div>
      ) : (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {artifacts.map((artifact) => {
            const isActive = activeArtifactId === artifact.artifact_id
            const opening = openingArtifactId === artifact.artifact_id
            return (
              <article
                key={artifact.artifact_id}
                className={`rounded-2xl border px-3 py-3 ${
                  isActive
                    ? 'border-accent-blue/45 bg-accent-blue/8'
                    : 'border-bg-border bg-bg-primary/50'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      {artifact.artifact_type === 'deck' ? (
                        <Layers3 size={14} className="text-accent-blue" />
                      ) : (
                        <FileText size={14} className="text-accent-green" />
                      )}
                      <span className="text-xs font-medium text-text-primary">
                        {artifactTypeLabel(artifact.artifact_type)}
                      </span>
                      {isActive && (
                        <span className="rounded-full bg-accent-blue/12 px-2 py-0.5 text-[10px] text-accent-blue">
                          当前
                        </span>
                      )}
                    </div>
                    <div className="mt-2 truncate text-sm font-semibold text-text-primary">
                      {artifact.title}
                    </div>
                    <div className="mt-1 text-[11px] text-text-secondary">
                      更新于 {formatArtifactTime(artifact.updated_at)}
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      void handleOpen(artifact)
                    }}
                    disabled={opening}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
                  >
                    {opening ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : artifact.artifact_type === 'deck' ? (
                      <Layers3 size={12} />
                    ) : (
                      <FileText size={12} />
                    )}
                    打开
                  </button>

                  {artifact.available_formats.map((format) => {
                    const key = `${artifact.artifact_id}:${format}`
                    const exporting = exportingKey === key
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => {
                          void handleExport(artifact, format)
                        }}
                        disabled={exporting}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
                      >
                        {exporting ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Download size={12} />
                        )}
                        导出 {format.toUpperCase()}
                      </button>
                    )
                  })}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
