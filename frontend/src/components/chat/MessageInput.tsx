import React, { useEffect, useRef, useState } from 'react'
import { Send, Globe, Square, Database, ImagePlus, Paperclip, X } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import {
  streamChat,
  createSession as apiCreateSession,
  getSystemPrompts,
  truncateSessionMessagesFromAnswerGroup,
} from '../../api/client'
import type { ChatFile, ChatImage, SSEChunk, SystemPrompt } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'
import type { ActiveStreamControl } from './streamControl'
import { parseWorkflowEvent } from '../../api/workflowClient'
import { useWorkflowStore } from '../../stores/workflowStore'

interface MessageInputProps {
  onStreamingChange: (panelId: string, streaming: boolean) => void
  isInteractionLocked: boolean
  activeStreamControl: ActiveStreamControl | null
  setActiveStreamControl: (control: ActiveStreamControl | null) => void
}

const readFileAsDataUrl = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(new Error(`读取文件失败：${file.name}`))
    reader.readAsDataURL(file)
  })

const SUPPORTED_ATTACHMENT_EXTENSIONS = new Set([
  '.pdf',
  '.doc',
  '.docx',
  '.txt',
  '.md',
  '.csv',
  '.xls',
  '.xlsx',
])

const MAX_ATTACHMENT_FILE_SIZE_BYTES = 5 * 1024 * 1024
const MAX_ATTACHMENT_COUNT = 6

interface ComposerSuggestion {
  id: string
  trigger: '/' | '@'
  label: string
  description: string
  insertText: string
}

interface TriggerRange {
  start: number
  end: number
}

const SLASH_TEMPLATES: ComposerSuggestion[] = [
  {
    id: 'summary',
    trigger: '/',
    label: 'summary',
    description: '总结当前问题并给出关键结论',
    insertText: '请基于上下文给出结构化总结：\n1. 关键结论\n2. 证据与依据\n3. 下一步建议\n',
  },
  {
    id: 'plan',
    trigger: '/',
    label: 'plan',
    description: '输出可执行计划',
    insertText: '请给出一个可执行计划（阶段、里程碑、风险、验收标准）。\n',
  },
  {
    id: 'review',
    trigger: '/',
    label: 'review',
    description: '代码评审模板（风险优先）',
    insertText: '请进行代码评审，按严重级别列出问题、影响范围和修复建议。\n',
  },
  {
    id: 'rewrite',
    trigger: '/',
    label: 'rewrite',
    description: '改写为更清晰版本',
    insertText: '请在保持原意的前提下，改写为更清晰、简洁、专业的版本。\n',
  },
  {
    id: 'translate',
    trigger: '/',
    label: 'translate',
    description: '中英互译模板',
    insertText: '请将下面内容翻译成英文，并保持术语一致：\n',
  },
  {
    id: 'table',
    trigger: '/',
    label: 'table',
    description: '表格化对比输出',
    insertText: '请用 Markdown 表格输出对比：包含方案、优点、风险、适用场景、推荐结论。\n',
  },
]

const getFileExtension = (fileName: string): string => {
  const index = fileName.lastIndexOf('.')
  return index >= 0 ? fileName.slice(index).toLowerCase() : ''
}

