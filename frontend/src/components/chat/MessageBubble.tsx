import React, { Suspense } from 'react'
import {
  AlertCircle,
  ArrowUpCircle,
  Bookmark,
  BookmarkCheck,
  Check,
  Copy,
  Download,
  Eye,
  GitBranch,
  Loader2,
  Paperclip,
  Pencil,
  Pin,
  Quote,
  RotateCcw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'
import type { PanelMessage } from '../../stores/chatStore'
import { CitationPanel } from './CitationPanel'
import { ErrorBanner } from './ErrorBanner'
import { IntentCardRenderer, stripIntentBlocks } from '../cards/IntentCardRenderer'
import { TaskProgressCard } from '../cards/TaskProgressCard'
import { ResearchMetaCard } from '../research/ResearchMetaCard'
import { getResearchTaskMeta } from '../../utils/researchTask'
import { useChatStore } from '../../stores/chatStore'
import { createAndTrackTask, useTaskStore } from '../../stores/taskStore'
import {
  clearSessionMessages,
  createBookmark,
  deleteBookmark,
  pinSessionMemory,
  setMessageFeedback,
} from '../../api/client'
import type { ChatFile } from '../../api/client'
import { AttachmentPreviewModal } from './AttachmentPreviewModal'
import { ReportPreviewModal } from '../reports/ReportPreviewModal'
import { ReportGenerationModal } from '../reports/ReportGenerationModal'

/*
interface MessageBubbleProps {
  message: PanelMessage
  panelId?: string
  isPrimaryPanel?: boolean
  interactionLocked?: boolean
  onReview?: (message: PanelMessage) => Promise<void> | void
  onPromote?: (message: PanelMessage) => Promise<void>
  onRerun?: (message: PanelMessage) => Promise<void>
  canRerun?: boolean
  onContinue?: (message: PanelMessage) => Promise<void>
  canContinue?: boolean
  onRetryError?: (message: PanelMessage) => Promise<void> | void
  onFork?: (message: PanelMessage) => void
  // 对话分叉：从该消息之前的历史创建新会话
  onFork?: (message: PanelMessage) => void
}

*/

interface MessageBubbleProps {
  message: PanelMessage
  panelId?: string
  isPrimaryPanel?: boolean
  interactionLocked?: boolean
  onReview?: (message: PanelMessage) => Promise<void> | void
  onPromote?: (message: PanelMessage) => Promise<void>
  onRerun?: (message: PanelMessage) => Promise<void>
  canRerun?: boolean
  onContinue?: (message: PanelMessage) => Promise<void>
  canContinue?: boolean
  onRetryError?: (message: PanelMessage) => Promise<void> | void
  onFork?: (message: PanelMessage) => void
}

const MessageMarkdown = React.lazy(() => import('./MessageMarkdown'))

const formatMessageTimestamp = (timestamp?: number): string => {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  if (Number.isNaN(date.getTime())) return ''

  const now = new Date()
  const isSameDay =
    now.getFullYear() === date.getFullYear() &&
    now.getMonth() === date.getMonth() &&
    now.getDate() === date.getDate()

  const formatter = new Intl.DateTimeFormat('zh-CN', {
    month: isSameDay ? undefined : '2-digit',
    day: isSameDay ? undefined : '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return formatter.format(date)
}

const tokenCountFormatter = new Intl.NumberFormat('zh-CN')

const formatTokenUsage = (usage?: PanelMessage['tokenUsage']): string => {
  if (!usage) return 'Tokens: unavailable'
  const total = Number.isFinite(usage.total_tokens) ? usage.total_tokens : 0
  const prompt = Number.isFinite(usage.prompt_tokens) ? usage.prompt_tokens : 0
  const completion = Number.isFinite(usage.completion_tokens)
    ? usage.completion_tokens
    : 0
  const suffix = usage.estimated ? ' est.' : ''
  return `Tokens: ${tokenCountFormatter.format(total)}${suffix} (in ${tokenCountFormatter.format(prompt)} / out ${tokenCountFormatter.format(completion)})`
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  panelId,
  isPrimaryPanel = false,
  interactionLocked = false,
  onReview,
  onPromote,
  onRerun,
  canRerun = false,
  onContinue,
  canContinue = false,
  onRetryError,
  onFork,
}) => {
  const isUser = message.role === 'user'
  const isError = message.role === 'error'
  const [promoting, setPromoting] = React.useState(false)
  const [reviewing, setReviewing] = React.useState(false)
  const [promoted, setPromoted] = React.useState(false)
  const [rerunning, setRerunning] = React.useState(false)
  const [continuing, setContinuing] = React.useState(false)
  const [copied, setCopied] = React.useState(false)
  const [bookmarkState, setBookmarkState] = React.useState<'idle' | 'saving' | 'error'>('idle')
  const [memoryPinState, setMemoryPinState] = React.useState<
    'idle' | 'saving' | 'created' | 'duplicate' | 'error'
  >('idle')
  const [feedbackState, setFeedbackState] = React.useState<'idle' | 'saving' | 'error'>('idle')
  const [feedbackPendingValue, setFeedbackPendingValue] = React.useState<1 | -1 | 0 | null>(null)
  const [previewFile, setPreviewFile] = React.useState<ChatFile | null>(null)
  const [reportState, setReportState] = React.useState<'idle' | 'loading' | 'error'>('idle')
  const [reportError, setReportError] = React.useState<string | null>(null)
  const [reportConfigOpen, setReportConfigOpen] = React.useState(false)
  const [reportTaskId, setReportTaskId] = React.useState<string | null>(null)
  const [handledReportTaskId, setHandledReportTaskId] = React.useState<string | null>(null)
  const [reportPreview, setReportPreview] = React.useState<{
    markdown: string
    title: string
    sessionId: string
    artifactId?: string
    answerGroupId?: string
    panelId?: string
  } | null>(null)

  const {
    currentSessionId,
    clearMessages,
    setSettingsOpen,
    updateSession,
    pushComposerSeed,
    bookmarks,
    addBookmark,
    removeBookmark,
    sessions,
    updateMessage,
  } = useChatStore()
  const reportTask = useTaskStore((state) => (reportTaskId ? state.tasks[reportTaskId] : undefined))
  const researchTask = useTaskStore((state) => (message.taskId ? state.tasks[message.taskId] : undefined))
  const effectivePanelId = panelId ?? message.panelId ?? ''
  const bookmarkEntry = bookmarks.find((bookmark) => {
    if ((bookmark.source ?? 'remote') === 'local' && bookmark.id === message.id) {
      return true
    }

    if (
      currentSessionId &&
      bookmark.sessionId === currentSessionId &&
      typeof bookmark.messageId === 'number' &&
      typeof message.serverMessageId === 'number' &&
      bookmark.messageId === message.serverMessageId
    ) {
      return true
    }

    if (
      currentSessionId &&
      bookmark.sessionId === currentSessionId &&
      message.answerGroupId &&
      bookmark.answerGroupId === message.answerGroupId &&
      bookmark.role === message.role
    ) {
      return message.role === 'user' || bookmark.panelId === effectivePanelId
    }

    return false
  })
  const isBookmarked = Boolean(bookmarkEntry)
  const messageTimeLabel = formatMessageTimestamp(message.timestamp)
  const tokenUsageLabel = !isUser && !isError ? formatTokenUsage(message.tokenUsage) : ''

  const handleClearContext = async () => {
    if (currentSessionId) {
      await clearSessionMessages(currentSessionId)
      updateSession(currentSessionId, {
        message_count: 0,
        updated_at: Date.now() / 1000,
      })
    }
    clearMessages()
  }

  const handleRetryError = async () => {
    if (!onRetryError || interactionLocked || !message.answerGroupId) return
    await onRetryError(message)
  }

  if (isError) {
    return (
      <ErrorBanner
        content={message.content}
        errorCode={message.errorCode}
        suggestion={message.suggestion}
        onRetry={
          onRetryError && message.answerGroupId && !interactionLocked
            ? () => {
                void handleRetryError()
              }
            : undefined
        }
        onClearContext={handleClearContext}
        onOpenSettings={() => setSettingsOpen(true)}
      />
    )
  }

  const messageBody = stripIntentBlocks(message.content)

  const handleEditMessage = () => {
    pushComposerSeed({
      text: message.content,
      images: message.images ?? [],
      files: message.files ?? [],
      editAnswerGroupId: message.answerGroupId ?? null,
    })
  }

  if (isUser) {
    return (
      <div
        className="mb-4 flex justify-end animate-fade-in group/user"
        data-role={message.role}
        data-panel-id={panelId}
        data-answer-group-id={message.answerGroupId}
        data-message-id={message.id}
        data-server-message-id={message.serverMessageId}
      >
        <div className="flex flex-col items-end gap-1 max-w-[85%]">
        {!interactionLocked && (
          <button
            type="button"
            onClick={handleEditMessage}
            className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-text-secondary/40 opacity-0 group-hover/user:opacity-100 transition-opacity hover:text-text-secondary"
            title="编辑并重新发送"
          >
            <Pencil size={10} />
            编辑
          </button>
        )}
        <div className="rounded-2xl rounded-tr-sm border border-accent-blue/30 bg-accent-blue/20 px-4 py-3 text-sm leading-relaxed text-text-primary w-full break-words">
          {message.images && message.images.length > 0 && (
            <div className="mb-3 grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))' }}>
              {message.images.map((image, index) => (
                <a
                  key={`${image.name}-${index}`}
                  href={image.data_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block overflow-hidden rounded-xl border border-accent-blue/20 bg-black/10"
                >
                  <img
                    src={image.data_url}
                    alt={image.name}
                    className="h-28 w-full object-cover"
                  />
                </a>
              ))}
            </div>
          )}
          {message.files && message.files.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {message.files.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="inline-flex max-w-full items-center gap-2 rounded-xl border border-accent-blue/25 bg-white/5 px-3 py-2 text-xs text-text-primary"
                  title={file.name}
                >
                  <Paperclip size={12} className="shrink-0" />
                  <span className="max-w-[160px] truncate">{file.name}</span>
                  {file.extracted_text && (
                    <>
                      <button
                        type="button"
                        onClick={() => setPreviewFile(file)}
                        className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/10 hover:text-text-primary"
                        title="预览附件内容"
                      >
                        <Eye size={11} className="shrink-0" />
                        预览
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const rawText = (file.extracted_text ?? '').trim()
                          if (!rawText) return
                          const clipped = rawText.length > 500
                            ? `${rawText.slice(0, 500).trim()}\n...[以下内容已截断]`
                            : rawText
                          pushComposerSeed({ text: `请把以下来自"${file.name}"的片段作为上下文：\n"""\n${clipped}\n"""` })
                        }}
                        className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/10 hover:text-text-primary"
                        title="引用此附件内容到输入框"
                      >
                        <Quote size={11} className="shrink-0" />
                        引用
                      </button>
                    </>
                  )}
                  {file.data_url && (
                    <a
                      href={file.data_url}
                      download={file.name}
                      className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-text-secondary transition-colors hover:bg-white/10 hover:text-text-primary"
                      title={`下载 ${file.name}`}
                    >
                      <Download size={11} className="shrink-0 opacity-70" />
                      下载
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
          {message.content && <div>{message.content}</div>}
          {previewFile && (
            <AttachmentPreviewModal file={previewFile} onClose={() => setPreviewFile(null)} />
          )}
        </div>
        {messageTimeLabel && (
          <div className="text-[10px] text-text-secondary/55">{messageTimeLabel}</div>
        )}
        </div>
      </div>
    )
  }

  const canPromote =
    Boolean(onPromote) &&
    Boolean(message.answerGroupId) &&
    !interactionLocked &&
    !message.streaming &&
    !isPrimaryPanel

  const canReview =
    Boolean(onReview) &&
    Boolean(currentSessionId) &&
    Boolean(message.answerGroupId) &&
    !interactionLocked &&
    !message.streaming

  const canRunAgain =
    Boolean(onRerun) &&
    canRerun &&
    Boolean(message.answerGroupId) &&
    !interactionLocked &&
    !message.streaming

  const canContinueGeneration =
    Boolean(onContinue) &&
    canContinue &&
    Boolean(message.answerGroupId) &&
    !interactionLocked &&
    !message.streaming

  const canPinToMemory =
    Boolean(currentSessionId) &&
    !interactionLocked &&
    !message.streaming &&
    Boolean(messageBody.trim())

  const canGiveFeedback =
    Boolean(currentSessionId) &&
    !interactionLocked &&
    !message.streaming &&
    Boolean(message.serverMessageId || message.answerGroupId)

  const canBookmark =
    Boolean(currentSessionId) &&
    !interactionLocked &&
    !message.streaming &&
    Boolean(messageBody.trim()) &&
    Boolean(message.serverMessageId || message.answerGroupId || bookmarkEntry)

  const isCompletedResearchMessage =
    message.role === 'assistant' &&
    !message.streaming &&
    (message.taskType === 'web_research' || message.modelId === 'web_research') &&
    Array.isArray(message.sources) &&
    message.sources.length > 0
  const researchTaskMeta = getResearchTaskMeta(researchTask)
  const showResearchMeta =
    message.role === 'assistant' &&
    (message.taskType === 'web_research' || message.modelId === 'web_research') &&
    Boolean(researchTaskMeta)

  const canGenerateReport =
    Boolean(currentSessionId) &&
    !interactionLocked &&
    isCompletedResearchMessage

  const isReportTaskActive =
    reportTask?.status === 'pending' || reportTask?.status === 'running'

  const handlePromote = async () => {
    if (!onPromote || !canPromote) return
    setPromoting(true)
    try {
      await onPromote(message)
      setPromoted(true)
      window.setTimeout(() => setPromoted(false), 2000)
    } finally {
      setPromoting(false)
    }
  }

  const handleReview = async () => {
    if (!onReview || !canReview) return
    setReviewing(true)
    try {
      await onReview(message)
    } finally {
      setReviewing(false)
    }
  }

  const handleRerun = async () => {
    if (!onRerun || !canRunAgain) return
    setRerunning(true)
    try {
      await onRerun(message)
    } finally {
      setRerunning(false)
    }
  }

  const handleContinue = async () => {
    if (!onContinue || !canContinueGeneration) return
    setContinuing(true)
    try {
      await onContinue(message)
    } finally {
      setContinuing(false)
    }
  }

  const handleBookmark = async () => {
    if (!canBookmark) return

    if (bookmarkEntry) {
      setBookmarkState('saving')
      try {
        if ((bookmarkEntry.source ?? 'remote') === 'remote') {
          await deleteBookmark(bookmarkEntry.id)
        }
        removeBookmark(bookmarkEntry.id)
        setBookmarkState('idle')
      } catch {
        setBookmarkState('error')
        window.setTimeout(() => setBookmarkState('idle'), 1800)
      }
      return
    }

    const session = sessions.find((s) => s.session_id === currentSessionId)
    setBookmarkState('saving')
    try {
      const savedBookmark = await createBookmark({
        session_id: currentSessionId ?? '',
        role: message.role as 'user' | 'assistant',
        message_id: message.serverMessageId,
        panel_id: effectivePanelId,
        answer_group_id: message.answerGroupId ?? '',
        content: messageBody,
        model_id: message.modelId,
        session_title: session?.title ?? '未命名对话',
      })
      addBookmark(savedBookmark)
      setBookmarkState('idle')
    } catch {
      setBookmarkState('error')
      window.setTimeout(() => setBookmarkState('idle'), 1800)
    }
  }

  const handleCopy = () => {
    const text = messageBody
    if (!text.trim()) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleFeedback = async (value: 1 | -1) => {
    if (!currentSessionId || !canGiveFeedback) return
    const nextValue = message.feedbackValue === value ? 0 : value
    setFeedbackState('saving')
    setFeedbackPendingValue(value)
    try {
      const result = await setMessageFeedback(currentSessionId, {
        value: nextValue,
        message_id: message.serverMessageId,
        panel_id: message.panelId ?? panelId ?? '',
        answer_group_id: message.answerGroupId ?? '',
      })
      updateMessage(panelId ?? message.panelId ?? '', message.id, {
        serverMessageId: result.message_id,
        panelId: result.panel_id,
        answerGroupId: result.answer_group_id,
        feedbackValue: result.feedback_value,
      })
      setFeedbackState('idle')
    } catch {
      setFeedbackState('error')
      window.setTimeout(() => setFeedbackState('idle'), 1800)
    } finally {
      setFeedbackPendingValue(null)
    }
  }

  const handlePinToMemory = async () => {
    if (!currentSessionId || !canPinToMemory) return
    setMemoryPinState('saving')
    try {
      const result = await pinSessionMemory(currentSessionId, {
        content: messageBody,
        kind: 'fact',
      })
      updateSession(currentSessionId, {
        updated_at: Date.now() / 1000,
      })
      setMemoryPinState(result.created ? 'created' : 'duplicate')
    } catch {
      setMemoryPinState('error')
    } finally {
      window.setTimeout(() => setMemoryPinState('idle'), 2200)
    }
  }

  const handleGenerateReport = async (payload?: {
    template_id?: string
    template_options?: Record<string, unknown>
  }) => {
    if (!currentSessionId || !canGenerateReport) return
    setReportState('loading')
    setReportError(null)
    try {
      const task = await createAndTrackTask(
        'generate_report',
        {
          answer_group_id: message.answerGroupId,
          panel_id: effectivePanelId,
          template_id: payload?.template_id,
          template_options: payload?.template_options,
        },
        currentSessionId,
      )
      setReportTaskId(task.task_id)
      setHandledReportTaskId(null)
      setReportState('idle')
    } catch (error) {
      const detail = (error as Error).message || '报告生成失败，请稍后重试。'
      setReportState('error')
      setReportError(detail)
      window.alert(detail)
      setReportState('idle')
    }
  }

  React.useEffect(() => {
    if (!reportTaskId || !reportTask || handledReportTaskId === reportTaskId) return

    if (reportTask.status === 'completed') {
      const params = reportTask.params ?? {}
      const markdown = typeof params.report_markdown === 'string' ? params.report_markdown : ''
      const title = typeof params.report_title === 'string' ? params.report_title : '研究报告'
      const artifactId =
        typeof params.artifact_id === 'string' ? params.artifact_id : undefined
      if (markdown) {
        setReportPreview({
          markdown,
          title,
          sessionId: currentSessionId ?? reportTask.session_id ?? '',
          artifactId,
          answerGroupId:
            typeof params.answer_group_id === 'string'
              ? params.answer_group_id
              : message.answerGroupId,
          panelId: typeof params.panel_id === 'string' ? params.panel_id : effectivePanelId,
        })
      }
      setReportError(null)
      setReportState('idle')
      setHandledReportTaskId(reportTaskId)
      return
    }

    if (reportTask.status === 'failed') {
      setReportError(reportTask.error ?? '报告生成失败，请稍后重试。')
      setReportState('error')
      setHandledReportTaskId(reportTaskId)
      return
    }

    if (reportTask.status === 'pending' || reportTask.status === 'running') {
      setReportState('loading')
    }
  }, [
    currentSessionId,
    effectivePanelId,
    handledReportTaskId,
    message.answerGroupId,
    reportTask,
    reportTaskId,
  ])

  const pinFeedbackVisible = memoryPinState !== 'idle'
  let pinButtonLabel = '固定到记忆'
  if (memoryPinState === 'created') pinButtonLabel = '已固定到记忆'
  else if (memoryPinState === 'duplicate') pinButtonLabel = '记忆已存在'
  else if (memoryPinState === 'error') pinButtonLabel = '固定失败'

  return (
    <div
      className="mb-4 flex justify-start animate-fade-in"
      data-role={message.role}
      data-panel-id={panelId}
      data-answer-group-id={message.answerGroupId}
      data-message-id={message.id}
      data-server-message-id={message.serverMessageId}
    >
      <div className={`max-w-[95%] min-w-0 text-sm break-words ${message.streaming ? 'streaming-cursor' : ''}`}>
        {(canReview || canPromote || promoted || canRunAgain || canContinueGeneration || canPinToMemory || pinFeedbackVisible) && (
          <div className="mb-1 flex items-center gap-2 text-[10px] text-text-secondary">
            {canReview && (
              <button
                type="button"
                onClick={() => {
                  void handleReview()
                }}
                disabled={reviewing}
                className="inline-flex items-center gap-1 rounded-md border border-bg-border px-2 py-1 transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
              >
                {reviewing ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <Eye size={11} />
                )}
                对比评审
              </button>
            )}
            {(canPromote || promoted) && (
              <button
                type="button"
                onClick={() => {
                  void handlePromote()
                }}
                disabled={promoting}
                className="inline-flex items-center gap-1 rounded-md border border-bg-border px-2 py-1 transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
              >
                {promoting ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : promoted ? (
                  <Check size={11} className="text-accent-green" />
                ) : (
                  <ArrowUpCircle size={11} />
                )}
                {promoted ? '已设为主答案' : '设为主答案'}
              </button>
            )}
            {(canPinToMemory || pinFeedbackVisible) && (
              <button
                type="button"
                onClick={() => {
                  void handlePinToMemory()
                }}
                disabled={memoryPinState === 'saving'}
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-colors disabled:opacity-50 ${
                  memoryPinState === 'error'
                    ? 'border-accent-red/40 text-accent-red hover:border-accent-red/60'
                    : 'border-bg-border hover:border-accent-blue/40 hover:text-text-primary'
                }`}
              >
                {memoryPinState === 'saving' ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : memoryPinState === 'created' || memoryPinState === 'duplicate' ? (
                  <Check size={11} className="text-accent-green" />
                ) : memoryPinState === 'error' ? (
                  <AlertCircle size={11} />
                ) : (
                  <Pin size={11} />
                )}
                {pinButtonLabel}
              </button>
            )}
            {canRunAgain && (
              <button
                type="button"
                onClick={() => {
                  void handleRerun()
                }}
                disabled={rerunning}
                className="inline-flex items-center gap-1 rounded-md border border-bg-border px-2 py-1 transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
              >
                {rerunning ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <RotateCcw size={11} />
                )}
                仅重跑此模型
              </button>
            )}
            {canContinueGeneration && (
              <button
                type="button"
                onClick={() => {
                  void handleContinue()
                }}
                disabled={continuing}
                className="inline-flex items-center gap-1 rounded-md border border-bg-border px-2 py-1 transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
                title="继续生成剩余内容"
              >
                {continuing ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <Sparkles size={11} />
                )}
                继续生成
              </button>
            )}
            {message.modelId && (
              <span className="truncate text-text-secondary/70">{message.modelId}</span>
            )}
          </div>
        )}
        {message.taskId && <TaskProgressCard taskId={message.taskId} taskType={message.taskType} />}
        {reportTaskId && reportTaskId !== message.taskId && (
          <TaskProgressCard
            taskId={reportTaskId}
            taskType="generate_report"
            sessionId={currentSessionId ?? undefined}
          />
        )}
        {showResearchMeta && researchTaskMeta && (
          <ResearchMetaCard meta={researchTaskMeta} compact className="mb-3" />
        )}
        <IntentCardRenderer content={message.content} streaming={message.streaming} />
        <Suspense
          fallback={
            <div className="whitespace-pre-wrap leading-relaxed text-text-primary">
              {messageBody}
            </div>
          }
        >
          <MessageMarkdown content={messageBody} />
        </Suspense>
        {message.sources && message.sources.length > 0 && (
          <CitationPanel
            sources={message.sources}
            panelId={panelId}
            answerGroupId={message.answerGroupId}
            streaming={message.streaming}
          />
        )}
        {!message.streaming && messageBody.trim() && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            {tokenUsageLabel && (
              <span
                className="inline-flex items-center rounded-md border border-bg-border px-2 py-1 text-[10px] text-text-secondary/60"
                title="Token usage for this answer"
              >
                {tokenUsageLabel}
              </span>
            )}
            {canGiveFeedback && (
              <>
                <button
                  type="button"
                  onClick={() => {
                    void handleFeedback(1)
                  }}
                  disabled={feedbackState === 'saving'}
                  className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] transition-colors ${
                    message.feedbackValue === 1
                      ? 'text-accent-green'
                      : 'text-text-secondary/50 hover:bg-bg-hover hover:text-text-secondary'
                  }`}
                  title="喜欢这条回复"
                >
                  {feedbackState === 'saving' && feedbackPendingValue === 1 ? (
                    <Loader2 size={11} className="animate-spin" />
                  ) : (
                    <ThumbsUp size={11} />
                  )}
                  喜欢
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleFeedback(-1)
                  }}
                  disabled={feedbackState === 'saving'}
                  className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] transition-colors ${
                    message.feedbackValue === -1
                      ? 'text-accent-red'
                      : 'text-text-secondary/50 hover:bg-bg-hover hover:text-text-secondary'
                  }`}
                  title="不喜欢这条回复"
                >
                  {feedbackState === 'saving' && feedbackPendingValue === -1 ? (
                    <Loader2 size={11} className="animate-spin" />
                  ) : (
                    <ThumbsDown size={11} />
                  )}
                  不喜欢
                </button>
              </>
            )}
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-text-secondary/50 transition-colors hover:bg-bg-hover hover:text-text-secondary"
              title="复制全文"
            >
              {copied ? (
                <Check size={11} className="text-accent-green" />
              ) : (
                <Copy size={11} />
              )}
              {copied ? '已复制' : '复制'}
            </button>
            {canGenerateReport && (
              <button
                type="button"
                onClick={() => {
                  setReportConfigOpen(true)
                }}
                disabled={reportState === 'loading' || isReportTaskActive || reportConfigOpen}
                data-testid="message-generate-report"
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-text-secondary/50 transition-colors hover:bg-bg-hover hover:text-text-secondary disabled:opacity-40"
                title={reportError ?? '基于当前会话生成报告预览'}
              >
                {reportState === 'loading' || isReportTaskActive ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <Download size={11} />
                )}
                {reportState === 'loading' || isReportTaskActive ? '生成中' : '生成报告'}
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                void handleBookmark()
              }}
              disabled={!canBookmark || bookmarkState === 'saving'}
              className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] transition-colors ${
                isBookmarked
                  ? 'text-amber-400 hover:text-amber-300'
                  : 'text-text-secondary/50 hover:bg-bg-hover hover:text-text-secondary'
              } disabled:opacity-40`}
              title={isBookmarked ? '取消书签' : '添加书签'}
            >
              {bookmarkState === 'saving' ? (
                <Loader2 size={11} className="animate-spin" />
              ) : isBookmarked ? (
                <BookmarkCheck size={11} />
              ) : (
                <Bookmark size={11} />
              )}
              {bookmarkState === 'saving' ? '保存中' : isBookmarked ? '已收藏' : '收藏'}
            </button>
            {onFork && !interactionLocked && (
              <button
                type="button"
                onClick={() => onFork(message)}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-text-secondary/50 transition-colors hover:bg-bg-hover hover:text-text-secondary"
                title="从此处分叉新对话"
              >
                <GitBranch size={11} />
                分叉
              </button>
            )}
            {feedbackState === 'error' && (
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-accent-red/15 text-accent-red ring-1 ring-accent-red/30 animate-pulse">
                ✕ 反馈保存失败
              </span>
            )}
            {bookmarkState === 'error' && (
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-accent-red/15 text-accent-red ring-1 ring-accent-red/30 animate-pulse">
                ✕ 收藏失败
              </span>
            )}
          </div>
        )}
        {messageTimeLabel && (
          <div className="mt-1 text-[10px] text-text-secondary/45">{messageTimeLabel}</div>
        )}
      </div>
      {reportPreview && (
        <ReportPreviewModal
          open={Boolean(reportPreview)}
          onClose={() => {
            setReportPreview(null)
            setReportError(null)
            setReportState('idle')
          }}
          markdown={reportPreview.markdown}
          title={reportPreview.title}
          sessionId={reportPreview.sessionId}
          artifactId={reportPreview.artifactId}
          answerGroupId={reportPreview.answerGroupId}
          panelId={reportPreview.panelId}
        />
      )}
      <ReportGenerationModal
        open={reportConfigOpen}
        onClose={() => setReportConfigOpen(false)}
        onSubmit={handleGenerateReport}
      />
    </div>
  )
}
