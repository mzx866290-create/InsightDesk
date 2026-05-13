import React from 'react'
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react'

import type { TaskRecord } from '../../api/client'

interface KnowledgeBaseUploadTaskProgressProps {
  task: TaskRecord | null
}

function getTaskStatusColor(status: TaskRecord['status']): string {
  if (status === 'completed') return 'text-accent-green'
  if (status === 'failed') return 'text-accent-red'
  return 'text-accent-blue'
}

function getTaskStatusLabel(task: TaskRecord): string {
  if (task.status === 'completed') return '上传并索引完成！'
  if (task.status === 'failed') return `失败: ${task.error || '未知错误'}`
  if (task.status === 'running') return '正在处理文档...'
  return '等待处理...'
}

export const KnowledgeBaseUploadTaskProgress: React.FC<KnowledgeBaseUploadTaskProgressProps> = ({
  task,
}) => {
  if (!task) return null

  const taskProgress = Math.round(task.progress * 100)
  const isProcessing = task.status === 'pending' || task.status === 'running'

  return (
    <div
      data-testid="settings-kb-upload-progress"
      className="px-4 py-3 bg-bg-tertiary rounded-xl border border-bg-border space-y-2"
    >
      <div className="flex items-center gap-2">
        {task.status === 'completed' && <CheckCircle size={14} className="text-accent-green" />}
        {task.status === 'failed' && <AlertCircle size={14} className="text-accent-red" />}
        {isProcessing && <Loader2 size={14} className="animate-spin text-accent-blue" />}
        <span data-testid="settings-kb-upload-status" className={`text-sm font-medium ${getTaskStatusColor(task.status)}`}>
          {getTaskStatusLabel(task)}
        </span>
        {task.status !== 'failed' && task.status !== 'completed' && (
          <span data-testid="settings-kb-upload-percent" className="text-xs text-text-muted ml-auto">{taskProgress}%</span>
        )}
      </div>
      {isProcessing && (
        <div className="w-full bg-bg-border rounded-full h-1.5">
          <div
            className="bg-accent-blue h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${taskProgress}%` }}
          />
        </div>
      )}
      {task.result && (
        <p data-testid="settings-kb-upload-result" className="text-xs text-text-secondary">{task.result}</p>
      )}
    </div>
  )
}
