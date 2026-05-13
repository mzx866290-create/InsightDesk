import React from 'react'

import type { TaskRecord } from '../../api/client'

export interface DocumentUploadProgressPanelProps {
  uploadTaskId: string
  uploadTask?: TaskRecord
  uploadProgress: number
}

export const DocumentUploadProgressPanel: React.FC<DocumentUploadProgressPanelProps> = ({
  uploadTaskId,
  uploadTask,
  uploadProgress,
}) => (
  <div data-testid="settings-documents-upload-progress" className="rounded-lg border border-bg-border bg-bg-tertiary/60 p-3">
    <div className="flex items-center justify-between text-xs text-text-secondary">
      <span data-testid="settings-documents-upload-status">
        上传任务进度
        {uploadTask
          ? `（状态：${uploadTask.status === 'completed' ? '已完成' : uploadTask.status === 'failed' ? '失败' : '处理中'}）`
          : '（等待任务状态）'}
      </span>
      <span data-testid="settings-documents-upload-percent" className="text-text-primary">{uploadProgress}%</span>
    </div>
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-bg-border/80">
      <div
        className={`h-full transition-all duration-300 ${
          uploadTask?.status === 'failed'
            ? 'bg-accent-red'
            : uploadTask?.status === 'completed'
              ? 'bg-accent-green'
              : 'bg-accent-blue'
        }`}
        style={{ width: `${uploadProgress}%` }}
      />
    </div>
    <p data-testid="settings-documents-upload-task-id" className="mt-1.5 text-[11px] text-text-secondary/80">
      任务 ID：{uploadTaskId}
    </p>
  </div>
)
