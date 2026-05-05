import React, { useEffect, useState } from 'react'
import {
  CheckCircle,
  Clock,
  Loader2,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react'

import { decideTaskApproval, getDeck, getTask } from '../../api/client'
import type { DeckSpec, TaskStatus } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { createAndTrackTask, useTaskStore } from '../../stores/taskStore'
import { DeckEditorModal } from '../reports/DeckEditorModal'
import { ReportPreviewModal } from '../reports/ReportPreviewModal'

const TASK_TYPE_LABELS: Record<string, string> = {
  analyze_knowledge_base: 'Knowledge Base Analysis',
  generate_dashboard: 'Dashboard Generation',
  generate_deck: 'Deck Generation',
  generate_report: 'Report Generation',
  multi_agent_workflow: 'Multi-Agent Workflow',
  upload_documents: 'Document Upload',
  web_research: 'Web Research',
}

const STATUS_CONFIG: Record<
  TaskStatus,
  { label: string; icon: React.ReactNode; color: string; barColor: string }
> = {
  pending: {
    label: 'Pending',
    icon: <Clock size={13} className="animate-pulse text-text-secondary/70" />,
    color: 'text-text-secondary/70',
    barColor: 'bg-text-secondary/40',
  },
  running: {
    label: 'Running',
    icon: <Loader2 size={13} className="animate-spin text-accent-blue" />,
    color: 'text-accent-blue',
    barColor: 'bg-accent-blue',
  },
  waiting_approval: {
    label: 'Needs approval',
    icon: <ShieldAlert size={13} className="text-amber-300" />,
    color: 'text-amber-300',
    barColor: 'bg-amber-400',
  },
  completed: {
    label: 'Completed',
    icon: <CheckCircle size={13} className="text-accent-green" />,
    color: 'text-accent-green',
    barColor: 'bg-accent-green',
  },
  failed: {
    label: 'Failed',
    icon: <XCircle size={13} className="text-red-400" />,
    color: 'text-red-400',
    barColor: 'bg-red-400',
  },
}

interface TaskProgressCardProps {
  taskId: string
  taskType?: string
  sessionId?: string
}

function isRestartInterrupted(error: string | undefined): boolean {
  if (!error) return false
  return error.includes('服务已重启') || error.includes('鏈嶅姟宸查噸鍚')
}

export const TaskProgressCard: React.FC<TaskProgressCardProps> = ({
  taskId,
  taskType,
  sessionId,
}) => {
  const task = useTaskStore((s) => s.tasks[taskId])
  const startPolling = useTaskStore((s) => s.startPolling)
  const panels = useChatStore((s) => s.panels)
  const currentSessionId = useChatStore((s) => s.currentSessionId)
  const [reportPreviewOpen, setReportPreviewOpen] = useState(false)
  const [deckOpen, setDeckOpen] = useState(false)
  const [deckData, setDeckData] = useState<DeckSpec | null>(null)
  const [deckLoading, setDeckLoading] = useState(false)
  const [deckError, setDeckError] = useState<string | null>(null)
  const [approvalLoading, setApprovalLoading] = useState(false)

  useEffect(() => {
    if (task) return
    getTask(taskId)
      .then((data) => {
        useTaskStore.getState().addTask(data)
        if (data.status === 'pending' || data.status === 'running') {
          startPolling(taskId)
        }
      })
      .catch(() => {})
  }, [taskId, task, startPolling])

  const displayType = task?.task_type ?? taskType ?? 'Task'
  const label = TASK_TYPE_LABELS[displayType] ?? displayType
  const status: TaskStatus = task?.status ?? 'pending'
  const progress = task?.progress ?? 0
  const cfg = STATUS_CONFIG[status]
  const effectiveSessionId = sessionId ?? task?.session_id ?? currentSessionId ?? undefined
  const restartInterrupted = isRestartInterrupted(task?.error)
  const isTerminal = status === 'completed' || status === 'failed'

  const reportMarkdown =
    typeof task?.params?.report_markdown === 'string' ? task.params.report_markdown : ''
  const reportTitle =
    typeof task?.params?.report_title === 'string' ? task.params.report_title : 'Research Report'
  const reportArtifactId =
    typeof task?.params?.artifact_id === 'string' ? task.params.artifact_id : undefined
  const reportAnswerGroupId =
    typeof task?.params?.answer_group_id === 'string' ? task.params.answer_group_id : undefined
  const reportPanelId =
    typeof task?.params?.panel_id === 'string' ? task.params.panel_id : undefined

  const deckId = typeof task?.params?.deck_id === 'string' ? task.params.deck_id : ''
  const deckTitle =
    typeof task?.params?.deck_title === 'string' ? task.params.deck_title : 'Deck Draft'
  const approvalReason =
    typeof task?.params?.approval_reason === 'string' ? task.params.approval_reason : ''

  const handleRetry = async () => {
    if (!task) return
    try {
      await createAndTrackTask(task.task_type, task.params ?? {}, effectiveSessionId)
    } catch (error) {
      console.error('Task retry failed', error)
    }
  }

  const handleApprovalDecision = async (decision: 'approved' | 'rejected') => {
    if (!task || approvalLoading) return
    setApprovalLoading(true)
    try {
      const updated = await decideTaskApproval(task.task_id, { decision })
      useTaskStore.getState().addTask(updated)
      if (updated.status === 'pending' || updated.status === 'running') {
        startPolling(task.task_id)
      }
    } catch (error) {
      console.error('Task approval failed', error)
    } finally {
      setApprovalLoading(false)
    }
  }

  const handleOpenDeck = async () => {
    if (!deckId || deckLoading) return
    if (deckData && deckData.deck_id === deckId) {
      setDeckOpen(true)
      return
    }

    setDeckLoading(true)
    setDeckError(null)
    try {
      const deck = await getDeck(deckId)
      setDeckData(deck)
      setDeckOpen(true)
    } catch (error) {
      setDeckError((error as Error).message || 'Failed to open deck.')
    } finally {
      setDeckLoading(false)
    }
  }

  return (
    <div
      className="my-3 max-w-sm overflow-hidden rounded-xl border border-bg-border bg-bg-secondary/50 shadow-sm"
      data-testid="task-progress-card"
      data-task-id={taskId}
      data-task-type={displayType}
    >
      <div className="flex items-center gap-2.5 border-b border-bg-border/60 bg-bg-tertiary/30 px-4 py-2.5">
        {cfg.icon}
        <div className="min-w-0 flex-1">
          <span className="truncate text-xs font-semibold text-text-primary">{label}</span>
        </div>
        <span className={`text-[10px] font-medium ${cfg.color}`}>{cfg.label}</span>
      </div>

      <div className="px-4 pb-1 pt-3">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-[10px] text-text-secondary/60">Progress</span>
          <span className={`text-[10px] font-semibold ${cfg.color}`}>{progress}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-bg-tertiary">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${cfg.barColor} ${
              status === 'running' && progress < 100 ? 'animate-pulse' : ''
            }`}
            style={{ width: `${Math.min(100, progress)}%` }}
          />
        </div>
      </div>

      {status === 'waiting_approval' && (
        <div className="space-y-2 px-4 pb-3 pt-2">
          <p className="text-[11px] leading-relaxed text-amber-200">
            {approvalReason || 'This workflow is waiting for approval.'}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                void handleApprovalDecision('approved')
              }}
              disabled={approvalLoading}
              className="rounded-lg border border-accent-green/30 bg-accent-green/10 px-2.5 py-1 text-[11px] text-accent-green disabled:opacity-50"
            >
              {approvalLoading ? 'Working...' : 'Approve'}
            </button>
            <button
              type="button"
              onClick={() => {
                void handleApprovalDecision('rejected')
              }}
              disabled={approvalLoading}
              className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-2.5 py-1 text-[11px] text-accent-red disabled:opacity-50"
            >
              {approvalLoading ? 'Working...' : 'Reject'}
            </button>
          </div>
        </div>
      )}

      {task?.result && status === 'completed' && (
        <div className="px-4 pb-3 pt-2">
          <p className="text-[11px] leading-relaxed text-text-primary/80">{task.result}</p>
          {reportMarkdown && (
            <button
              type="button"
              onClick={() => setReportPreviewOpen(true)}
              className="mt-2 inline-flex items-center gap-1 text-[11px] text-accent-blue transition-colors hover:text-accent-blue/80"
            >
              Open report
            </button>
          )}
          {deckId && (
            <button
              type="button"
              onClick={() => {
                void handleOpenDeck()
              }}
              disabled={deckLoading}
              className="ml-3 mt-2 inline-flex items-center gap-1 text-[11px] text-accent-blue transition-colors hover:text-accent-blue/80 disabled:opacity-50"
            >
              {deckLoading ? 'Opening...' : `Open deck${deckTitle ? `: ${deckTitle}` : ''}`}
            </button>
          )}
          {deckError && (
            <p className="mt-2 text-[11px] leading-relaxed text-red-400/80">{deckError}</p>
          )}
        </div>
      )}

      {task?.error && status === 'failed' && (
        <div className="space-y-2 px-4 pb-3 pt-2">
          {restartInterrupted && (
            <div className="rounded-lg border border-amber-400/20 bg-amber-400/10 px-2.5 py-2">
              <p className="text-[11px] leading-relaxed text-amber-300">
                The task was interrupted by a service restart and needs to be relaunched.
              </p>
            </div>
          )}
          <p className="text-[11px] leading-relaxed text-red-400/80">{task.error}</p>
          <button
            onClick={handleRetry}
            className="flex items-center gap-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
          >
            <RefreshCw size={10} /> {restartInterrupted ? 'Relaunch task' : 'Retry'}
          </button>
        </div>
      )}

      {!isTerminal && status !== 'waiting_approval' && (
        <div className="px-4 pb-2">
          <p className="truncate font-mono text-[9px] text-text-secondary/30">{taskId}</p>
        </div>
      )}

      {reportMarkdown && (
        <ReportPreviewModal
          open={reportPreviewOpen}
          onClose={() => setReportPreviewOpen(false)}
          markdown={reportMarkdown}
          title={reportTitle}
          sessionId={effectiveSessionId ?? ''}
          artifactId={reportArtifactId}
          answerGroupId={reportAnswerGroupId}
          panelId={reportPanelId}
        />
      )}

      {deckData && (
        <DeckEditorModal
          open={deckOpen}
          onClose={() => setDeckOpen(false)}
          deck={deckData}
          panels={panels}
          onDeckChange={setDeckData}
        />
      )}
    </div>
  )
}
