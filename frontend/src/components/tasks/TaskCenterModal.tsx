import React, { useEffect, useMemo, useState } from 'react'
import {
  CheckCircle2,
  Clock3,
  FileText,
  Layers3,
  Loader2,
  RefreshCw,
  Share2,
  XCircle,
} from 'lucide-react'

import { createDeckShareLink, getDeck } from '../../api/client'
import type { DeckSpec, TaskRecord, TaskStatus } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { createAndTrackTask, useTaskStore } from '../../stores/taskStore'
import { DeckEditorModal } from '../reports/DeckEditorModal'
import { ReportPreviewModal } from '../reports/ReportPreviewModal'
import { Modal } from '../ui/Modal'

interface TaskCenterModalProps {
  open: boolean
  onClose: () => void
}

const TASK_TYPE_LABELS: Record<string, string> = {
  analyze_knowledge_base: '知识库分析',
  generate_dashboard: '仪表盘生成',
  generate_deck: '演示稿生成',
  generate_report: '报告生成',
  promote_attachment_to_kb: '附件入库',
  upload_documents: '文档导入',
  web_research: '联网研究',
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
  return typeof task.error === 'string' && task.error.includes('服务已重启')
}

function taskContextLabel(task: TaskRecord): string {
  const params = task.params ?? {}

  if (task.task_type === 'generate_report') {
    const reportTitle =
      typeof params.report_title === 'string' ? params.report_title.trim() : ''
    if (reportTitle) return reportTitle
  }

  if (task.task_type === 'generate_deck') {
    const deckTitle = typeof params.deck_title === 'string' ? params.deck_title.trim() : ''
    if (deckTitle) return deckTitle
    const slideCount =
      typeof params.target_slide_count === 'number'
        ? params.target_slide_count
        : typeof params.target_slide_count === 'string'
          ? Number(params.target_slide_count)
          : 0
    if (slideCount > 0) return `${slideCount} 页演示稿`
  }

  if (task.task_type === 'promote_attachment_to_kb') {
    const attachmentName =
      typeof params.attachment_name === 'string' ? params.attachment_name.trim() : ''
    const vectorStorePath =
      typeof params.vector_store_path === 'string' ? params.vector_store_path.trim() : ''
    if (attachmentName && vectorStorePath) {
      return `${attachmentName} -> ${vectorStorePath}`
    }
    if (attachmentName) return attachmentName
    if (vectorStorePath) return `目标知识库：${vectorStorePath}`
  }

  if (task.task_type === 'upload_documents') {
    const fileNames = Array.isArray(params.file_names)
      ? params.file_names.filter(
          (value): value is string => typeof value === 'string' && value.trim().length > 0,
        )
      : []
    if (fileNames.length > 0) return fileNames.slice(0, 2).join('、')
  }

  if (task.task_type === 'web_research') {
    const query = typeof params.query === 'string' ? params.query.trim() : ''
    const provider = typeof params.provider === 'string' ? params.provider.trim() : ''
    if (query && provider) return `${query} (${provider})`
    if (query) return query
  }

  return ''
}

