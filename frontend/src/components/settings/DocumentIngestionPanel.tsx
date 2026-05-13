import React, { useCallback, useState } from 'react'
import { AlertCircle, CheckCircle, Database, Trash2 } from 'lucide-react'
import { getDocStats, uploadDocuments, type DocStats } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'
import { Button } from '../ui/Button'
import { DocumentStatsPanel } from './DocumentStatsPanel'
import { DocumentUploadProgressPanel } from './DocumentUploadProgressPanel'
import { DocumentUploadZone } from './DocumentUploadZone'
import type { DeleteKnowledgeBaseResult } from './kbMonitorModel'

interface DocumentIngestionPanelProps {
  deletingKnowledgeBase: boolean
  deleteKnowledgeBaseConfirming: boolean
  onDeleteKnowledgeBase: () => Promise<DeleteKnowledgeBaseResult>
}

export const DocumentIngestionPanel: React.FC<DocumentIngestionPanelProps> = ({
  deletingKnowledgeBase,
  deleteKnowledgeBaseConfirming,
  onDeleteKnowledgeBase,
}) => {
  const [uploading, setUploading] = useState(false)
  const [uploadTaskId, setUploadTaskId] = useState<string | null>(null)
  const [uploadResult, setUploadResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [stats, setStats] = useState<DocStats | null>(null)
  const [loadingStats, setLoadingStats] = useState(false)

  const addTask = useTaskStore((state) => state.addTask)
  const startPolling = useTaskStore((state) => state.startPolling)
  const tasks = useTaskStore((state) => state.tasks)

  const uploadTask = uploadTaskId ? tasks[uploadTaskId] : undefined
  const uploadProgress = Math.max(0, Math.min(100, uploadTask?.progress ?? 0))

  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadTaskId(null)
    setUploadResult(null)
    try {
      const result = await uploadDocuments(Array.from(files))
      addTask({
        task_id: result.task_id,
        task_type: result.task_type,
        status: result.status as 'pending' | 'running' | 'completed' | 'failed',
        progress: 0,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
      })
      startPolling(result.task_id)
      setUploadTaskId(result.task_id)
      setUploadResult({ ok: true, message: `${result.message}，任务 ID: ${result.task_id}` })
    } catch (error) {
      setUploadResult({ ok: false, message: (error as Error).message })
    } finally {
      setUploading(false)
    }
  }, [addTask, startPolling])

  const loadStats = useCallback(async () => {
    setLoadingStats(true)
    try {
      const nextStats = await getDocStats()
      setStats(nextStats)
    } catch (error) {
      setStats({ status: `获取失败：${(error as Error).message}` })
    } finally {
      setLoadingStats(false)
    }
  }, [])

  const handleDeleteKnowledgeBase = useCallback(async () => {
    const result = await onDeleteKnowledgeBase()
    if (result === 'deleted') {
      setStats(null)
    }
  }, [onDeleteKnowledgeBase])

  return (
    <div className="space-y-4" data-testid="settings-documents-panel">
      <DocumentUploadZone
        uploading={uploading}
        onUpload={(files) => {
          void handleUpload(files)
        }}
      />

      {uploadResult && (
        <div
          data-testid="settings-documents-upload-result"
          data-status={uploadResult.ok ? 'success' : 'error'}
          className={`flex items-start gap-2.5 p-3 rounded-lg text-sm ${
            uploadResult.ok
              ? 'bg-accent-green/10 border border-accent-green/30 text-accent-green'
              : 'bg-accent-red/10 border border-accent-red/30 text-accent-red'
          }`}
        >
          {uploadResult.ok ? (
            <CheckCircle size={15} className="shrink-0 mt-0.5" />
          ) : (
            <AlertCircle size={15} className="shrink-0 mt-0.5" />
          )}
          {uploadResult.message}
        </div>
      )}

      {uploadTaskId && (
        <DocumentUploadProgressPanel
          uploadTaskId={uploadTaskId}
          uploadTask={uploadTask}
          uploadProgress={uploadProgress}
        />
      )}

      <div className="flex gap-2 flex-wrap">
        <Button
          data-testid="settings-documents-stats-refresh"
          variant="ghost"
          onClick={loadStats}
          loading={loadingStats}
          className="gap-2"
        >
          <Database size={13} />
          查看统计
        </Button>
        <Button
          data-testid="settings-documents-delete-kb"
          variant="ghost"
          onClick={() => {
            void handleDeleteKnowledgeBase()
          }}
          loading={deletingKnowledgeBase}
          className={`gap-2 ${deleteKnowledgeBaseConfirming ? 'text-accent-red border-accent-red/40' : ''}`}
        >
          <Trash2 size={13} />
          {deleteKnowledgeBaseConfirming ? '再次点击确认删除' : '删除知识库'}
        </Button>
      </div>

      {stats && <DocumentStatsPanel stats={stats} />}
    </div>
  )
}
