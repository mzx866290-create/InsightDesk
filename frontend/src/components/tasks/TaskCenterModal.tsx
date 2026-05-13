import React, { useEffect, useMemo, useState } from 'react'
import {
  CheckCircle2,
  Clock3,
  FileText,
  Layers3,
  Loader2,
  RefreshCw,
  Share2,
  ShieldAlert,
  XCircle,
} from 'lucide-react'

import {
  createDeckShareLink,
  decideTaskApproval,
  decideTaskApprovalsBatch,
  getDeck,
  getTaskApprovalPolicy,
  updateTaskApprovalPolicy,
} from '../../api/client'
import type {
  BatchTaskApprovalResponse,
  DeckSpec,
  TaskApprovalPolicy,
  TaskApprovalDecision,
  TaskRecord,
  TaskStatus,
} from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { createAndTrackTask, createAndTrackWorkflowTask, useTaskStore } from '../../stores/taskStore'
import { formatResearchModeLabel, getResearchTaskMeta } from '../../utils/researchTask'
import { DeckEditorModal } from '../reports/DeckEditorModal'
import { ResearchMetaCard } from '../research/ResearchMetaCard'
import { ReportPreviewModal } from '../reports/ReportPreviewModal'
import { Modal } from '../ui/Modal'

interface TaskCenterModalProps {
  open: boolean
  onClose: () => void
}

type TaskFilter = 'all' | 'active' | TaskStatus

type ApprovalPolicySaveState = 'idle' | 'saving' | 'saved' | 'error'

const TASK_TYPE_LABELS: Record<string, string> = {
  analyze_knowledge_base: 'Knowledge Base Analysis',
  generate_dashboard: 'Dashboard Generation',
  generate_deck: 'Deck Generation',
  generate_report: 'Report Generation',
  multi_agent_workflow: 'Multi-Agent Workflow',
  promote_attachment_to_kb: 'Attachment Indexing',
  upload_documents: 'Document Upload',
  web_research: 'Web Research',
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
    label: 'Pending',
    badgeClass: 'border-bg-border text-text-secondary',
    icon: <Clock3 size={13} className="text-text-secondary/70" />,
  },
  running: {
    label: 'Running',
    badgeClass: 'border-accent-blue/30 text-accent-blue',
    icon: <Loader2 size={13} className="animate-spin text-accent-blue" />,
  },
  waiting_approval: {
    label: 'Approval gate',
    badgeClass: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
    icon: <ShieldAlert size={13} className="text-amber-300" />,
  },
  completed: {
    label: 'Completed',
    badgeClass: 'border-accent-green/30 text-accent-green',
    icon: <CheckCircle2 size={13} className="text-accent-green" />,
  },
  failed: {
    label: 'Failed',
    badgeClass: 'border-accent-red/30 text-accent-red',
    icon: <XCircle size={13} className="text-accent-red" />,
  },
}

function taskTypeLabel(taskType: string): string {
  return TASK_TYPE_LABELS[taskType] ?? taskType
}

function formatTaskTime(timestamp: number | undefined): string {
  if (!timestamp) return 'Unknown time'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp * 1000))
}

function isRestartInterruptedTask(task: TaskRecord): boolean {
  return (
    typeof task.error === 'string' &&
    (task.error.includes('服务已重启') || task.error.includes('鏈嶅姟宸查噸鍚'))
  )
}