const formatFileSize = (sizeBytes: number): string => {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

const validateAttachmentFile = (file: File): string | null => {
  const extension = getFileExtension(file.name)
  if (!SUPPORTED_ATTACHMENT_EXTENSIONS.has(extension)) {
    return `不支持的文件类型：${file.name}`
  }
  if (file.size > MAX_ATTACHMENT_FILE_SIZE_BYTES) {
    return `文件过大：${file.name}（最大 5 MB）`
  }
  return null
}

const filesToChatImages = async (files: File[]): Promise<ChatImage[]> =>
  Promise.all(
    files
      .filter((file) => file.type.startsWith('image/'))
      .map(async (file) => ({
        name: file.name,
        media_type: file.type || 'image/png',
        data_url: await readFileAsDataUrl(file),
      })),
  )

const filesToChatFiles = async (files: File[]): Promise<ChatFile[]> =>
  Promise.all(
    files.map(async (file) => ({
      name: file.name,
      media_type: file.type || 'application/octet-stream',
      data_url: await readFileAsDataUrl(file),
      size_bytes: file.size,
    })),
  )

const mergeComposerText = (currentText: string, incomingText: string): string => {
  const nextText = incomingText.trim()
  if (!nextText) return currentText
  if (!currentText.trim()) return nextText
  if (currentText.includes(nextText)) return currentText
  return `${currentText.replace(/\s+$/, '')}\n\n${nextText}`
}

const imageAttachmentKey = (image: ChatImage): string =>
  `${image.name}::${image.media_type}::${image.data_url.slice(0, 64)}`

const fileAttachmentKey = (file: ChatFile): string =>
  [
    file.name,
    file.media_type,
    String(file.size_bytes),
    (file.data_url ?? '').slice(0, 64),
    (file.extracted_text ?? '').slice(0, 64),
  ].join('::')

const mergeUniqueImages = (current: ChatImage[], incoming: ChatImage[]): ChatImage[] => {
  const seen = new Set(current.map(imageAttachmentKey))
  const merged = [...current]
  for (const image of incoming) {
    const key = imageAttachmentKey(image)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(image)
  }
  return merged
}

const mergeUniqueFiles = (current: ChatFile[], incoming: ChatFile[]): ChatFile[] => {
  const seen = new Set(current.map(fileAttachmentKey))
  const merged = [...current]
  for (const file of incoming) {
    const key = fileAttachmentKey(file)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(file)
  }
  return merged
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onStreamingChange,
  isInteractionLocked,
  activeStreamControl,
  setActiveStreamControl,
}) => {
  const {
    panels,
    currentSessionId,
    currentWorkspaceId,
    webSearchEnabled,
    setWebSearchEnabled,
    knowledgeBaseEnabled,
    setKnowledgeBaseEnabled,
    addUserMessage,
    appendChunk,
    setAssistantMessage,
    setAssistantStreaming,
    setSources,
    setTaskId,
    addErrorMessage,
    replaceAssistantMessageByAnswerGroup,
    addSession,
    setCurrentSession,
    updateSessionTitle,
    updateSession,
    removeMessage,
    truncateMessagesFromAnswerGroup,
    sessions,
    composerSeed,
    adjustWorkspaceSessionCount,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [images, setImages] = useState<ChatImage[]>([])
  const [files, setFiles] = useState<ChatFile[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [pendingEditAnswerGroupId, setPendingEditAnswerGroupId] = useState<string | null>(null)
  const [systemPrompts, setSystemPrompts] = useState<SystemPrompt[]>([])
  const [suggestions, setSuggestions] = useState<ComposerSuggestion[]>([])
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0)
  const [triggerRange, setTriggerRange] = useState<TriggerRange | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const attachmentInputRef = useRef<HTMLInputElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const streamingMsgIds = useRef<Map<string, string>>(new Map())

  useEffect(() => {
    if (composerSeed.token === 0) return

    setInput((current) => mergeComposerText(current, composerSeed.text))
    setImages((current) => mergeUniqueImages(current, composerSeed.images))
    setFiles((current) => mergeUniqueFiles(current, composerSeed.files).slice(0, MAX_ATTACHMENT_COUNT))
    setPendingEditAnswerGroupId(composerSeed.editAnswerGroupId ?? null)

    window.requestAnimationFrame(() => {
      adjustHeight()
      textareaRef.current?.focus()
    })
  }, [composerSeed])

  useEffect(() => {
    let disposed = false
    getSystemPrompts()
      .then((list) => {
        if (!disposed) setSystemPrompts(list)
      })
      .catch(() => {
        if (!disposed) setSystemPrompts([])
      })
    return () => {
      disposed = true
    }
  }, [])

  const adjustHeight = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 180)}px`
  }

  const closeSuggestions = () => {
    setSuggestions([])
    setActiveSuggestionIndex(0)
    setTriggerRange(null)
  }

  const updateSuggestions = (nextInput: string, caretPosition: number | null) => {
    if (caretPosition === null) {
      closeSuggestions()
      return
    }

    const textBeforeCaret = nextInput.slice(0, caretPosition)
    const triggerMatch = textBeforeCaret.match(/(?:^|\s)([@/][^\s@/]*)$/)
    if (!triggerMatch) {
      closeSuggestions()
      return
    }

    const triggerToken = triggerMatch[1]
    const trigger = triggerToken[0] as '/' | '@'
    const query = triggerToken.slice(1).trim().toLowerCase()
    const start = caretPosition - triggerToken.length

    let nextSuggestions: ComposerSuggestion[] = []
    if (trigger === '/') {
      nextSuggestions = SLASH_TEMPLATES
        .filter((item) =>
          query.length === 0 ||
          item.label.toLowerCase().includes(query) ||
          item.description.toLowerCase().includes(query),
        )
        .slice(0, 8)
    } else {
      nextSuggestions = systemPrompts
        .map((prompt) => {
          const normalizedContent = prompt.content.trim()
          return {
            id: `prompt-${prompt.id}`,
            trigger: '@' as const,
            label: prompt.name,
            description:
              normalizedContent.replace(/\s+/g, ' ').slice(0, 72) ||
              'System prompt template',
            insertText: normalizedContent ? `${normalizedContent}\n` : `@${prompt.name} `,
          }
        })
        .filter((item) =>
          query.length === 0 ||
          item.label.toLowerCase().includes(query) ||
          item.description.toLowerCase().includes(query),
        )
        .slice(0, 8)
    }

    if (nextSuggestions.length === 0) {
      closeSuggestions()
      return
    }

    setSuggestions(nextSuggestions)
    setActiveSuggestionIndex(0)
    setTriggerRange({ start, end: caretPosition })
  }

  const applySuggestion = (suggestion: ComposerSuggestion) => {
    if (!triggerRange) return

    const before = input.slice(0, triggerRange.start)
    const after = input.slice(triggerRange.end)
    const nextInput = `${before}${suggestion.insertText}${after}`
    const nextCaret = before.length + suggestion.insertText.length

    setInput(nextInput)
    closeSuggestions()

    window.requestAnimationFrame(() => {
      const textarea = textareaRef.current
      if (!textarea) return
      textarea.focus()
      textarea.setSelectionRange(nextCaret, nextCaret)
      adjustHeight()
    })
  }

  const resetComposer = () => {
    setInput('')
    setImages([])
    setFiles([])
    setPendingEditAnswerGroupId(null)
    closeSuggestions()
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    if (imageInputRef.current) {
      imageInputRef.current.value = ''
    }
    if (attachmentInputRef.current) {
      attachmentInputRef.current.value = ''
    }
  }

  const handleSelectImages = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    if (files.length === 0) return

    try {
      const nextImages = await filesToChatImages(files)
      setImages((current) => [...current, ...nextImages])
    } catch (error) {
      console.error('Failed to load selected images', error)
      window.alert('图片读取失败，请重试。')
    } finally {
      event.target.value = ''
    }
  }

  const handleRemoveImage = (index: number) => {
    setImages((current) => current.filter((_, currentIndex) => currentIndex !== index))
  }

  const handleSelectFiles = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? [])
    if (selectedFiles.length === 0) return

    const errors = selectedFiles
      .map((file) => validateAttachmentFile(file))
      .filter((error): error is string => Boolean(error))
    const validFiles = selectedFiles.filter((file) => validateAttachmentFile(file) === null)

    if (validFiles.length === 0) {
      window.alert(errors[0] ?? '没有选择支持的文件类型。')
      event.target.value = ''
      return
    }

    if (files.length + validFiles.length > MAX_ATTACHMENT_COUNT) {
      window.alert(`每条消息最多附加 ${MAX_ATTACHMENT_COUNT} 个文件。`)
      event.target.value = ''
      return
    }

    try {
      const nextFiles = await filesToChatFiles(validFiles)
      setFiles((current) => [...current, ...nextFiles])
      if (errors.length > 0) {
        window.alert(errors[0])
      }
    } catch (error) {
      console.error('Failed to load selected files', error)
      window.alert('文件读取失败，请重试。')
    } finally {
      event.target.value = ''
    }
  }

  const handleRemoveFile = (index: number) => {
    setFiles((current) => current.filter((_, currentIndex) => currentIndex !== index))
  }

  const handlePaste = async (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = Array.from(event.clipboardData?.items ?? [])
    const imageFiles = items
      .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
      .map((item) => item.getAsFile())
      .filter((file): file is File => file !== null)

    if (imageFiles.length === 0) return

    event.preventDefault()

    try {
      const pastedImages = await filesToChatImages(imageFiles)
      setImages((current) => [...current, ...pastedImages])
    } catch (error) {
      console.error('Failed to paste images', error)
      window.alert('粘贴图片失败，请重试。')
    }
  }

  const hasVisibleAssistantState = (panelId: string, msgId: string): boolean => {
    const panel = useChatStore.getState().panels.find((item) => item.id === panelId)
    const message = panel?.messages.find((item) => item.id === msgId && item.role === 'assistant')
    return Boolean(
      message &&
      (
        message.content.trim().length > 0 ||
        (message.sources?.length ?? 0) > 0 ||
        message.taskId
      ),
    )
  }

  const handleStop = () => {
    abortControllerRef.current?.abort()
    setIsLoading(false)
    panels.forEach((panel) => {
      const msgId = streamingMsgIds.current.get(panel.id)
      if (msgId) {
        if (hasVisibleAssistantState(panel.id, msgId)) {
          setAssistantStreaming(panel.id, msgId, false)
        } else {
          removeMessage(panel.id, msgId)
        }
      }
      onStreamingChange(panel.id, false)
    })
    streamingMsgIds.current.clear()
    abortControllerRef.current = null
    setActiveStreamControl(null)
    const activeSessionId = currentSessionId ?? useChatStore.getState().currentSessionId
    if (activeSessionId) {
      syncSessionMetaFromPanels(activeSessionId)
    }
  }

  const syncSessionMetaFromPanels = (sessionId: string) => {
    const now = Date.now() / 1000
    const firstPanel = useChatStore.getState().panels[0]
    const messageCount = firstPanel
      ? firstPanel.messages.filter((message) => message.role !== 'error').length
      : 0

    updateSession(sessionId, {
      updated_at: now,
      message_count: messageCount,
    })
  }

  const handleSend = async () => {
    const msg = input.trim()
    const pendingImages = [...images]
    const pendingFiles = [...files]
    const editingAnswerGroupId = pendingEditAnswerGroupId?.trim() || ''
    const isEditRegenerationRequested = Boolean(editingAnswerGroupId && currentSessionId)
    if (
      (msg.length === 0 && pendingImages.length === 0 && pendingFiles.length === 0) ||
      isLoading ||
      isInteractionLocked
    ) {
      return
    }
    const answerGroupId = (isEditRegenerationRequested ? editingAnswerGroupId : '') ||
      (globalThis.crypto?.randomUUID?.() ?? `grp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)

    resetComposer()
    setIsLoading(true)

    let sessionId = currentSessionId
    const sessionTitleSeed =
      msg ||
      (pendingFiles.length > 0 ? pendingFiles[0].name : '') ||
      (pendingImages.length > 0 ? 'Image chat' : '')

    if (!sessionId) {
      try {
        const session = await apiCreateSession(sessionTitleSeed.slice(0, 40), {
          workspace_id: currentWorkspaceId ?? undefined,
        })
        sessionId = session.session_id
        setCurrentSession(sessionId)
        addSession({
          session_id: sessionId,
          title: session.title,
          created_at: Date.now() / 1000,
          updated_at: Date.now() / 1000,
          message_count: 0,
          is_archived: false,
          is_favorite: false,
          is_pinned: false,
          session_order: 0,
          tags: [],
          workspace_id: session.workspace_id ?? currentWorkspaceId ?? 'workspace-default',
        })
        adjustWorkspaceSessionCount(
          session.workspace_id ?? currentWorkspaceId ?? 'workspace-default',
          1,
        )
      } catch (error) {
        console.error('Failed to create session', error)
        setIsLoading(false)
        return
      }
    }

    const restoreComposerAfterFailure = () => {
      setInput(msg)
      setImages(pendingImages)
      setFiles(pendingFiles)
      setPendingEditAnswerGroupId(isEditRegenerationRequested ? editingAnswerGroupId : null)
      window.requestAnimationFrame(() => {
        adjustHeight()
        textareaRef.current?.focus()
      })
    }

    const isEditRegeneration = Boolean(isEditRegenerationRequested && sessionId)

    if (isEditRegeneration) {
      try {
        await truncateSessionMessagesFromAnswerGroup(sessionId, {
          answer_group_id: answerGroupId,
          content: msg,
          images: pendingImages,
          files: pendingFiles,
        })
        truncateMessagesFromAnswerGroup(answerGroupId, {
          content: msg,
          images: pendingImages,
          files: pendingFiles,
          timestamp: Date.now() / 1000,
        })
      } catch (error) {
        console.error('Failed to truncate session for edited message', error)
        setIsLoading(false)
        restoreComposerAfterFailure()
        return
      }
    } else {
      addUserMessage(msg, pendingImages, pendingFiles, answerGroupId)
    }

    syncSessionMetaFromPanels(sessionId)

    const currentSession = sessions.find((session) => session.session_id === sessionId)
    if (!isEditRegeneration && currentSession && currentSession.message_count === 0 && sessionTitleSeed) {
      updateSessionTitle(sessionId, sessionTitleSeed.slice(0, 40))
    }

    panels.forEach((panel) => onStreamingChange(panel.id, true))
    const workflowStore = useWorkflowStore.getState()
    panels.forEach((panel) => {
      workflowStore.resetWorkflow(panel.id)
    })
    const assistantMsgIds = new Map<string, string>()
    panels.forEach((panel) => {
      const messageId = `assistant-${panel.id}-${Date.now()}`
      assistantMsgIds.set(panel.id, messageId)
      streamingMsgIds.current.set(panel.id, messageId)
    })

    const donePanels = new Set<string>()

    const controller = streamChat(
      sessionId,
      msg,
      panels.map((panel) => panel.modelConfig),
      webSearchEnabled,
      knowledgeBaseEnabled,
      pendingImages,
      pendingFiles,
      answerGroupId,
      (chunk: SSEChunk) => {
        const workflowEvent = parseWorkflowEvent(chunk)
        if (workflowEvent) {
          useWorkflowStore.getState().updateNodeStatus(
            chunk.panel_id,
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

        const msgId = assistantMsgIds.get(chunk.panel_id)
        if (!msgId) return
        const panel = panels.find((item) => item.id === chunk.panel_id)
        const assistantMeta = {
          answerGroupId,
          modelId: panel?.modelConfig.model,
        }

        if (chunk.type === 'chunk' && chunk.content) {
          appendChunk(chunk.panel_id, msgId, chunk.content, assistantMeta)
        } else if (chunk.type === 'sources' && chunk.sources) {
          setSources(chunk.panel_id, msgId, chunk.sources, assistantMeta)
        } else if (chunk.type === 'task_created' && chunk.task_id) {
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
          setTaskId(chunk.panel_id, msgId, chunk.task_id, chunk.task_type)
        } else if (chunk.type === 'done') {
          const workflowSnapshot = useWorkflowStore.getState().getWorkflow(chunk.panel_id)?.nodes
          if (workflowSnapshot && workflowSnapshot.length > 0) {
            replaceAssistantMessageByAnswerGroup(chunk.panel_id, answerGroupId, {
              workflowNodes: workflowSnapshot,
            })
          }
          setAssistantStreaming(chunk.panel_id, msgId, false)
          onStreamingChange(chunk.panel_id, false)
          donePanels.add(chunk.panel_id)
          if (donePanels.size === panels.length) {
            syncSessionMetaFromPanels(sessionId)
            setIsLoading(false)
          }
        } else if (chunk.type === 'error') {
          setAssistantMessage(chunk.panel_id, msgId, '', false)
          addErrorMessage(
            chunk.panel_id,
            chunk.content ?? 'Request failed while processing.',
            chunk.error_code,
            chunk.suggestion,
          )
          onStreamingChange(chunk.panel_id, false)
          donePanels.add(chunk.panel_id)
          if (donePanels.size === panels.length) {
            syncSessionMetaFromPanels(sessionId)
            setIsLoading(false)
          }
        }
      },
      () => {
        syncSessionMetaFromPanels(sessionId)
        setIsLoading(false)
        panels.forEach((panel) => onStreamingChange(panel.id, false))
        streamingMsgIds.current.clear()
        abortControllerRef.current = null
        setActiveStreamControl(null)
      },
      (err) => {
        const normalizedError = err?.trim() || 'Request failed while processing.'
        const isNetworkError = /failed to fetch|network|backend returned an empty response body/i.test(
          normalizedError,
        )
        panels.forEach((panel) => {
          const msgId = streamingMsgIds.current.get(panel.id)
          if (msgId) {
            setAssistantStreaming(panel.id, msgId, false)
          }
          addErrorMessage(
            panel.id,
            isNetworkError
              ? 'Network connection failed. Unable to reach the backend service.'
              : normalizedError,
            isNetworkError ? 'NETWORK_ERROR' : 'REQUEST_FAILED',
            isNetworkError
              ? 'Please check the network connection and verify the backend is running.'
              : 'Please adjust the message or attachments and try again.',
          )
          onStreamingChange(panel.id, false)
        })
        syncSessionMetaFromPanels(sessionId)
        setIsLoading(false)
        streamingMsgIds.current.clear()
        abortControllerRef.current = null
        setActiveStreamControl(null)
        console.error('Stream error:', err)
      },
    )

    abortControllerRef.current = controller
    setActiveStreamControl({
      mode: 'parallel',
      stop: handleStop,
    })
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (suggestions.length > 0) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setActiveSuggestionIndex((current) => (current + 1) % suggestions.length)
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setActiveSuggestionIndex((current) => (current - 1 + suggestions.length) % suggestions.length)
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        closeSuggestions()
        return
      }
      if ((event.key === 'Enter' && !event.shiftKey) || event.key === 'Tab') {
        event.preventDefault()
        const selected = suggestions[activeSuggestionIndex]
        if (selected) {
          applySuggestion(selected)
          return
        }
      }
    }

    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void handleSend()
    }
  }

  const activeStopHandler = isLoading ? handleStop : activeStreamControl?.stop ?? null
  const stopButtonTitle =
    activeStreamControl?.mode === 'single_rerun'
      ? '停止重跑'
      : activeStreamControl?.mode === 'single_continue'
        ? '停止续写'
        : '停止生成'
  const lockedPlaceholder =
    activeStreamControl?.mode === 'single_rerun'
      ? '某个面板正在重新生成，可以停止它，或等待完成后再发送新消息。'
      : activeStreamControl?.mode === 'single_continue'
        ? '某个面板正在继续生成，可以停止它，或等待完成后再发送新消息。'
        : '正在生成回答，请等待完成后再发送新消息。'
  const composerLocked = isInteractionLocked && !isLoading
  const canSend = input.trim().length > 0 || images.length > 0 || files.length > 0

  return (
    <div className="sticky bottom-0 z-10 shrink-0 border-t border-bg-border bg-bg-primary/95 px-4 py-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] backdrop-blur-sm">
      <div className="mx-auto max-w-4xl">
        {pendingEditAnswerGroupId && (
          <div className="mb-2 flex items-center justify-between rounded-xl border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
            <span>编辑模式已开启：发送后会截断该消息之后的内容并重新生成。</span>
            <button
              type="button"
              onClick={() => setPendingEditAnswerGroupId(null)}
              className="rounded-md px-1.5 py-0.5 text-[11px] text-amber-100/80 transition-colors hover:bg-amber-300/20 hover:text-amber-100"
            >
              取消
            </button>
          </div>
        )}

        {images.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {images.map((image, index) => (
              <div
                key={`${image.name}-${index}`}
                className="group relative overflow-hidden rounded-xl border border-bg-border bg-bg-secondary"
              >
                <img
                  src={image.data_url}
                  alt={image.name}
                  className="h-20 w-20 object-cover"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveImage(index)}
                  disabled={composerLocked}
                  className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white opacity-90 transition-opacity group-hover:opacity-100"
                  title="Remove image"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        {files.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="group flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2 text-xs text-text-primary"
              >
                <Paperclip size={12} className="shrink-0 text-text-secondary" />
                <div className="flex min-w-0 flex-col">
                  <span className="max-w-[180px] truncate">{file.name}</span>
                  <span className="text-[10px] text-text-secondary">
                    {formatFileSize(file.size_bytes)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(index)}
                  disabled={composerLocked}
                  className="flex h-5 w-5 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="Remove file"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="rounded-2xl border border-bg-border bg-bg-secondary px-4 py-3 transition-colors focus-within:border-accent-blue/50">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="relative w-full flex-1">
              {suggestions.length > 0 && (
                <div className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl border border-bg-border bg-bg-primary shadow-xl">
                  <div className="max-h-56 overflow-y-auto py-1">
                    {suggestions.map((suggestion, index) => (
                      <button
                        key={suggestion.id}
                        type="button"
                        className={`w-full px-3 py-2 text-left transition-colors ${
                          index === activeSuggestionIndex
                            ? 'bg-accent-blue/15'
                            : 'hover:bg-bg-hover'
                        }`}
                        onMouseDown={(event) => {
                          event.preventDefault()
                          applySuggestion(suggestion)
                        }}
                      >
                        <div className="flex items-center gap-2 text-xs font-medium text-text-primary">
                          <span className="rounded-md bg-bg-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
                            {suggestion.trigger}
                          </span>
                          <span>{suggestion.label}</span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-text-secondary">
                          {suggestion.description}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <textarea
                ref={textareaRef}
                className="min-h-[24px] max-h-[180px] w-full resize-none bg-transparent text-sm leading-relaxed text-text-primary outline-none placeholder:text-text-secondary"
                placeholder={
                  composerLocked
                    ? lockedPlaceholder
                  : '输入消息，可上传文件或图片。Enter 发送，Shift+Enter 换行。'
                }
                value={input}
                onChange={(event) => {
                  const nextValue = event.target.value
                  setInput(nextValue)
                  updateSuggestions(nextValue, event.target.selectionStart)
                  adjustHeight()
                }}
                onClick={(event) => updateSuggestions(event.currentTarget.value, event.currentTarget.selectionStart)}
                onKeyUp={(event) => {
                  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') return
                  updateSuggestions(event.currentTarget.value, event.currentTarget.selectionStart)
                }}
                onPaste={(event) => {
                  void handlePaste(event)
                }}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={isLoading || composerLocked}
              />
            </div>

            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(event) => {
                void handleSelectImages(event)
              }}
            />

            <input
              ref={attachmentInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.txt,.md,.csv,.xls,.xlsx"
              multiple
              className="hidden"
              onChange={(event) => {
                void handleSelectFiles(event)
              }}
            />

            <div className="flex flex-wrap items-center justify-end gap-2 sm:pb-0.5">
              <button
                type="button"
                onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                disabled={composerLocked}
                className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors ${
                  webSearchEnabled
                    ? 'bg-accent-blue/20 text-accent-blue'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                }`}
                title="联网搜索"
              >
                <Globe size={13} />
              </button>

              <button
                type="button"
                onClick={() => setKnowledgeBaseEnabled(!knowledgeBaseEnabled)}
                disabled={composerLocked}
                className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors ${
                  knowledgeBaseEnabled
                    ? 'bg-accent-green/20 text-accent-green'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                }`}
                title="知识库"
              >
                <Database size={13} />
              </button>

              <button
                type="button"
                onClick={() => attachmentInputRef.current?.click()}
                disabled={isLoading || composerLocked}
                className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                title="附加文件"
              >
                <Paperclip size={13} />
              </button>

              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={isLoading || composerLocked}
                className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                title="上传图片"
              >
                <ImagePlus size={13} />
              </button>

              {activeStopHandler ? (
                <button
                  type="button"
                  onClick={activeStopHandler}
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-red/20 text-accent-red transition-colors hover:bg-accent-red/30"
                  title={stopButtonTitle}
                >
                  <Square size={13} fill="currentColor" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    void handleSend()
                  }}
                  disabled={!canSend || composerLocked}
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-blue text-white transition-colors hover:bg-accent-blue-hover disabled:cursor-not-allowed disabled:opacity-30"
                  title="发送"
                >
                  <Send size={13} />
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="mt-2 flex items-center justify-center text-[10px] text-text-secondary/50">
          AI 可能出错，重要信息请自行核实。
        </div>
      </div>
    </div>
  )
}