export const TaskCenterModal: React.FC<TaskCenterModalProps> = ({ open, onClose }) => {
  const tasksMap = useTaskStore((s) => s.tasks)
  const syncRecentTasks = useTaskStore((s) => s.syncRecentTasks)
  const currentSessionId = useChatStore((s) => s.currentSessionId)
  const panels = useChatStore((s) => s.panels)

  const [refreshing, setRefreshing] = useState(false)
  const [retryingTaskId, setRetryingTaskId] = useState<string | null>(null)
  const [deckLoadingTaskId, setDeckLoadingTaskId] = useState<string | null>(null)
  const [sharingDeckTaskId, setSharingDeckTaskId] = useState<string | null>(null)
  const [copiedDeckTaskId, setCopiedDeckTaskId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [deckOpen, setDeckOpen] = useState(false)
  const [deckData, setDeckData] = useState<DeckSpec | null>(null)
  const [reportPreview, setReportPreview] = useState<{
    markdown: string
    title: string
    sessionId: string
    artifactId?: string
    answerGroupId?: string
    panelId?: string
  } | null>(null)

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

  useEffect(() => {
    if (!open) return
    void refreshTasks()
  }, [open])

  useEffect(() => {
    if (!copiedDeckTaskId) return
    const timer = window.setTimeout(() => setCopiedDeckTaskId(null), 2200)
    return () => window.clearTimeout(timer)
  }, [copiedDeckTaskId])

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

  const handleOpenDeck = async (task: TaskRecord) => {
    const deckId = typeof task.params?.deck_id === 'string' ? task.params.deck_id.trim() : ''
    if (!deckId) {
      setError('当前任务没有可打开的 Deck。')
      return
    }

    setDeckLoadingTaskId(task.task_id)
    setError('')
    try {
      const deck = await getDeck(deckId)
      setDeckData(deck)
      setDeckOpen(true)
    } catch (err) {
      setError((err as Error).message || '打开 Deck 失败。')
    } finally {
      setDeckLoadingTaskId(null)
    }
  }

  const handleShareDeck = async (task: TaskRecord) => {
    const deckId = typeof task.params?.deck_id === 'string' ? task.params.deck_id.trim() : ''
    if (!deckId) {
      setError('当前任务没有可分享的 Deck。')
      return
    }

    setSharingDeckTaskId(task.task_id)
    setError('')
    try {
      const payload = await createDeckShareLink(deckId)
      let copied = false
      try {
        await navigator.clipboard.writeText(payload.share_url)
        copied = true
      } catch {
        copied = false
      }
      window.open(payload.share_url, '_blank', 'noopener,noreferrer')
      if (copied) {
        setCopiedDeckTaskId(task.task_id)
      } else {
        setError('分享页已打开，但复制链接失败。')
      }
    } catch (err) {
      setError((err as Error).message || '创建 Deck 分享链接失败。')
    } finally {
      setSharingDeckTaskId(null)
    }
  }

  return (
    <>
      <Modal open={open} onClose={onClose} title="任务中心" width="max-w-4xl">
        <div className="space-y-4" data-testid="task-center-modal">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-bg-border bg-bg-primary/40 px-4 py-3">
            <div className="space-y-1">
              <p className="text-sm font-medium text-text-primary">最近任务与后台执行状态</p>
              <p className="text-xs text-text-secondary">
                当前活跃任务 {activeTaskCount} 个，共显示最近 {Math.min(tasks.length, 30)} 条记录。
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                void refreshTasks()
              }}
              data-testid="task-center-refresh"
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
                const reportMarkdown =
                  typeof task.params?.report_markdown === 'string' ? task.params.report_markdown : ''
                const reportTitle =
                  typeof task.params?.report_title === 'string' ? task.params.report_title : '研究报告'
                const reportArtifactId =
                  typeof task.params?.artifact_id === 'string' ? task.params.artifact_id : undefined
                const reportAnswerGroupId =
                  typeof task.params?.answer_group_id === 'string'
                    ? task.params.answer_group_id
                    : undefined
                const reportPanelId =
                  typeof task.params?.panel_id === 'string' ? task.params.panel_id : undefined
                const deckId =
                  typeof task.params?.deck_id === 'string' ? task.params.deck_id.trim() : ''
                const deckTitle =
                  typeof task.params?.deck_title === 'string' ? task.params.deck_title : '演示稿草稿'
                const canOpenReport = task.status === 'completed' && Boolean(reportMarkdown)
                const canOpenDeck = task.status === 'completed' && Boolean(deckId)

                return (
                  <div
                    key={task.task_id}
                    data-testid="task-center-task"
                    data-task-id={task.task_id}
                    data-task-type={task.task_type}
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
                          <p className="mt-2 text-xs text-text-secondary">{contextLabel}</p>
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

                    {(canOpenReport || canOpenDeck) && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {canOpenReport && (
                          <button
                            type="button"
                            onClick={() =>
                              setReportPreview({
                                markdown: reportMarkdown,
                                title: reportTitle,
                                sessionId: task.session_id ?? currentSessionId ?? '',
                                artifactId: reportArtifactId,
                                answerGroupId: reportAnswerGroupId,
                                panelId: reportPanelId,
                              })
                            }
                            data-testid="task-center-open-report"
                            className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
                          >
                            <FileText size={12} />
                            查看报告
                          </button>
                        )}

                        {canOpenDeck && (
                          <>
                            <button
                              type="button"
                              onClick={() => {
                                void handleOpenDeck(task)
                              }}
                              disabled={deckLoadingTaskId === task.task_id}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-accent-blue/30 bg-accent-blue/10 px-3 py-1.5 text-xs text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:opacity-50"
                            >
                              {deckLoadingTaskId === task.task_id ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (
                                <Layers3 size={12} />
                              )}
                              打开 Deck
                            </button>

                            <button
                              type="button"
                              onClick={() => {
                                void handleShareDeck(task)
                              }}
                              disabled={sharingDeckTaskId === task.task_id}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
                              title={deckTitle}
                            >
                              {sharingDeckTaskId === task.task_id ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : copiedDeckTaskId === task.task_id ? (
                                <CheckCircle2 size={12} className="text-accent-green" />
                              ) : (
                                <Share2 size={12} />
                              )}
                              {copiedDeckTaskId === task.task_id ? '已复制并打开分享页' : '分享 Deck'}
                            </button>
                          </>
                        )}
                      </div>
                    )}

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

      {reportPreview && (
        <ReportPreviewModal
          open={true}
          onClose={() => setReportPreview(null)}
          markdown={reportPreview.markdown}
          title={reportPreview.title}
          sessionId={reportPreview.sessionId}
          artifactId={reportPreview.artifactId}
          answerGroupId={reportPreview.answerGroupId}
          panelId={reportPreview.panelId}
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
    </>
  )
}