function taskContextLabel(task: TaskRecord): string {
  const params = task.params ?? {}

  if (task.task_type === 'generate_report') {
    const reportTitle =
      typeof params.report_title === 'string' ? params.report_title.trim() : ''
    if (reportTitle) return reportTitle
    const templateId = typeof params.template_id === 'string' ? params.template_id.trim() : ''
    if (templateId) return `Template: ${templateId}`
  }

  if (task.task_type === 'generate_deck') {
    const deckTitle = typeof params.deck_title === 'string' ? params.deck_title.trim() : ''
    if (deckTitle) return deckTitle
    const templateId = typeof params.template_id === 'string' ? params.template_id.trim() : ''
    if (templateId) return `Template: ${templateId}`
    const slideCount =
      typeof params.target_slide_count === 'number'
        ? params.target_slide_count
        : typeof params.target_slide_count === 'string'
          ? Number(params.target_slide_count)
          : 0
    if (slideCount > 0) return `${slideCount} slides`
  }

  if (task.task_type === 'promote_attachment_to_kb') {
    const attachmentName =
      typeof params.attachment_name === 'string' ? params.attachment_name.trim() : ''
    const vectorStorePath =
      typeof params.vector_store_path === 'string' ? params.vector_store_path.trim() : ''
    if (attachmentName && vectorStorePath) return `${attachmentName} -> ${vectorStorePath}`
    if (attachmentName) return attachmentName
    if (vectorStorePath) return vectorStorePath
  }

  if (task.task_type === 'upload_documents') {
    const fileNames = Array.isArray(params.file_names)
      ? params.file_names.filter(
          (value): value is string => typeof value === 'string' && value.trim().length > 0,
        )
      : []
    if (fileNames.length > 0) return fileNames.slice(0, 2).join(', ')
  }

  if (task.task_type === 'web_research') {
    const meta = getResearchTaskMeta(task)
    if (meta?.query && meta?.didFallback) {
      return `${meta.query} (${formatResearchModeLabel(meta.requestedMode)} -> ${formatResearchModeLabel(meta.effectiveMode)})`
    }
    if (meta?.query && meta?.providerSummary) return `${meta.query} (${meta.providerSummary})`
    if (meta?.query) return meta.query
  }

  if (task.task_type === 'multi_agent_workflow') {
    const requestText =
      typeof params.user_request === 'string' ? params.user_request.trim() : ''
    if (requestText) return requestText
  }

  return ''
}

