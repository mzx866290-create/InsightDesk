import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { MessageBubble } from './MessageBubble'
import type { Panel, PanelMessage } from '../../stores/chatStore'
import { Bot, Presentation } from 'lucide-react'
import {
  clearSessionMessages,
  createSession,
  getSystemPrompts,
  importSessionMessages,
  promotePanelAnswer,
  streamSingleChat,
} from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'
import type { ActiveStreamControl } from './streamControl'
import { useWorkflowStore } from '../../stores/workflowStore'
import { WorkflowVisualizer } from '../workflow/WorkflowVisualizer'
import { parseWorkflowEvent } from '../../api/workflowClient'
import {
  getAnswerGroupReview,
  promoteRecommendedAnswerGroup,
} from '../../api/client'
import type {
  AnswerGroupReviewResponse,
  ChatFile,
  ChatImage,
  Message,
  PromoteAnswerResponse,
  SystemPrompt,
} from '../../api/client'
import { exportConversationAsMarkdown } from '../../utils/exportConversation'
import { ChatPanelHeader } from './ChatPanelHeader'
import { AnswerReviewModal } from './AnswerReviewModal'

// 默认快捷提问（当角色没有特定提示时使用）
const DEFAULT_STARTERS = [
  '帮我总结知识库里的核心内容',
  '查询最新行业动态',
  '帮我分析上传的文档',
  '生成一份数据可视化仪表盘',
]

// 根据角色名称推断快捷提问
function getStartersForPrompt(prompt: SystemPrompt | null): string[] {
  if (!prompt) return DEFAULT_STARTERS
  const name = prompt.name.toLowerCase()
  if (name.includes('代码') || name.includes('code')) {
    return ['帮我审查这段代码', '解释这个函数的作用', '找出潜在的安全漏洞', '优化代码性能']
  }
  if (name.includes('文档') || name.includes('写作')) {
    return ['帮我撰写技术文档', '优化这段文字的表达', '生成 API 说明文档', '写一份项目 README']
  }
  if (name.includes('简历') || name.includes('hr') || name.includes('招聘')) {
    return ['分析候选人简历', '生成岗位职责描述', '提取简历关键信息', '对比多份简历']
  }
  return DEFAULT_STARTERS
}

function mapMessages(messages: Message[]): PanelMessage[] {
  return messages.map((message, index) => ({
    id: typeof message.id === 'number' ? `db-${message.id}` : `loaded-${index}`,
    serverMessageId: message.id,
    role: message.role,
    content: message.content,
    images: message.images,
    files: message.files,
    sources: message.sources,
    modelId: message.model_id,
    panelId: message.panel_id,
    answerGroupId: message.answer_group_id,
    taskId: message.task_id,
    taskType: message.task_type,
    workflowNodes: message.workflow_nodes,
    timestamp: message.timestamp,
    feedbackValue: message.feedback_value,
  }))
}

function findLatestWorkflowNodes(messages: Message[]) {
  const latestAssistantMessage = [...messages]
    .reverse()
    .find(
      (message) =>
        message.role === 'assistant' && (message.workflow_nodes?.length ?? 0) > 0,
    )

  return latestAssistantMessage?.workflow_nodes ?? []
}

interface EmptyStateProps {
  modelName: string
  activePrompt: SystemPrompt | null
  onSelectStarter: (text: string) => void
}

const EmptyState: React.FC<EmptyStateProps> = ({ modelName, activePrompt, onSelectStarter }) => {
  const starters = getStartersForPrompt(activePrompt)
  return (
    <div className="flex flex-col items-center justify-center h-full text-center gap-4 py-10">
      <div className="w-12 h-12 rounded-2xl bg-accent-blue/10 flex items-center justify-center">
        <Bot size={24} className="text-accent-blue/60" />
      </div>
      <div>
        <p className="text-text-secondary text-sm font-medium">
          {activePrompt ? activePrompt.name : '准备就绪'}
        </p>
        <p className="text-text-secondary/50 text-xs mt-0.5">{modelName}</p>
      </div>
      <div className="grid grid-cols-1 gap-2 w-full max-w-xs mt-1">
        {starters.map((starter) => (
          <button
            key={starter}
            type="button"
            onClick={() => onSelectStarter(starter)}
            className="text-left rounded-xl border border-bg-border bg-bg-tertiary/40 px-3 py-2.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:bg-accent-blue/5 hover:text-text-primary"
          >
            {starter}
          </button>
        ))}
      </div>
    </div>
  )
}

