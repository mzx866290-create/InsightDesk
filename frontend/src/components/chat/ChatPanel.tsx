import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { MessageBubble } from './MessageBubble'
import type { Panel, PanelMessage } from '../../stores/chatStore'
import { Bot, Presentation } from 'lucide-react'
import { clearSessionMessages, createSession, getSessionMessages, getSystemPrompts, promotePanelAnswer, streamSingleChat } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'
import type { ActiveStreamControl } from './streamControl'
import { useWorkflowStore } from '../../stores/workflowStore'
import { WorkflowVisualizer } from '../workflow/WorkflowVisualizer'
import { parseWorkflowEvent } from '../../api/workflowClient'
import type { SystemPrompt } from '../../api/client'
import { exportConversationAsMarkdown } from '../../utils/exportConversation'
import { ChatPanelHeader } from './ChatPanelHeader'

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
  isInteractionLocked: boolean
  activeStreamControl: ActiveStreamControl | null
  setActiveStreamControl: (control: ActiveStreamControl | null) => void
  contextLimit?: number
  onStreamingChange: (panelId: string, streaming: boolean) => void
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  panel,
  isStreaming,
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
    appendChunk,
    setAssistantStreaming,
    setSources,
    addErrorMessage,
    setTaskId,
    replaceAssistantMessageByAnswerGroup,
    pushComposerSeed,
    addSession,
    setCurrentSession,
    adjustWorkspaceSessionCount,
    loadMessagesToAllPanels,
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

  const handleFork = async (message: PanelMessage) => {
    if (!currentSessionId) return
    // 找到该消息在列表中的位置，取其之前的所有消息（含该消息）
    const msgIndex = panel.messages.findIndex((m) => m.id === message.id)
    if (msgIndex < 0) return
    const historySlice = panel.messages.slice(0, msgIndex + 1)

    try {
      const session = sessions.find((s) => s.session_id === currentSessionId)
      const forkTitle = `${session?.title ?? '对话'} [分叉]`
      const newSession = await createSession(forkTitle.slice(0, 40), {
        workspace_id: currentWorkspaceId ?? undefined,
      })
      addSession({
        session_id: newSession.session_id,
        title: newSession.title,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
        message_count: historySlice.filter((m) => m.role !== 'error').length,
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
      // 把历史消息加载到所有面板
      loadMessagesToAllPanels(
        historySlice
          .filter((m) => m.role !== 'error')
          .map((m) => ({
            role: m.role as 'user' | 'assistant',
            content: m.content,
            images: m.images,
            files: m.files,
            sources: m.sources,
            model_id: m.modelId,
            answer_group_id: m.answerGroupId,
            task_id: m.taskId,
            task_type: m.taskType,
            workflow_nodes: m.workflowNodes,
          })),
      )
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

  const handlePromote = async (message: PanelMessage) => {
    if (isInteractionLocked) return
    if (!currentSessionId || !message.answerGroupId || !primaryPanelId) return
    await promotePanelAnswer(currentSessionId, message.answerGroupId, panel.id)
    replaceAssistantMessageByAnswerGroup(primaryPanelId, message.answerGroupId, {
      content: message.content,
      sources: message.sources,
      modelId: panel.modelConfig.model,
      taskId: message.taskId,
      taskType: message.taskType,
      workflowNodes: message.workflowNodes,
    })
    if (message.workflowNodes && message.workflowNodes.length > 0) {
      hydrateWorkflow(primaryPanelId, message.workflowNodes)
    }
  }

  const handleRerun = async (message: PanelMessage) => {
    if (isInteractionLocked || isStreaming || !currentSessionId || !message.answerGroupId) return

    const matchedUserMessage = [...panel.messages]
      .reverse()
      .find(
        (candidate) =>
          candidate.role === 'user' && candidate.answerGroupId === message.answerGroupId,
      )

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

    if (!hasOriginalInput) {
      addErrorMessage(
        panel.id,
        '这条回答暂时无法重跑，因为原始输入没有完整保存在当前会话里。',
        'RERUN_INPUT_UNAVAILABLE',
        '如果这是刷新后的纯附件消息，请重新发送一次再试。',
      )
      return
    }

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
  }

  const handleContinue = async (message: PanelMessage) => {
    if (isInteractionLocked || isStreaming || !currentSessionId || !message.answerGroupId) return

    const matchedUserMessage = [...panel.messages]
      .reverse()
      .find(
        (candidate) =>
          candidate.role === 'user' && candidate.answerGroupId === message.answerGroupId,
      )

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
  }

  return (
    <div className="panel-card min-w-0 flex-1 min-h-[22rem] lg:min-h-0 flex flex-col">
      <ChatPanelHeader
        panel={panel}
        canRemove={canRemove}
        isStreaming={isStreaming}
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
                onPromote={handlePromote}
                onRerun={handleRerun}
                canRerun={msg.id === latestAssistantMessageId && !isInteractionLocked}
                onContinue={handleContinue}
                canContinue={msg.id === latestAssistantMessageId && !isInteractionLocked}
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
    </div>
  )
}