function readParamText(
  params: Record<string, unknown> | undefined,
  keys: string[],
): string {
  for (const key of keys) {
    const value = params?.[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

function approvalGateTitle(task: TaskRecord): string {
  const explicitTitle = readParamText(task.params, [
    'approval_title',
    'approval_label',
    'approval_step_name',
  ])
  if (explicitTitle) return explicitTitle

  const stepId = readParamText(task.params, ['approval_step_id', 'approval_gate_id'])
  return stepId ? `Manual checkpoint: ${stepId}` : 'Manual checkpoint'
}

function approvalGateReason(task: TaskRecord): string {
  return (
    readParamText(task.params, [
      'approval_reason',
      'approval_message',
      'approval_summary',
      'approval_description',
    ]) ||
    task.result ||
    'This multi-agent workflow is paused until a reviewer approves or rejects the checkpoint.'
  )
}

const EMPTY_APPROVAL_POLICY: TaskApprovalPolicy = {
  enabled: false,
  required_task_types: [],
  high_risk_requires_approval: true,
  default_reviewer_role: '',
  updated_at: null,
}

function formatApprovalPolicyUpdatedAt(timestamp: number | null): string {
  if (!timestamp) return 'Never saved'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp * 1000))
}

function parseTaskTypeList(value: string): string[] {
  // Keep the persisted policy compact and stable for backend matching.
  return Array.from(
    new Set(
      value
        .split(',')
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
    ),
  )
}

export const TaskCenterModal: React.FC<TaskCenterModalProps> = ({ open, onClose }) => {
  const tasksMap = useTaskStore((s) => s.tasks)
  const syncRecentTasks = useTaskStore((s) => s.syncRecentTasks)
  const currentSessionId = useChatStore((s) => s.currentSessionId)
  const panels = useChatStore((s) => s.panels)

  const [refreshing, setRefreshing] = useState(false)
  const [retryingTaskId, setRetryingTaskId] = useState<string | null>(null)
  const [approvalAction, setApprovalAction] = useState<{
    taskId: string
    decision: TaskApprovalDecision
  } | null>(null)
  const [approvalErrors, setApprovalErrors] = useState<Record<string, string>>({})
  const [batchApprovalDecision, setBatchApprovalDecision] = useState<TaskApprovalDecision | null>(null)
  const [batchApprovalError, setBatchApprovalError] = useState('')
  const [batchApprovalResult, setBatchApprovalResult] =
    useState<BatchTaskApprovalResponse | null>(null)
  const [approvalPolicy, setApprovalPolicy] =
    useState<TaskApprovalPolicy>(EMPTY_APPROVAL_POLICY)
  const [approvalPolicyDraft, setApprovalPolicyDraft] =
    useState<TaskApprovalPolicy>(EMPTY_APPROVAL_POLICY)
  const [approvalPolicyTypesInput, setApprovalPolicyTypesInput] = useState('')
  const [approvalPolicyOpen, setApprovalPolicyOpen] = useState(false)
  const [approvalPolicyLoading, setApprovalPolicyLoading] = useState(false)
  const [approvalPolicySaveState, setApprovalPolicySaveState] =
    useState<ApprovalPolicySaveState>('idle')
  const [approvalPolicyError, setApprovalPolicyError] = useState('')
  const [taskFilter, setTaskFilter] = useState<TaskFilter>('all')
  const [workflowPrompt, setWorkflowPrompt] = useState('')
  const [workflowSubmitting, setWorkflowSubmitting] = useState(false)
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
  const approvalTaskCount = tasks.filter(
    (task) => task.task_type === 'multi_agent_workflow' && task.status === 'waiting_approval',
  ).length

  const filteredTasks = useMemo(() => {
    if (taskFilter === 'all') return tasks
    if (taskFilter === 'active') {
      return tasks.filter((task) => task.status === 'pending' || task.status === 'running')
    }
    return tasks.filter((task) => task.status === taskFilter)
  }, [taskFilter, tasks])

  const filteredApprovalTasks = useMemo(
    () =>
      filteredTasks.filter(
        (task) => task.task_type === 'multi_agent_workflow' && task.status === 'waiting_approval',
      ),
    [filteredTasks],
  )

  const approvalPolicySummary = useMemo(() => {
    const scope = approvalPolicy.required_task_types.length
      ? approvalPolicy.required_task_types.map(taskTypeLabel).join(', ')
      : 'No task types selected'
    const highRiskText = approvalPolicy.high_risk_requires_approval
      ? 'high-risk tasks require approval'
      : 'high-risk approval is optional'
    const reviewer = approvalPolicy.default_reviewer_role.trim() || 'no default reviewer'
    return `${approvalPolicy.enabled ? 'Enabled' : 'Disabled'} · ${scope} · ${highRiskText} · ${reviewer}`
  }, [approvalPolicy])

  useEffect(() => {
    if (!open) return
    void refreshTasks()
  }, [open, taskFilter])

  useEffect(() => {
    if (!open) return
    void loadApprovalPolicy()
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
      await syncRecentTasks(30, taskFilter === 'waiting_approval' ? 'waiting_approval' : undefined)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setRefreshing(false)
    }
  }

  const loadApprovalPolicy = async () => {
    setApprovalPolicyLoading(true)
    setApprovalPolicyError('')
    setApprovalPolicySaveState('idle')
    try {
      const policy = await getTaskApprovalPolicy()
      setApprovalPolicy(policy)
      setApprovalPolicyDraft(policy)
      setApprovalPolicyTypesInput(policy.required_task_types.join(', '))
    } catch (err) {
      setApprovalPolicyError((err as Error).message || 'Failed to load approval policy.')
      setApprovalPolicy(EMPTY_APPROVAL_POLICY)
      setApprovalPolicyDraft(EMPTY_APPROVAL_POLICY)
      setApprovalPolicyTypesInput('')
    } finally {
      setApprovalPolicyLoading(false)
    }
  }

  const handleSaveApprovalPolicy = async () => {
    if (approvalPolicySaveState === 'saving') return

    const payload: TaskApprovalPolicy = {
      ...approvalPolicyDraft,
      default_reviewer_role: approvalPolicyDraft.default_reviewer_role.trim(),
      required_task_types: parseTaskTypeList(approvalPolicyTypesInput),
    }

    setApprovalPolicySaveState('saving')
    setApprovalPolicyError('')
    try {
      const saved = await updateTaskApprovalPolicy(payload)
      setApprovalPolicy(saved)
      setApprovalPolicyDraft(saved)
      setApprovalPolicyTypesInput(saved.required_task_types.join(', '))
      setApprovalPolicySaveState('saved')
    } catch (err) {
      setApprovalPolicySaveState('error')
      setApprovalPolicyError((err as Error).message || 'Failed to save approval policy.')
    }
  }

  const handleStartWorkflow = async () => {
    const userRequest = workflowPrompt.trim()
    if (!userRequest || workflowSubmitting) return

    setWorkflowSubmitting(true)
    setError('')
    try {
      await createAndTrackWorkflowTask({
        user_request: userRequest,
        session_id: currentSessionId ?? undefined,
      })
      setWorkflowPrompt('')
      setTaskFilter('all')
      await syncRecentTasks(30)
    } catch (err) {
      setError((err as Error).message || 'Failed to create workflow task.')
    } finally {
      setWorkflowSubmitting(false)
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

  const handleApprovalDecision = async (
    task: TaskRecord,
    decision: TaskApprovalDecision,
  ) => {
    if (approvalAction || batchApprovalDecision) return

    setApprovalAction({ taskId: task.task_id, decision })
    setApprovalErrors((current) => {
      const next = { ...current }
      delete next[task.task_id]
      return next
    })
    setError('')
    try {
      const updated = await decideTaskApproval(task.task_id, { decision })
      useTaskStore.getState().addTask(updated)
      if (updated.status === 'pending' || updated.status === 'running') {
        useTaskStore.getState().startPolling(updated.task_id)
      } else {
        useTaskStore.getState().stopPolling(updated.task_id)
      }
      await syncRecentTasks(30)
    } catch (err) {
      const message = (err as Error).message || 'Approval request failed.'
      setApprovalErrors((current) => ({ ...current, [task.task_id]: message }))
      setError(message)
    } finally {
      setApprovalAction(null)
    }
  }

  const handleBatchApprovalDecision = async (decision: TaskApprovalDecision) => {
    if (approvalAction || batchApprovalDecision || filteredApprovalTasks.length === 0) return

    setBatchApprovalDecision(decision)
    setBatchApprovalError('')
    setBatchApprovalResult(null)
    setApprovalErrors({})
    setError('')
    try {
      const result = await decideTaskApprovalsBatch({
        task_ids: filteredApprovalTasks.map((task) => task.task_id),
        decision,
        comment:
          decision === 'approved'
            ? 'Batch approved from task center.'
            : 'Batch rejected from task center.',
      })
      setBatchApprovalResult(result)
      await syncRecentTasks(30, taskFilter === 'waiting_approval' ? 'waiting_approval' : undefined)
    } catch (err) {
      const message = (err as Error).message || 'Batch approval request failed.'
      setBatchApprovalError(message)
      setError(message)
    } finally {
      setBatchApprovalDecision(null)
    }
  }

  const handleOpenDeck = async (task: TaskRecord) => {
    const deckId = typeof task.params?.deck_id === 'string' ? task.params.deck_id.trim() : ''
    if (!deckId) {
      setError('Current task does not include a deck.')
      return
    }

    setDeckLoadingTaskId(task.task_id)
    setError('')
    try {
      const deck = await getDeck(deckId)
      setDeckData(deck)
      setDeckOpen(true)
    } catch (err) {
      setError((err as Error).message || 'Failed to open deck.')
    } finally {
      setDeckLoadingTaskId(null)
    }
  }

  const handleShareDeck = async (task: TaskRecord) => {
    const deckId = typeof task.params?.deck_id === 'string' ? task.params.deck_id.trim() : ''
    if (!deckId) {
      setError('Current task does not include a shareable deck.')
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
        setError('Share page opened, but copying the URL failed.')
      }
    } catch (err) {
      setError((err as Error).message || 'Failed to create a deck share link.')
    } finally {
      setSharingDeckTaskId(null)
    }
  }

  return (
    <>
      <Modal open={open} onClose={onClose} title="Task Center" width="max-w-4xl">
        <div className="space-y-4" data-testid="task-center-modal">
          <div className="rounded-2xl border border-bg-border bg-bg-primary/40 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <p className="text-sm font-medium text-text-primary">Start workflow</p>
                <p className="text-xs text-text-secondary">
                  {currentSessionId ? 'Linked to the current session.' : 'Creates a standalone workflow task.'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  void handleStartWorkflow()
                }}
                disabled={workflowSubmitting || workflowPrompt.trim().length === 0}
                data-testid="task-center-start-workflow"
                className="inline-flex items-center gap-1.5 rounded-lg border border-accent-blue/30 bg-accent-blue/10 px-3 py-1.5 text-xs text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {workflowSubmitting ? <Loader2 size={13} className="animate-spin" /> : <Layers3 size={13} />}
                Start workflow
              </button>
            </div>
            <textarea
              value={workflowPrompt}
              onChange={(event) => setWorkflowPrompt(event.target.value)}
              rows={3}
              placeholder="Research the target market, summarize the findings, and flag delivery risks."
              data-testid="task-center-workflow-prompt"
              className="mt-3 w-full resize-none rounded-xl border border-bg-border bg-bg-secondary/50 px-3 py-2 text-sm text-text-primary outline-none transition-colors placeholder:text-text-secondary/60 focus:border-accent-blue/40"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-bg-border bg-bg-primary/40 px-4 py-3">
            <div className="space-y-1">
              <p className="text-sm font-medium text-text-primary">Recent background tasks</p>
              <p className="text-xs text-text-secondary">
                {activeTaskCount} active task(s), {approvalTaskCount} approval gate(s), showing {filteredTasks.length} of the latest {Math.min(tasks.length, 30)} record(s).
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {([
                ['all', 'All'],
                ['active', 'Active'],
                ['waiting_approval', 'Approval gates'],
                ['completed', 'Completed'],
                ['failed', 'Failed'],
              ] as Array<[TaskFilter, string]>).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setTaskFilter(value)}
                  className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                    taskFilter === value
                      ? 'border-accent-blue/40 bg-accent-blue/10 text-accent-blue'
                      : 'border-bg-border text-text-secondary hover:border-accent-blue/40 hover:text-text-primary'
                  }`}
                >
                  {label}
                </button>
              ))}
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
                Refresh
              </button>
            </div>
          </div>

          <div
            className="rounded-2xl border border-amber-400/20 bg-bg-primary/40 px-4 py-3"
            data-testid="task-center-approval-policy"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <ShieldAlert size={14} className="text-amber-300" />
                  <p className="text-sm font-medium text-text-primary">Approval policy</p>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[11px] ${
                      approvalPolicy.enabled
                        ? 'border-amber-400/40 bg-amber-400/10 text-amber-200'
                        : 'border-bg-border text-text-secondary'
                    }`}
                  >
                    {approvalPolicy.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
                <p className="text-xs leading-5 text-text-secondary">
                  {approvalPolicyLoading ? 'Loading approval policy...' : approvalPolicySummary}
                </p>
                <p className="text-[11px] text-text-secondary/80">
                  Updated {formatApprovalPolicyUpdatedAt(approvalPolicy.updated_at)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setApprovalPolicyOpen((value) => !value)}
                className="rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
              >
                {approvalPolicyOpen ? 'Hide config' : 'Configure'}
              </button>
            </div>

            {approvalPolicyOpen && (
              <div className="mt-3 grid gap-3 rounded-xl border border-bg-border bg-bg-secondary/30 px-3 py-3">
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className="flex items-center justify-between gap-3 rounded-lg border border-bg-border bg-bg-primary/40 px-3 py-2 text-xs text-text-secondary">
                    <span>Enable approval policy</span>
                    <input
                      type="checkbox"
                      checked={approvalPolicyDraft.enabled}
                      onChange={(event) =>
                        setApprovalPolicyDraft((current) => ({
                          ...current,
                          enabled: event.target.checked,
                        }))
                      }
                      disabled={approvalPolicyLoading || approvalPolicySaveState === 'saving'}
                      data-testid="task-center-approval-policy-toggle"
                    />
                  </label>
                  <label className="flex items-center justify-between gap-3 rounded-lg border border-bg-border bg-bg-primary/40 px-3 py-2 text-xs text-text-secondary">
                    <span>High-risk approval</span>
                    <input
                      type="checkbox"
                      checked={approvalPolicyDraft.high_risk_requires_approval}
                      onChange={(event) =>
                        setApprovalPolicyDraft((current) => ({
                          ...current,
                          high_risk_requires_approval: event.target.checked,
                        }))
                      }
                      disabled={approvalPolicyLoading || approvalPolicySaveState === 'saving'}
                    />
                  </label>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-1.5 text-xs text-text-secondary">
                    <span>Default reviewer role</span>
                    <input
                      type="text"
                      value={approvalPolicyDraft.default_reviewer_role}
                      onChange={(event) =>
                        setApprovalPolicyDraft((current) => ({
                          ...current,
                          default_reviewer_role: event.target.value,
                        }))
                      }
                      placeholder="admin"
                      disabled={approvalPolicyLoading || approvalPolicySaveState === 'saving'}
                      className="rounded-lg border border-bg-border bg-bg-primary/60 px-3 py-2 text-xs text-text-primary outline-none transition-colors placeholder:text-text-secondary/60 focus:border-accent-blue/40"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs text-text-secondary">
                    <span>Required task types</span>
                    <input
                      type="text"
                      value={approvalPolicyTypesInput}
                      onChange={(event) => setApprovalPolicyTypesInput(event.target.value)}
                      placeholder="multi_agent_workflow, generate_report"
                      disabled={approvalPolicyLoading || approvalPolicySaveState === 'saving'}
                      className="rounded-lg border border-bg-border bg-bg-primary/60 px-3 py-2 text-xs text-text-primary outline-none transition-colors placeholder:text-text-secondary/60 focus:border-accent-blue/40"
                    />
                  </label>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-h-5 text-[11px] leading-5">
                    {approvalPolicyError ? (
                      <span className="text-accent-red">{approvalPolicyError}</span>
                    ) : approvalPolicySaveState === 'saved' ? (
                      <span className="text-accent-green">Saved.</span>
                    ) : (
                      <span className="text-text-secondary">
                        Use commas to separate task type keys.
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      void handleSaveApprovalPolicy()
                    }}
                    disabled={approvalPolicyLoading || approvalPolicySaveState === 'saving'}
                    data-testid="task-center-approval-policy-save"
                    aria-busy={approvalPolicySaveState === 'saving'}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-accent-blue/30 bg-accent-blue/10 px-3 py-1.5 text-xs text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {approvalPolicySaveState === 'saving' ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <CheckCircle2 size={13} />
                    )}
                    {approvalPolicySaveState === 'saving' ? 'Saving...' : 'Save policy'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {filteredApprovalTasks.length > 0 && (
            <div className="rounded-2xl border border-amber-400/25 bg-amber-400/10 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-amber-200">Batch approval</p>
                  <p className="text-xs text-text-secondary">
                    Apply a decision to {filteredApprovalTasks.length} waiting approval task(s) in the current view.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      void handleBatchApprovalDecision('approved')
                    }}
                    disabled={approvalAction !== null || batchApprovalDecision !== null}
                    data-testid="task-center-batch-approve"
                    aria-busy={batchApprovalDecision === 'approved'}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-1.5 text-xs text-accent-green transition-colors hover:bg-accent-green/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {batchApprovalDecision === 'approved' ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <CheckCircle2 size={13} />
                    )}
                    {batchApprovalDecision === 'approved' ? 'Approving...' : 'Approve all'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void handleBatchApprovalDecision('rejected')
                    }}
                    disabled={approvalAction !== null || batchApprovalDecision !== null}
                    data-testid="task-center-batch-reject"
                    aria-busy={batchApprovalDecision === 'rejected'}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-1.5 text-xs text-accent-red transition-colors hover:bg-accent-red/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {batchApprovalDecision === 'rejected' ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <XCircle size={13} />
                    )}
                    {batchApprovalDecision === 'rejected' ? 'Rejecting...' : 'Reject all'}
                  </button>
                </div>
              </div>

              {(batchApprovalResult || batchApprovalError) && (
                <div
                  data-testid="task-center-batch-result"
                  className={`mt-3 rounded-xl border px-3 py-2 text-xs ${
                    batchApprovalError
                      ? 'border-accent-red/20 bg-accent-red/10 text-accent-red'
                      : 'border-bg-border bg-bg-secondary/40 text-text-secondary'
                  }`}
                >
                  {batchApprovalError
                    ? batchApprovalError
                    : `Batch decision complete: ${batchApprovalResult?.succeeded ?? 0}/${batchApprovalResult?.total ?? 0} succeeded, ${batchApprovalResult?.failed ?? 0} failed.`}
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-sm text-accent-red">
              {error}
            </div>
          )}

          {filteredTasks.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-bg-border bg-bg-primary/30 px-4 py-8 text-center text-sm text-text-secondary">
              No tasks to show yet.
            </div>
          ) : (
            <div className="space-y-3">
              {filteredTasks.map((task) => {
                const statusMeta = STATUS_META[task.status]
                const restartInterrupted = isRestartInterruptedTask(task)
                const contextLabel = taskContextLabel(task)
                const needsApproval =
                  task.task_type === 'multi_agent_workflow' && task.status === 'waiting_approval'
                const approvalBusy = approvalAction?.taskId === task.task_id
                const approvalError = approvalErrors[task.task_id]
                const researchMeta = getResearchTaskMeta(task)
                const reportMarkdown =
                  typeof task.params?.report_markdown === 'string' ? task.params.report_markdown : ''
                const reportTitle =
                  typeof task.params?.report_title === 'string' ? task.params.report_title : 'Research Report'
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
                  typeof task.params?.deck_title === 'string' ? task.params.deck_title : 'Deck Draft'
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
                              Restart interrupted
                            </span>
                          )}
                        </div>

                        <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                          <span>Created {formatTaskTime(task.created_at)}</span>
                          <span>Updated {formatTaskTime(task.updated_at ?? task.created_at)}</span>
                          <span className="font-mono text-text-secondary/70">{task.task_id}</span>
                        </div>

                        {contextLabel && (
                          <p className="mt-2 text-xs text-text-secondary">{contextLabel}</p>
                        )}
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {needsApproval && (
                          <>
                            <button
                              type="button"
                              onClick={() => {
                                void handleApprovalDecision(task, 'approved')
                              }}
                              disabled={approvalAction !== null || batchApprovalDecision !== null}
                              data-testid="task-center-approve"
                              aria-busy={approvalBusy && approvalAction?.decision === 'approved'}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-1.5 text-xs text-accent-green transition-colors hover:bg-accent-green/20 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {approvalBusy && approvalAction?.decision === 'approved' ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (
                                <CheckCircle2 size={12} />
                              )}
                              {approvalBusy && approvalAction?.decision === 'approved' ? 'Approving...' : 'Approve'}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                void handleApprovalDecision(task, 'rejected')
                              }}
                              disabled={approvalAction !== null || batchApprovalDecision !== null}
                              data-testid="task-center-reject"
                              aria-busy={approvalBusy && approvalAction?.decision === 'rejected'}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-1.5 text-xs text-accent-red transition-colors hover:bg-accent-red/20 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {approvalBusy && approvalAction?.decision === 'rejected' ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (
                                <XCircle size={12} />
                              )}
                              {approvalBusy && approvalAction?.decision === 'rejected' ? 'Rejecting...' : 'Reject'}
                            </button>
                          </>
                        )}

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
                            {restartInterrupted ? 'Relaunch' : 'Retry'}
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="mt-3">
                      <div className="mb-1 flex items-center justify-between text-[11px] text-text-secondary">
                        <span>Progress</span>
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
                                  : task.status === 'waiting_approval'
                                    ? 'bg-amber-400'
                                    : 'bg-text-secondary/40'
                          }`}
                          style={{ width: `${Math.min(100, task.progress)}%` }}
                        />
                      </div>
                    </div>

                    {researchMeta && <ResearchMetaCard meta={researchMeta} className="mt-3" />}

                    {needsApproval && (
                      <div className="mt-3 rounded-xl border border-amber-400/20 bg-amber-400/10 px-3 py-2">
                        <div className="flex items-start gap-2">
                          <ShieldAlert size={14} className="mt-0.5 shrink-0 text-amber-300" />
                          <div className="min-w-0">
                            <p className="text-[11px] font-medium text-amber-200">
                              {approvalGateTitle(task)}
                            </p>
                            <p className="mt-1 text-xs leading-5 text-text-secondary">
                              {approvalGateReason(task)}
                            </p>
                          </div>
                        </div>
                        <p className="mt-2 text-[11px] leading-5 text-amber-200/80">
                          Approve to resume execution, or reject to stop the workflow with a recorded decision.
                        </p>
                        {approvalError && (
                          <p className="mt-2 rounded-lg border border-accent-red/20 bg-accent-red/10 px-2 py-1.5 text-[11px] leading-5 text-accent-red">
                            {approvalError}
                          </p>
                        )}
                      </div>
                    )}

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
                            Open Report
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
                              Open Deck
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
                              {copiedDeckTaskId === task.task_id ? 'Copied share URL' : 'Share Deck'}
                            </button>
                          </>
                        )}
                      </div>
                    )}

                    {task.result && (
                      <div className="mt-3 rounded-xl border border-bg-border bg-bg-secondary/40 px-3 py-2">
                        <p className="text-[11px] font-medium text-text-primary">Result</p>
                        <p className="mt-1 text-xs leading-5 text-text-secondary">{task.result}</p>
                      </div>
                    )}

                    {task.error && (
                      <div className="mt-3 rounded-xl border border-accent-red/20 bg-accent-red/10 px-3 py-2">
                        <p className="text-[11px] font-medium text-accent-red">Error</p>
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