interface ChatPanelProps {
  panel: Panel
  isStreaming: boolean
  loadingElapsedMs: number
  isInteractionLocked: boolean
  activeStreamControl: ActiveStreamControl | null
  setActiveStreamControl: (control: ActiveStreamControl | null) => void
  contextLimit?: number
  onStreamingChange: (panelId: string, streaming: boolean) => void
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  panel,
  isStreaming,
  loadingElapsedMs,
  isInteractionLocked,
  activeStreamControl,
  setActiveStreamControl,
  contextLimit = 16,
  onStreamingChange,
}) => {
  const {
    removePanel,
    panels,
    clearMessages,
    currentSessionId,
    currentWorkspaceId,
    updateSession,
    webSearchEnabled,
    knowledgeBaseEnabled,
    enabledMcpServers,
    appendChunk,
    setAssistantStreaming,
    setSources,
    addErrorMessage,
    setTaskId,
    replaceAssistantMessageByAnswerGroup,
    removeMessage,
    pushComposerSeed,
    addSession,
    setCurrentSession,
    setPanels,
    adjustWorkspaceSessionCount,
    sessions,
    jumpTarget,
    clearJumpTarget,
  } = useChatStore()
  const workflow = useWorkflowStore((s) => s.getWorkflow(panel.id))
  const { setWorkflowVisible, resetWorkflow, hydrateWorkflow, clearWorkflow } = useWorkflowStore()
  const panelBodyRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const rerunAbortControllerRef = useRef<AbortController | null>(null)
  const canRemove = panels.length > 1
  const [confirmClear, setConfirmClear] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [workflowVisible, setWorkflowVisibleLocal] = useState(true)
  const [activePrompt, setActivePrompt] = useState<SystemPrompt | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [deckHintDismissed, setDeckHintDismissed] = useState(false)
  const [reviewAnswerGroupId, setReviewAnswerGroupId] = useState<string | null>(null)
  const [reviewData, setReviewData] = useState<AnswerGroupReviewResponse | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [reviewPromotingPanelId, setReviewPromotingPanelId] = useState<string | null>(null)
  const [reviewPromotingRecommended, setReviewPromotingRecommended] = useState(false)

  useEffect(() => {
    getSystemPrompts()
      .then((list) => {
        const active = list.find((p) => p.is_active) ?? list[0] ?? null
        setActivePrompt(active)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!searchOpen) {
      setSearchQuery('')
    }
  }, [searchOpen])

  // 搜索匹配的消息 id 集合
  const matchedMessageIds = useMemo(() => {
    if (!searchQuery.trim()) return new Set<string>()
    const q = searchQuery.toLowerCase()
    return new Set(
      panel.messages
        .filter((m) => m.role !== 'error' && m.content.toLowerCase().includes(q))
        .map((m) => m.id),
    )
  }, [searchQuery, panel.messages])
  const showDeckHint = !deckHintDismissed && !isStreaming && (() => {
    const assistantMsgs = panel.messages.filter((m) => m.role === 'assistant' && m.content)
    if (assistantMsgs.length < 4) return false
    return assistantMsgs.some((m) => /\n#{1,3} |\|.+\|/.test(m.content))
  })()

  const hasWorkflowActivity = panel.messages.length > 0 && Boolean(
    workflow?.nodes.some(
      (node) =>
        node.status !== 'pending' ||
        Boolean(node.toolName) ||
        Boolean(node.toolResult) ||
        Boolean(node.error),
    ),
  )

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [panel.messages])

  useEffect(() => {
    if (!jumpTarget || jumpTarget.sessionId !== currentSessionId) return

    const container = panelBodyRef.current
    if (!container) return

    let target: HTMLElement | null = null

    if (typeof jumpTarget.messageId === 'number') {
      const byMessageId = container.querySelector<HTMLElement>(
        `[data-server-message-id="${jumpTarget.messageId}"]`,
      )
      if (byMessageId) {
        target = byMessageId
      }
    }

    if (!target && jumpTarget.answerGroupId) {
      if (jumpTarget.role === 'assistant') {
        if (jumpTarget.panelId && jumpTarget.panelId !== panel.id) {
          return
        }
        target = container.querySelector<HTMLElement>(
          `[data-role="assistant"][data-answer-group-id="${jumpTarget.answerGroupId}"]`,
        )
      } else {
        target = container.querySelector<HTMLElement>(
          `[data-role="user"][data-answer-group-id="${jumpTarget.answerGroupId}"]`,
        )
      }
    }

    if (!target) return

    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (typeof target.animate === 'function') {
      target.animate(
        [
          { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(79,142,247,0)' },
          { transform: 'scale(1.01)', boxShadow: '0 0 0 3px rgba(79,142,247,0.28)' },
          { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(79,142,247,0)' },
        ],
        {
          duration: 900,
          easing: 'ease-out',
        },
      )
    }

    clearJumpTarget()
  }, [clearJumpTarget, currentSessionId, jumpTarget, panel.id, panel.messages])

  const handleClearContext = async () => {
    if (isInteractionLocked) return
    if (!confirmClear) {
      setConfirmClear(true)
      setTimeout(() => setConfirmClear(false), 3000)
      return
    }
    setConfirmClear(false)
    setClearing(true)
    try {
      if (currentSessionId) {
        await clearSessionMessages(currentSessionId)
        updateSession(currentSessionId, {
          message_count: 0,
          updated_at: Date.now() / 1000,
        })
      }
      clearMessages()
      panels.forEach((item) => clearWorkflow(item.id))
    } finally {
      setClearing(false)
    }
  }

  const msgCount = panel.messages.filter((m) => m.role !== 'error').length
  const contextUsed = Math.min(msgCount, contextLimit)
  const primaryPanelId = panels[0]?.id
  const isPrimaryPanel = primaryPanelId === panel.id
  const latestAssistantMessageId = [...panel.messages]
    .reverse()
    .find((message) => message.role === 'assistant')?.id
  const isStoppingSingleRunAvailable =
    isStreaming &&
    (
      activeStreamControl?.mode === 'single_rerun' ||
      activeStreamControl?.mode === 'single_continue'
    ) &&
      activeStreamControl.panelId === panel.id

  const applyPromotedAnswer = (payload: PromoteAnswerResponse) => {
    const targetPanelId = payload.target_panel_id?.trim() || primaryPanelId || ''
    const answerGroupId = payload.answer_group_id?.trim()
    if (!targetPanelId || !answerGroupId) return

    replaceAssistantMessageByAnswerGroup(targetPanelId, answerGroupId, {
      content: payload.content,
      sources: payload.sources ?? [],
      modelId: payload.model_id,
      taskId: payload.task_id,
      taskType: payload.task_type,
      workflowNodes: payload.workflow_nodes ?? [],
    })
    if (payload.workflow_nodes && payload.workflow_nodes.length > 0) {
      hydrateWorkflow(targetPanelId, payload.workflow_nodes)
    }
    touchSession()
  }

  const loadAnswerReview = async (answerGroupId: string) => {
    if (!currentSessionId) return
    setReviewLoading(true)
    setReviewError(null)
    try {
      const payload = await getAnswerGroupReview(currentSessionId, answerGroupId)
      setReviewData(payload)
    } catch (error) {
      setReviewError((error as Error).message || '加载答案评审失败')
      setReviewData(null)
    } finally {
      setReviewLoading(false)
    }
  }

  const handleOpenAnswerReview = async (message: PanelMessage) => {
    if (!currentSessionId || !message.answerGroupId) return
    setReviewAnswerGroupId(message.answerGroupId)
    setReviewData(null)
    setReviewError(null)
    await loadAnswerReview(message.answerGroupId)
  }

  const handleRefreshAnswerReview = async () => {
    if (!reviewAnswerGroupId) return
    await loadAnswerReview(reviewAnswerGroupId)
  }

  const handlePromoteReviewedPanel = async (sourcePanelId: string) => {
    if (!currentSessionId || !reviewAnswerGroupId) return
    setReviewPromotingPanelId(sourcePanelId)
    setReviewError(null)
    try {
      const payload = await promotePanelAnswer(currentSessionId, reviewAnswerGroupId, sourcePanelId)
      applyPromotedAnswer(payload)
      setReviewAnswerGroupId(null)
    } catch (error) {
      setReviewError((error as Error).message || '设置主答案失败')
    } finally {
      setReviewPromotingPanelId(null)
    }
  }

  const handlePromoteRecommendedAnswer = async () => {
    if (!currentSessionId || !reviewAnswerGroupId) return
    setReviewPromotingRecommended(true)
    setReviewError(null)
    try {
      const payload = await promoteRecommendedAnswerGroup(currentSessionId, reviewAnswerGroupId)
      applyPromotedAnswer(payload)
      setReviewAnswerGroupId(null)
    } catch (error) {
      setReviewError((error as Error).message || '采用推荐答案失败')
    } finally {
      setReviewPromotingRecommended(false)
    }
  }

  const handleFork = async (message: PanelMessage) => {
    if (!currentSessionId) return
    const msgIndex = panel.messages.findIndex((m) => m.id === message.id)
    if (msgIndex < 0) return
    const historySlice = panel.messages.slice(0, msgIndex + 1)

    try {
      const session = sessions.find((s) => s.session_id === currentSessionId)
      const forkTitle = `${session?.title ?? '对话'} [分叉]`
      const newSession = await createSession(forkTitle.slice(0, 40), {
        workspace_id: currentWorkspaceId ?? undefined,
      })
      const imported = await importSessionMessages(newSession.session_id, {
        panels: panels.map((item) => item.modelConfig),
        messages: historySlice
          .filter((item) => item.role !== 'error')
          .map((item) => ({
            role: item.role as 'user' | 'assistant',
            content: item.content,
            images: item.images,
            files: item.files,
            sources: item.sources,
            model_id: item.modelId,
            panel_id: item.role === 'assistant' ? panel.id : undefined,
            answer_group_id: item.answerGroupId,
            task_id: item.taskId,
            task_type: item.taskType,
            workflow_nodes: item.workflowNodes,
          })),
      })

      addSession({
        session_id: newSession.session_id,
        title: newSession.title,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
        message_count: imported.total_messages,
        is_archived: false,
        is_favorite: false,
        is_pinned: false,
        session_order: 0,
        tags: [],
        workspace_id: newSession.workspace_id ?? currentWorkspaceId ?? 'workspace-default',
      })
      adjustWorkspaceSessionCount(
        newSession.workspace_id ?? currentWorkspaceId ?? 'workspace-default',
        1,
      )
      setCurrentSession(newSession.session_id)

      if (imported.panels && imported.panels.length > 0) {
        const nextPanelIds = new Set(imported.panels.map((item) => item.panel_id))
        setPanels(
          imported.panels.map((item) => ({
            id: item.panel_id,
            modelConfig: item.model_config,
            messages: mapMessages(imported.panel_messages?.[item.panel_id] ?? imported.messages),
          })),
        )
        imported.panels.forEach((item) => {
          const restoredMessages = imported.panel_messages?.[item.panel_id] ?? imported.messages
          const workflowNodes = findLatestWorkflowNodes(restoredMessages)
          if (workflowNodes.length > 0) {
            hydrateWorkflow(item.panel_id, workflowNodes)
          } else {
            clearWorkflow(item.panel_id)
          }
        })
        panels.forEach((item) => {
          if (!nextPanelIds.has(item.id)) {
            clearWorkflow(item.id)
          }
        })
      }

      updateSession(newSession.session_id, {
        message_count: imported.total_messages,
        updated_at: Date.now() / 1000,
      })
    } catch (e) {
      console.error('分叉失败', e)
    }
  }

  const touchSession = () => {
    if (!currentSessionId) return
    updateSession(currentSessionId, {
      updated_at: Date.now() / 1000,
    })
  }

  const findUserMessageByAnswerGroup = (answerGroupId: string) =>
    [...panel.messages]
      .reverse()
      .find(
        (candidate) =>
          candidate.role === 'user' && candidate.answerGroupId === answerGroupId,
      )

  const findAssistantMessageByAnswerGroup = (answerGroupId: string) =>
    [...panel.messages]
      .reverse()
      .find(
        (candidate) =>
          candidate.role === 'assistant' && candidate.answerGroupId === answerGroupId,
      )

  const hasRunnableInput = (message: PanelMessage | undefined): message is PanelMessage =>
    Boolean(
      message &&
      (
        message.content.trim().length > 0 ||
        (message.images?.length ?? 0) > 0 ||
        (message.files?.length ?? 0) > 0
      ),
    )

  const classifySingleStreamFailure = (
    error: string,
    fallbackMessage: string,
    requestFailedSuggestion: string,
  ) => {
    const normalizedError = error.trim() || fallbackMessage
    const isNetworkError = /failed to fetch|network|backend returned an empty response body/i.test(
      normalizedError,
    )
    const isTimeoutError = /timeout|timed out|504|超时/i.test(normalizedError)

    return {
      content: isNetworkError
        ? 'Network connection failed. Unable to reach the backend service.'
        : isTimeoutError
          ? 'The request timed out before the model finished responding.'
          : normalizedError,
      errorCode: isNetworkError ? 'NETWORK_ERROR' : isTimeoutError ? 'TIMEOUT' : 'REQUEST_FAILED',
      suggestion: isNetworkError || isTimeoutError ? undefined : requestFailedSuggestion,
    }
  }

  type SinglePanelRetryMode = NonNullable<PanelMessage['retryMode']>
  interface SinglePanelStreamOptions {
    answerGroupId: string
    prompt: string
    images: ChatImage[]
    files: ChatFile[]
    existingAssistantMessage?: PanelMessage
    activeMode: Extract<ActiveStreamControl['mode'], 'single_rerun' | 'single_continue'>
    retryMode: SinglePanelRetryMode
    sseErrorFallback: string
    requestErrorFallback: string
    requestFailedSuggestion: string
  }

  const runSinglePanelStream = ({
    answerGroupId,
    prompt,
    images,
    files,
    existingAssistantMessage,
    activeMode,
    retryMode,
    sseErrorFallback,
    requestErrorFallback,
    requestFailedSuggestion,
  }: SinglePanelStreamOptions) => {
    if (isInteractionLocked || isStreaming || !currentSessionId) return

    const targetMessageId =
      existingAssistantMessage?.id ?? `assistant-${panel.id}-${Date.now()}`
    const previousAssistantState = existingAssistantMessage
      ? {
          content: existingAssistantMessage.content,
          sources: existingAssistantMessage.sources,
          modelId: existingAssistantMessage.modelId,
          taskId: existingAssistantMessage.taskId,
          taskType: existingAssistantMessage.taskType,
          workflowNodes: existingAssistantMessage.workflowNodes,
          timestamp: existingAssistantMessage.timestamp,
        }
      : null
    const assistantMeta = {
      answerGroupId,
      modelId: panel.modelConfig.model,
    }

    const hasVisibleAssistantState = (): boolean => {
      const currentPanel = useChatStore.getState().panels.find((item) => item.id === panel.id)
      const currentMessage = currentPanel?.messages.find(
        (item) => item.id === targetMessageId && item.role === 'assistant',
      )
      return Boolean(
        currentMessage &&
        (
          currentMessage.content.trim().length > 0 ||
          (currentMessage.sources?.length ?? 0) > 0 ||
          currentMessage.taskId
        ),
      )
    }

    const restorePreviousAssistant = () => {
      if (!previousAssistantState) {
        removeMessage(panel.id, targetMessageId)
        clearWorkflow(panel.id)
        return
      }

      replaceAssistantMessageByAnswerGroup(panel.id, answerGroupId, {
        ...previousAssistantState,
        streaming: false,
      })
      if (previousAssistantState.workflowNodes && previousAssistantState.workflowNodes.length > 0) {
        hydrateWorkflow(panel.id, previousAssistantState.workflowNodes)
      } else {
        clearWorkflow(panel.id)
      }
    }

    const stopCurrentSingleRun = () => {
      rerunAbortControllerRef.current?.abort()
      rerunAbortControllerRef.current = null
      if (hasVisibleAssistantState()) {
        setAssistantStreaming(panel.id, targetMessageId, false)
      } else {
        restorePreviousAssistant()
      }
      onStreamingChange(panel.id, false)
      setActiveStreamControl(null)
      touchSession()
    }

    if (existingAssistantMessage) {
      replaceAssistantMessageByAnswerGroup(panel.id, answerGroupId, {
        content: '',
        sources: [],
        modelId: panel.modelConfig.model,
        streaming: true,
        taskId: undefined,
        taskType: undefined,
        workflowNodes: undefined,
        timestamp: Date.now() / 1000,
      })
    } else {
      appendChunk(panel.id, targetMessageId, '', assistantMeta)
    }
    resetWorkflow(panel.id)
    onStreamingChange(panel.id, true)

    const controller = streamSingleChat(
      currentSessionId,
      prompt,
      panel.modelConfig,
      webSearchEnabled,
      knowledgeBaseEnabled,
      enabledMcpServers,
      images,
      files,
      answerGroupId,
      true,
      (chunk) => {
        if (chunk.panel_id !== panel.id) return

        const workflowEvent = parseWorkflowEvent(chunk)
        if (workflowEvent) {
          useWorkflowStore.getState().updateNodeStatus(
            panel.id,
            workflowEvent.node_name,
            workflowEvent.status,
            {
              toolName: workflowEvent.tool_name,
              toolParams: workflowEvent.tool_params,
              toolResult: workflowEvent.tool_result_summary,
              retrievalMeta: workflowEvent.retrieval_meta,
              error: workflowEvent.error,
            },
          )
          return
        }

        if (chunk.type === 'chunk' && chunk.content) {
          appendChunk(panel.id, targetMessageId, chunk.content, assistantMeta)
          return
        }

        if (chunk.type === 'sources' && chunk.sources) {
          setSources(panel.id, targetMessageId, chunk.sources, assistantMeta)
          return
        }

        if (chunk.type === 'task_created' && chunk.task_id) {
          const taskStore = useTaskStore.getState()
          taskStore.addTask({
            task_id: chunk.task_id,
            task_type: chunk.task_type ?? 'task',
            status: 'pending',
            progress: 0,
            created_at: Date.now() / 1000,
            updated_at: Date.now() / 1000,
          })
          taskStore.startPolling(chunk.task_id)
          setTaskId(panel.id, targetMessageId, chunk.task_id, chunk.task_type)
          return
        }

        if (chunk.type === 'done') {
          const workflowSnapshot = useWorkflowStore.getState().getWorkflow(panel.id)?.nodes
          if (workflowSnapshot && workflowSnapshot.length > 0) {
            replaceAssistantMessageByAnswerGroup(panel.id, answerGroupId, {
              workflowNodes: workflowSnapshot,
            })
          }
          rerunAbortControllerRef.current = null
          setAssistantStreaming(panel.id, targetMessageId, false)
          onStreamingChange(panel.id, false)
          setActiveStreamControl(null)
          touchSession()
          return
        }

        if (chunk.type === 'error') {
          rerunAbortControllerRef.current = null
          restorePreviousAssistant()
          addErrorMessage(
            panel.id,
            chunk.content ?? sseErrorFallback,
            chunk.error_code,
            chunk.suggestion,
            {
              answerGroupId,
              retryMode,
            },
          )
          onStreamingChange(panel.id, false)
          setActiveStreamControl(null)
        }
      },
      () => {
        rerunAbortControllerRef.current = null
        setAssistantStreaming(panel.id, targetMessageId, false)
        onStreamingChange(panel.id, false)
        setActiveStreamControl(null)
      },
      (err) => {
        rerunAbortControllerRef.current = null
        restorePreviousAssistant()
        const failure = classifySingleStreamFailure(
          err ?? '',
          requestErrorFallback,
          requestFailedSuggestion,
        )
        addErrorMessage(
          panel.id,
          failure.content,
          failure.errorCode,
          failure.suggestion,
          {
            answerGroupId,
            retryMode,
          },
        )
        onStreamingChange(panel.id, false)
        setActiveStreamControl(null)
      },
    )

    rerunAbortControllerRef.current = controller
    setActiveStreamControl({
      mode: activeMode,
      panelId: panel.id,
      stop: stopCurrentSingleRun,
    })
  }

  const handlePromote = async (message: PanelMessage) => {
    if (isInteractionLocked) return
    if (!currentSessionId || !message.answerGroupId || !primaryPanelId) return
    const payload = await promotePanelAnswer(currentSessionId, message.answerGroupId, panel.id)
    applyPromotedAnswer(payload)
  }

  const handleRerun = async (message: PanelMessage) => {
    if (isInteractionLocked || isStreaming || !currentSessionId || !message.answerGroupId) return

    const matchedUserMessage = findUserMessageByAnswerGroup(message.answerGroupId)

    if (!matchedUserMessage) {
      addErrorMessage(
        panel.id,
        '无法重新生成这条回答，因为没有找到对应的用户提问。',
        'RERUN_CONTEXT_MISSING',
        '请重新发送这条问题后再试。',
      )
      return
    }

    const hasOriginalInput =
      matchedUserMessage.content.trim().length > 0 ||
      (matchedUserMessage.images?.length ?? 0) > 0 ||
      (matchedUserMessage.files?.length ?? 0) > 0

    if (!hasRunnableInput(matchedUserMessage)) {
      addErrorMessage(
        panel.id,
        '这条回答暂时无法重跑，因为原始输入没有完整保存在当前会话里。',
        'RERUN_INPUT_UNAVAILABLE',
        '如果这是刷新后的纯附件消息，请重新发送一次再试。',
      )
      return
    }

    runSinglePanelStream({
      answerGroupId: message.answerGroupId,
      prompt: matchedUserMessage.content,
      images: matchedUserMessage.images ?? [],
      files: matchedUserMessage.files ?? [],
      existingAssistantMessage: message,
      activeMode: 'single_rerun',
      retryMode: 'rerun',
      sseErrorFallback: 'Single-model rerun failed.',
      requestErrorFallback: 'Single-model rerun failed.',
      requestFailedSuggestion: 'Please try again later, or resend this question.',
    })
    return
    /*
    const previousAssistantState = {
      content: message.content,
      sources: message.sources,
      modelId: message.modelId,
      taskId: message.taskId,
      taskType: message.taskType,
      workflowNodes: message.workflowNodes,
    }
    const assistantMeta = {
      answerGroupId: message.answerGroupId,
      modelId: panel.modelConfig.model,
    }
    const hasVisibleAssistantState = (): boolean => {
      const currentPanel = useChatStore.getState().panels.find((item) => item.id === panel.id)
      const currentMessage = currentPanel?.messages.find(
        (item) => item.id === message.id && item.role === 'assistant',
      )
      return Boolean(
        currentMessage &&
        (
          currentMessage.content.trim().length > 0 ||
          (currentMessage.sources?.length ?? 0) > 0 ||
          currentMessage.taskId
        ),
      )
    }
    const restorePreviousAssistant = () => {
      replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId!, {
        ...previousAssistantState,
        streaming: false,
      })
      if (previousAssistantState.workflowNodes && previousAssistantState.workflowNodes.length > 0) {
        hydrateWorkflow(panel.id, previousAssistantState.workflowNodes)
      } else {
        clearWorkflow(panel.id)
      }
    }
    const stopCurrentRerun = () => {
      rerunAbortControllerRef.current?.abort()
      rerunAbortControllerRef.current = null
      if (hasVisibleAssistantState()) {
        setAssistantStreaming(panel.id, message.id, false)
      } else {
        restorePreviousAssistant()
      }
      onStreamingChange(panel.id, false)
      setActiveStreamControl(null)
      touchSession()
    }

    replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId, {
      content: '',
      sources: [],
      modelId: panel.modelConfig.model,
      streaming: true,
      taskId: undefined,
      taskType: undefined,
      workflowNodes: undefined,
      timestamp: Date.now() / 1000,
    })
    resetWorkflow(panel.id)
    onStreamingChange(panel.id, true)

    const controller = streamSingleChat(
      currentSessionId,
      matchedUserMessage.content,
      panel.modelConfig,
      webSearchEnabled,
      knowledgeBaseEnabled,
      enabledMcpServers,
      matchedUserMessage.images ?? [],
      matchedUserMessage.files ?? [],
      message.answerGroupId,
      true,
      (chunk) => {
        if (chunk.panel_id !== panel.id) return

        const workflowEvent = parseWorkflowEvent(chunk)
        if (workflowEvent) {
          useWorkflowStore.getState().updateNodeStatus(
            panel.id,
            workflowEvent.node_name,
            workflowEvent.status,
            {
              toolName: workflowEvent.tool_name,
              toolParams: workflowEvent.tool_params,
              toolResult: workflowEvent.tool_result_summary,
              retrievalMeta: workflowEvent.retrieval_meta,
              error: workflowEvent.error,
            },
          )
          return
        }

        if (chunk.type === 'chunk' && chunk.content) {
          appendChunk(panel.id, message.id, chunk.content, assistantMeta)
          return
        }

        if (chunk.type === 'sources' && chunk.sources) {
          setSources(panel.id, message.id, chunk.sources, assistantMeta)
          return
        }

        if (chunk.type === 'task_created' && chunk.task_id) {
          const taskStore = useTaskStore.getState()
          taskStore.addTask({
            task_id: chunk.task_id,
            task_type: chunk.task_type ?? 'task',
            status: 'pending',
            progress: 0,
            created_at: Date.now() / 1000,
            updated_at: Date.now() / 1000,
          })
          taskStore.startPolling(chunk.task_id)
          setTaskId(panel.id, message.id, chunk.task_id, chunk.task_type)
          return
        }

        if (chunk.type === 'done') {
          const workflowSnapshot = useWorkflowStore.getState().getWorkflow(panel.id)?.nodes
          if (workflowSnapshot && workflowSnapshot.length > 0) {
            replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId!, {
              workflowNodes: workflowSnapshot,
            })
          }
          rerunAbortControllerRef.current = null
          setAssistantStreaming(panel.id, message.id, false)
          onStreamingChange(panel.id, false)
          setActiveStreamControl(null)
          touchSession()
          return
        }

        if (chunk.type === 'error') {
          rerunAbortControllerRef.current = null
          restorePreviousAssistant()
          addErrorMessage(
            panel.id,
            chunk.content ?? '单模型重跑失败。',
            chunk.error_code,
            chunk.suggestion,
          )
          onStreamingChange(panel.id, false)
          setActiveStreamControl(null)
        }
      },
      () => {
        rerunAbortControllerRef.current = null
        setAssistantStreaming(panel.id, message.id, false)
        onStreamingChange(panel.id, false)
        setActiveStreamControl(null)
      },
      (err) => {
        rerunAbortControllerRef.current = null
        restorePreviousAssistant()
        const normalizedError = err?.trim() || '单模型重跑失败。'
        const isNetworkError = /failed to fetch|network|backend returned an empty response body/i.test(
          normalizedError,
        )
        addErrorMessage(
          panel.id,
          isNetworkError
            ? '网络连接失败，暂时无法联系后端服务。'
            : normalizedError,
          isNetworkError ? 'NETWORK_ERROR' : 'REQUEST_FAILED',
          isNetworkError
            ? '请检查网络连接，并确认后端服务正在运行。'
            : '请稍后重试，或重新发送这条问题。',
        )
        onStreamingChange(panel.id, false)
        setActiveStreamControl(null)
      },
    )
    rerunAbortControllerRef.current = controller
    setActiveStreamControl({
      mode: 'single_rerun',
      panelId: panel.id,
      stop: stopCurrentRerun,
    })
    */
  }

  /*
  const handleRetryError = async (message: PanelMessage) => {
    if (isInteractionLocked || isStreaming || !currentSessionId || !message.answerGroupId) return

    const matchedAssistantMessage = findAssistantMessageByAnswerGroup(message.answerGroupId)
    if (message.retryMode === 'continue' && matchedAssistantMessage) {
      await handleContinue(matchedAssistantMessage)
      return
    }

    if (matchedAssistantMessage) {
      await handleRerun(matchedAssistantMessage)
      return
    }

    const matchedUserMessage = findUserMessageByAnswerGroup(message.answerGroupId)
    if (!matchedUserMessage) {
      addErrorMessage(
        panel.id,
        '鏃犳硶閲嶆柊鐢熸垚杩欐潯鍥炵瓟锛屽洜涓烘病鏈夋壘鍒板搴旂殑鐢ㄦ埛鎻愰棶銆?,
        'RERUN_CONTEXT_MISSING',
        '璇烽噸鏂板彂閫佽繖鏉￠棶棰樺悗鍐嶈瘯銆?,
      )
      return
    }

    if (!hasRunnableInput(matchedUserMessage)) {
      addErrorMessage(
        panel.id,
        '杩欐潯鍥炵瓟鏆傛椂鏃犳硶閲嶈窇锛屽洜涓哄師濮嬭緭鍏ユ病鏈夊畬鏁翠繚瀛樺湪褰撳墠浼氳瘽閲屻€?,
        'RERUN_INPUT_UNAVAILABLE',
        '濡傛灉杩欐槸鍒锋柊鍚庣殑绾檮浠舵秷鎭紝璇烽噸鏂板彂閫佷竴娆″啀璇曘€?,
      )
      return
    }

    runSinglePanelStream({
      answerGroupId: message.answerGroupId,
      prompt: matchedUserMessage.content,
      images: matchedUserMessage.images ?? [],
      files: matchedUserMessage.files ?? [],
      activeMode: 'single_rerun',
      retryMode: 'rerun',
      sseErrorFallback: 'Single-model rerun failed.',
      requestErrorFallback: 'Single-model rerun failed.',
      requestFailedSuggestion: 'Please try again later, or resend this question.',
    })
  }

  */

  const handleRetryError = async (message: PanelMessage) => {
    if (isInteractionLocked || isStreaming || !currentSessionId || !message.answerGroupId) return

    const matchedAssistantMessage = findAssistantMessageByAnswerGroup(message.answerGroupId)
    if (message.retryMode === 'continue' && matchedAssistantMessage) {
      await handleContinue(matchedAssistantMessage)
      return
    }

    if (matchedAssistantMessage) {
      await handleRerun(matchedAssistantMessage)
      return
    }

    const matchedUserMessage = findUserMessageByAnswerGroup(message.answerGroupId)
    if (!matchedUserMessage) {
      addErrorMessage(
        panel.id,
        'Unable to retry this answer because the original user message could not be found.',
        'RERUN_CONTEXT_MISSING',
        'Please resend this question and try again.',
      )
      return
    }

    if (!hasRunnableInput(matchedUserMessage)) {
      addErrorMessage(
        panel.id,
        'This answer cannot be rerun because the original input is no longer available in this session.',
        'RERUN_INPUT_UNAVAILABLE',
        'If this came from a refreshed session, please resend the original question once and retry.',
      )
      return
    }

    runSinglePanelStream({
      answerGroupId: message.answerGroupId,
      prompt: matchedUserMessage.content,
      images: matchedUserMessage.images ?? [],
      files: matchedUserMessage.files ?? [],
      activeMode: 'single_rerun',
      retryMode: 'rerun',
      sseErrorFallback: 'Single-model rerun failed.',
      requestErrorFallback: 'Single-model rerun failed.',
      requestFailedSuggestion: 'Please try again later, or resend this question.',
    })
  }

  const handleContinue = async (message: PanelMessage) => {
    if (isInteractionLocked || isStreaming || !currentSessionId || !message.answerGroupId) return

    const matchedUserMessage = findUserMessageByAnswerGroup(message.answerGroupId)

    if (!matchedUserMessage) {
      addErrorMessage(
        panel.id,
        '无法继续这条回答，因为没有找到对应的用户提问。',
        'CONTINUE_CONTEXT_MISSING',
        '请先重试该问题，或重新发送一次提问。',
      )
      return
    }

    const currentAnswer = message.content.trim()
    if (!currentAnswer) {
      addErrorMessage(
        panel.id,
        '当前回答内容为空，无法继续生成。',
        'CONTINUE_EMPTY_ANSWER',
        '请先重跑该回答，再尝试继续生成。',
      )
      return
    }

    const continuePromptParts: string[] = []
    if (matchedUserMessage.content.trim()) {
      continuePromptParts.push(`用户原始问题：\n${matchedUserMessage.content.trim()}`)
    }
    continuePromptParts.push(`你上一条回答（可能未完成）：\n${currentAnswer}`)
    continuePromptParts.push(
      '请在不丢失已有内容的前提下继续补全答案，并只返回“完整合并后的最终答案”。不要重复无关开场，不要解释过程，直接给最终内容。',
    )
    const continuePrompt = continuePromptParts.join('\n\n')

    runSinglePanelStream({
      answerGroupId: message.answerGroupId,
      prompt: continuePrompt,
      images: matchedUserMessage.images ?? [],
      files: matchedUserMessage.files ?? [],
      existingAssistantMessage: message,
      activeMode: 'single_continue',
      retryMode: 'continue',
      sseErrorFallback: 'Continue generation failed.',
      requestErrorFallback: 'Continue generation failed.',
      requestFailedSuggestion: 'Please try again later, or switch to rerun for this panel.',
    })
    return
    /*
    const previousAssistantState = {
      content: message.content,
      sources: message.sources,
      modelId: message.modelId,
      taskId: message.taskId,
      taskType: message.taskType,
      workflowNodes: message.workflowNodes,
      timestamp: message.timestamp,
    }
    const assistantMeta = {
      answerGroupId: message.answerGroupId,
      modelId: panel.modelConfig.model,
    }
    const hasVisibleAssistantState = (): boolean => {
      const currentPanel = useChatStore.getState().panels.find((item) => item.id === panel.id)
      const currentMessage = currentPanel?.messages.find(
        (item) => item.id === message.id && item.role === 'assistant',
      )
      return Boolean(
        currentMessage &&
        (
          currentMessage.content.trim().length > 0 ||
          (currentMessage.sources?.length ?? 0) > 0 ||
          currentMessage.taskId
        ),
      )
    }
    const restorePreviousAssistant = () => {
      replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId!, {
        ...previousAssistantState,
        streaming: false,
      })
      if (previousAssistantState.workflowNodes && previousAssistantState.workflowNodes.length > 0) {
        hydrateWorkflow(panel.id, previousAssistantState.workflowNodes)
      } else {
        clearWorkflow(panel.id)
      }
    }
    const stopCurrentContinue = () => {
      rerunAbortControllerRef.current?.abort()
      rerunAbortControllerRef.current = null
      if (hasVisibleAssistantState()) {
        setAssistantStreaming(panel.id, message.id, false)
      } else {
        restorePreviousAssistant()
      }
      onStreamingChange(panel.id, false)
      setActiveStreamControl(null)
      touchSession()
    }

    replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId, {
      content: '',
      sources: [],
      modelId: panel.modelConfig.model,
      streaming: true,
      taskId: undefined,
      taskType: undefined,
      workflowNodes: undefined,
      timestamp: Date.now() / 1000,
    })
    resetWorkflow(panel.id)
    onStreamingChange(panel.id, true)

    const controller = streamSingleChat(
      currentSessionId,
      continuePrompt,
      panel.modelConfig,
      webSearchEnabled,
      knowledgeBaseEnabled,
      enabledMcpServers,
      matchedUserMessage.images ?? [],
      matchedUserMessage.files ?? [],
      message.answerGroupId,
      true,
      (chunk) => {
        if (chunk.panel_id !== panel.id) return

        const workflowEvent = parseWorkflowEvent(chunk)
        if (workflowEvent) {
          useWorkflowStore.getState().updateNodeStatus(
            panel.id,
            workflowEvent.node_name,
            workflowEvent.status,
            {
              toolName: workflowEvent.tool_name,
              toolParams: workflowEvent.tool_params,
              toolResult: workflowEvent.tool_result_summary,
              retrievalMeta: workflowEvent.retrieval_meta,
              error: workflowEvent.error,
            },
          )
          return
        }

        if (chunk.type === 'chunk' && chunk.content) {
          appendChunk(panel.id, message.id, chunk.content, assistantMeta)
          return
        }

        if (chunk.type === 'sources' && chunk.sources) {
          setSources(panel.id, message.id, chunk.sources, assistantMeta)
          return
        }

        if (chunk.type === 'task_created' && chunk.task_id) {
          const taskStore = useTaskStore.getState()
          taskStore.addTask({
            task_id: chunk.task_id,
            task_type: chunk.task_type ?? 'task',
            status: 'pending',
            progress: 0,
            created_at: Date.now() / 1000,
            updated_at: Date.now() / 1000,
          })
          taskStore.startPolling(chunk.task_id)
          setTaskId(panel.id, message.id, chunk.task_id, chunk.task_type)
          return
        }

        if (chunk.type === 'done') {
          const workflowSnapshot = useWorkflowStore.getState().getWorkflow(panel.id)?.nodes
          if (workflowSnapshot && workflowSnapshot.length > 0) {
            replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId!, {
              workflowNodes: workflowSnapshot,
            })
          }
          rerunAbortControllerRef.current = null
          setAssistantStreaming(panel.id, message.id, false)
          onStreamingChange(panel.id, false)
          setActiveStreamControl(null)
          touchSession()
          return
        }

        if (chunk.type === 'error') {
          rerunAbortControllerRef.current = null
          restorePreviousAssistant()
          addErrorMessage(
            panel.id,
            chunk.content ?? '继续生成失败。',
            chunk.error_code,
            chunk.suggestion,
          )
          onStreamingChange(panel.id, false)
          setActiveStreamControl(null)
        }
      },
      () => {
        rerunAbortControllerRef.current = null
        setAssistantStreaming(panel.id, message.id, false)
        onStreamingChange(panel.id, false)
        setActiveStreamControl(null)
      },
      (err) => {
        rerunAbortControllerRef.current = null
        restorePreviousAssistant()
        const normalizedError = err?.trim() || '继续生成失败。'
        const isNetworkError = /failed to fetch|network|backend returned an empty response body/i.test(
          normalizedError,
        )
        addErrorMessage(
          panel.id,
          isNetworkError
            ? '网络连接失败，暂时无法联系后端服务。'
            : normalizedError,
          isNetworkError ? 'NETWORK_ERROR' : 'REQUEST_FAILED',
          isNetworkError
            ? '请检查网络连接，并确认后端服务正在运行。'
            : '请稍后重试，或改用“仅重跑此模型”。',
        )
        onStreamingChange(panel.id, false)
        setActiveStreamControl(null)
      },
    )
    rerunAbortControllerRef.current = controller
    setActiveStreamControl({
      mode: 'single_continue',
      panelId: panel.id,
      stop: stopCurrentContinue,
    })
    */
  }

  return (
    <div
      className="panel-card min-w-0 flex-1 min-h-[22rem] lg:min-h-0 flex flex-col"
      data-testid="chat-panel"
      data-panel-id={panel.id}
    >
      <ChatPanelHeader
        panel={panel}
        canRemove={canRemove}
        isStreaming={isStreaming}
        loadingElapsedMs={loadingElapsedMs}
        isInteractionLocked={isInteractionLocked}
        isStoppingSingleRunAvailable={isStoppingSingleRunAvailable}
        activeStreamControl={activeStreamControl}
        msgCount={msgCount}
        contextUsed={contextUsed}
        contextLimit={contextLimit}
        hasWorkflowActivity={hasWorkflowActivity}
        workflowVisible={workflowVisible}
        searchOpen={searchOpen}
        searchQuery={searchQuery}
        matchedCount={matchedMessageIds.size}
        confirmClear={confirmClear}
        clearing={clearing}
        onRemovePanel={() => removePanel(panel.id)}
        onToggleWorkflowVisible={() => {
          setWorkflowVisibleLocal(!workflowVisible)
          setWorkflowVisible(panel.id, !workflowVisible)
        }}
        onToggleSearch={() => setSearchOpen((v) => !v)}
        onSearchQueryChange={setSearchQuery}
        onClearContext={handleClearContext}
        onExport={() => {
          const currentSession = sessions.find((s) => s.session_id === currentSessionId) ?? null
          exportConversationAsMarkdown(currentSession, panel.messages, panel.modelConfig.model)
        }}
      />

      {/* Workflow Visualizer */}
      {workflowVisible && hasWorkflowActivity && (
        <div className="px-4 py-3 border-b border-bg-border/50 bg-bg-secondary/30 shrink-0">
          <WorkflowVisualizer panelId={panel.id} />
        </div>
      )}

      {/* Messages */}
      <div ref={panelBodyRef} className="min-h-[14rem] flex-1 overflow-y-auto overflow-x-hidden px-4 py-4 lg:min-h-0 flex flex-col">
        {panel.messages.length === 0 ? (
          <EmptyState
            modelName={panel.modelConfig.model}
            activePrompt={activePrompt}
            onSelectStarter={(text) => pushComposerSeed({ text })}
          />
        ) : (
          panel.messages.map((msg) => (
            <div
              key={msg.id}
              className={
                searchQuery && matchedMessageIds.size > 0
                  ? matchedMessageIds.has(msg.id)
                    ? 'ring-1 ring-accent-blue/40 rounded-xl'
                    : 'opacity-40'
                  : ''
              }
            >
              <MessageBubble
                message={msg}
                panelId={panel.id}
                isPrimaryPanel={isPrimaryPanel}
                interactionLocked={isInteractionLocked}
                onReview={handleOpenAnswerReview}
                onPromote={handlePromote}
                onRerun={handleRerun}
                canRerun={msg.id === latestAssistantMessageId && !isInteractionLocked}
                onContinue={handleContinue}
                canContinue={msg.id === latestAssistantMessageId && !isInteractionLocked}
                onRetryError={msg.role === 'error' ? handleRetryError : undefined}
                onFork={msg.role === 'assistant' && !isInteractionLocked ? handleFork : undefined}
              />
            </div>
          ))
        )}
        {showDeckHint && (
          <div className="mx-4 mb-3 flex items-center gap-3 rounded-2xl border border-accent-orange/30 bg-accent-orange/8 px-4 py-2.5 text-xs">
            <Presentation size={14} className="shrink-0 text-accent-orange" />
            <span className="flex-1 text-text-secondary">
              检测到结构化内容——点击工具栏「<span className="font-medium text-text-primary">更多 → 生成演示稿</span>」可一键导出 PPT。
            </span>
            <button
              type="button"
              onClick={() => setDeckHintDismissed(true)}
              className="shrink-0 text-text-secondary/50 hover:text-text-secondary"
              title="关闭提示"
            >
              ✕
            </button>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <AnswerReviewModal
        open={Boolean(reviewAnswerGroupId)}
        review={reviewData}
        loading={reviewLoading}
        error={reviewError}
        primaryPanelId={primaryPanelId}
        promotingPanelId={reviewPromotingPanelId}
        promotingRecommended={reviewPromotingRecommended}
        onClose={() => {
          setReviewAnswerGroupId(null)
          setReviewData(null)
          setReviewError(null)
          setReviewPromotingPanelId(null)
          setReviewPromotingRecommended(false)
        }}
        onRefresh={() => {
          void handleRefreshAnswerReview()
        }}
        onPromotePanel={(sourcePanelId) => {
          void handlePromoteReviewedPanel(sourcePanelId)
        }}
        onPromoteRecommended={() => {
          void handlePromoteRecommendedAnswer()
        }}
      />
    </div>
  )
}
