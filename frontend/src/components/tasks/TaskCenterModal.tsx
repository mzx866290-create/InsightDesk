import React, { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Clock3, Loader2, RefreshCw, XCircle } from 'lucide-react'

import { Modal } from '../ui/Modal'
import { useTaskStore, createAndTrackTask } from '../../stores/taskStore'
import { useChatStore } from '../../stores/chatStore'
import type { TaskRecord, TaskStatus } from '../../api/client'

interface TaskCenterModalProps {
  open: boolean
  onClose: () => void
}

const TASK_TYPE_LABELS: Record<string, string> = {
  analyze_knowledge_base: '分析知识库',
  generate_dashboard: '生成仪表盘',
  generate_report: '生成报告',
  upload_documents: '导入知识库',
  promote_attachment_to_kb: '附件入库',
}

const STATUS_META: Record<
  TaskStatus,
  {
    label: string
    badgeClass: string
    icon: React.ReactNode
  }
> = {
  pending: {
    label: '等待中',
    badgeClass: 'border-bg-border text-text-secondary',
    icon: <Clock3 size={13} className="text-text-secondary/70" />,
  },
  running: {
    label: '执行中',
    badgeClass: 'border-accent-blue/30 text-accent-blue',
    icon: <Loader2 size={13} className="animate-spin text-accent-blue" />,
  },
  completed: {
    label: '已完成',
    badgeClass: 'border-accent-green/30 text-accent-green',
    icon: <CheckCircle2 size={13} className="text-accent-green" />,
  },
  failed: {
    label: '失败',
    badgeClass: 'border-accent-red/30 text-accent-red',
    icon: <XCircle size={13} className="text-accent-red" />,
  },
}

function taskTypeLabel(taskType: string): string {
  return TASK_TYPE_LABELS[taskType] ?? taskType
}

function taskContextLabel(task: TaskRecord): string {
  const params = task.params ?? {}

  if (task.task_type === 'promote_attachment_to_kb') {
    const attachmentName =
      typeof params.attachment_name === 'string' ? params.attachment_name.trim() : ''
    const vectorStorePath =
      typeof params.vector_store_path === 'string' ? params.vector_store_path.trim() : ''

    if (attachmentName && vectorStorePath) {
      return `${attachmentName} -> ${vectorStorePath}`
    }
    if (attachmentName) {
      return attachmentName
    }
    if (vectorStorePath) {
      return `目标知识库：${vectorStorePath}`
    }
  }

  if (task.task_type === 'upload_documents') {
    const fileNames = Array.isArray(params.file_names)
      ? params.file_names.filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
      : []
    if (fileNames.length > 0) {
      return fileNames.slice(0, 2).join('、')
    }
  }

  return ''
}

function formatTaskTime(timestamp: number | undefined): string {
  if (!timestamp) return '未知时间'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp * 1000))
}

function isRestartInterruptedTask(task: TaskRecord): boolean {
  return typeof task.error === 'string' && task.error.includes('服务已重启，任务未能继续执行')
}

