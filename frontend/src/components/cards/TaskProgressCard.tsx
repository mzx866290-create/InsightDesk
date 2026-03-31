import React, { useEffect } from 'react'
import { Loader2, CheckCircle, XCircle, Clock, RefreshCw } from 'lucide-react'
import { useTaskStore, createAndTrackTask } from '../../stores/taskStore'
import type { TaskStatus } from '../../stores/taskStore'

const TASK_TYPE_LABELS: Record<string, string> = {
  analyze_knowledge_base: '分析知识库',
  generate_report: '生成报告',
}

const STATUS_CONFIG: Record<
  TaskStatus,
  { label: string; icon: React.ReactNode; color: string; barColor: string }
> = {
  pending: {
    label: '等待中',
    icon: <Clock size={13} className="text-text-secondary/70 animate-pulse" />,
    color: 'text-text-secondary/70',
    barColor: 'bg-text-secondary/40',
  },
  running: {
    label: '执行中',
    icon: <Loader2 size={13} className="text-accent-blue animate-spin" />,
    color: 'text-accent-blue',
    barColor: 'bg-accent-blue',
  },
  completed: {
    label: '已完成',
    icon: <CheckCircle size={13} className="text-accent-green" />,
    color: 'text-accent-green',
    barColor: 'bg-accent-green',
  },
  failed: {
    label: '失败',
    icon: <XCircle size={13} className="text-red-400" />,
    color: 'text-red-400',
    barColor: 'bg-red-400',
  },
}

interface TaskProgressCardProps {
  taskId: string
  /** Initial task type label, shown before first poll */
  taskType?: string
  sessionId?: string
}

export const TaskProgressCard: React.FC<TaskProgressCardProps> = ({
  taskId,
  taskType,
  sessionId,
}) => {
  const task = useTaskStore((s) => s.tasks[taskId])
  const startPolling = useTaskStore((s) => s.startPolling)

  // If the task is not yet in the store (e.g. message loaded from history),
  // attempt a single fetch to populate it and start polling if still active
  useEffect(() => {
    if (!task) {
      fetch(`/api/tasks/${taskId}`)
        .then((r) => r.json())
        .then((data) => {
          useTaskStore.getState().addTask(data)
          if (data.status === 'pending' || data.status === 'running') {
            startPolling(taskId)
          }
        })
        .catch(() => {})
    }
  }, [taskId, task, startPolling])

  const displayType = task?.task_type ?? taskType ?? 'task'
  const label = TASK_TYPE_LABELS[displayType] ?? displayType
  const status: TaskStatus = task?.status ?? 'pending'
  const progress = task?.progress ?? 0
  const cfg = STATUS_CONFIG[status]

  const isTerminal = status === 'completed' || status === 'failed'

  const handleRetry = async () => {
    if (!task) return
    try {
      await createAndTrackTask(task.task_type, task.params ?? {}, sessionId)
    } catch (e) {
      console.error('Retry failed', e)
    }
  }

  return (
    <div className="my-3 rounded-xl border border-bg-border bg-bg-secondary/50 overflow-hidden shadow-sm max-w-sm">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-4 py-2.5 border-b border-bg-border/60 bg-bg-tertiary/30">
        {cfg.icon}
        <div className="flex-1 min-w-0">
          <span className="text-xs font-semibold text-text-primary truncate">{label}</span>
        </div>
        <span className={`text-[10px] font-medium ${cfg.color}`}>{cfg.label}</span>
      </div>

      {/* Progress bar */}
      <div className="px-4 pt-3 pb-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] text-text-secondary/60">进度</span>
          <span className={`text-[10px] font-semibold ${cfg.color}`}>{progress}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${cfg.barColor} ${
              status === 'running' && progress < 100 ? 'animate-pulse' : ''
            }`}
            style={{ width: `${Math.min(100, progress)}%` }}
          />
        </div>
      </div>

      {/* Result / error */}
      {task?.result && status === 'completed' && (
        <div className="px-4 pb-3 pt-2">
          <p className="text-[11px] text-text-primary/80 leading-relaxed">{task.result}</p>
        </div>
      )}
      {task?.error && status === 'failed' && (
        <div className="px-4 pb-3 pt-2 space-y-2">
          <p className="text-[11px] text-red-400/80 leading-relaxed">{task.error}</p>
          <button
            onClick={handleRetry}
            className="flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary transition-colors"
          >
            <RefreshCw size={10} /> 重试
          </button>
        </div>
      )}

      {/* Task ID (subtle) */}
      {!isTerminal && (
        <div className="px-4 pb-2">
          <p className="text-[9px] text-text-secondary/30 truncate font-mono">{taskId}</p>
        </div>
      )}
    </div>
  )
}