export const TaskCenterModal: React.FC<TaskCenterModalProps> = ({ open, onClose }) => {
  const tasksMap = useTaskStore((s) => s.tasks)
  const syncRecentTasks = useTaskStore((s) => s.syncRecentTasks)
  const currentSessionId = useChatStore((s) => s.currentSessionId)
  const [refreshing, setRefreshing] = useState(false)
  const [retryingTaskId, setRetryingTaskId] = useState<string | null>(null)
  const [error, setError] = useState('')

  const tasks = useMemo(
    () =>
      Object.values(tasksMap).sort((a, b) => {
        const timeA = a.updated_at ?? a.created_at
        const timeB = b.updated_at ?? b.created_at
        return timeB - timeA
      }),
    [tasksMap],
  )

  const activeTaskCount = tasks.filter(
    (task) => task.status === 'pending' || task.status === 'running',
  ).length

  const refreshTasks = async () => {
    setRefreshing(true)
    setError('')
    try {
      await syncRecentTasks(30)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    if (!open) return
    void refreshTasks()
  }, [open])

  const handleRetry = async (task: TaskRecord) => {
    setRetryingTaskId(task.task_id)
    setError('')
    try {
      await createAndTrackTask(
        task.task_type,
        task.params ?? {},
        task.session_id ?? currentSessionId ?? undefined,
      )
      await syncRecentTasks(30)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setRetryingTaskId(null)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="任务中心" width="max-w-4xl">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-bg-border bg-bg-primary/40 px-4 py-3">
          <div className="space-y-1">
            <p className="text-sm font-medium text-text-primary">最近任务与后台执行状态</p>
            <p className="text-xs text-text-secondary">
              当前活跃任务 {activeTaskCount} 个，共展示最近 {Math.min(tasks.length, 30)} 条记录。
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              void refreshTasks()
            }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
          >
            {refreshing ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <RefreshCw size={13} />
            )}
            刷新
          </button>
        </div>

        {error && (
          <div className="rounded-xl border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-sm text-accent-red">
            {error}
          </div>
        )}

        {tasks.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-bg-border bg-bg-primary/30 px-4 py-8 text-center text-sm text-text-secondary">
            当前还没有可显示的任务记录。
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => {
              const statusMeta = STATUS_META[task.status]
              const restartInterrupted = isRestartInterruptedTask(task)
              const contextLabel = taskContextLabel(task)
              return (
                <div
                  key={task.task_id}
                  className="rounded-2xl border border-bg-border bg-bg-primary/50 px-4 py-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {statusMeta.icon}
                        <p className="text-sm font-medium text-text-primary">
                          {taskTypeLabel(task.task_type)}
                        </p>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[11px] ${statusMeta.badgeClass}`}
                        >
                          {statusMeta.label}
                        </span>
                        {restartInterrupted && (
                          <span className="rounded-full border border-amber-400/30 px-2 py-0.5 text-[11px] text-amber-300">
                            重启中断
                          </span>
                        )}
                      </div>

                       <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                         <span>创建于 {formatTaskTime(task.created_at)}</span>
                         <span>更新于 {formatTaskTime(task.updated_at ?? task.created_at)}</span>
                         <span className="font-mono text-text-secondary/70">{task.task_id}</span>
                       </div>

                       {contextLabel && (
                         <p className="mt-2 text-xs text-text-secondary">
                           {contextLabel}
                         </p>
                       )}
                     </div>

                    {task.status === 'failed' && (
                      <button
                        type="button"
                        onClick={() => {
                          void handleRetry(task)
                        }}
                        disabled={retryingTaskId === task.task_id}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
                      >
                        {retryingTaskId === task.task_id ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <RefreshCw size={12} />
                        )}
                        {restartInterrupted ? '重新发起' : '重试'}
                      </button>
                    )}
                  </div>

                  <div className="mt-3">
                    <div className="mb-1 flex items-center justify-between text-[11px] text-text-secondary">
                      <span>进度</span>
                      <span>{task.progress}%</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-bg-tertiary">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          task.status === 'completed'
                            ? 'bg-accent-green'
                            : task.status === 'failed'
                              ? 'bg-accent-red'
                              : task.status === 'running'
                                ? 'bg-accent-blue'
                                : 'bg-text-secondary/40'
                        }`}
                        style={{ width: `${Math.min(100, task.progress)}%` }}
                      />
                    </div>
                  </div>

                  {task.result && (
                    <div className="mt-3 rounded-xl border border-bg-border bg-bg-secondary/40 px-3 py-2">
                      <p className="text-[11px] font-medium text-text-primary">结果摘要</p>
                      <p className="mt-1 text-xs leading-5 text-text-secondary">{task.result}</p>
                    </div>
                  )}

                  {task.error && (
                    <div className="mt-3 rounded-xl border border-accent-red/20 bg-accent-red/10 px-3 py-2">
                      <p className="text-[11px] font-medium text-accent-red">失败原因</p>
                      <p className="mt-1 text-xs leading-5 text-text-secondary">{task.error}</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Modal>
  )
}
