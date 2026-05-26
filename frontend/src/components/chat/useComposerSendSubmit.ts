import { useRef, useState } from 'react'
import type { Dispatch, RefObject, SetStateAction } from 'react'
import type { ChatFile, ChatImage } from '../../api/client'
import {
  streamChat,
  truncateSessionMessagesFromAnswerGroup,
} from '../../api/client'
import { dispatchChatStreamChunk } from '../../hooks/useChatStreaming'
import { useChatStore } from '../../stores/chatStore'
import { useWorkflowStore } from '../../stores/workflowStore'
import type { ActiveStreamControl } from './streamControl'
import {
  createAssistantMessageIds,
  finishComposerPanelStreams,
  markPanelStreamComplete,
  replaceStreamingMessageIds,
  reportComposerStreamError,
  resetPanelWorkflows,
  setAllPanelsStreaming,
  stopComposerPanelStreams,
} from './composerStreamLifecycle'
import {
  buildAnswerGroupId,
  classifyStreamFailure,
} from './messageInputUtils'

interface UseComposerSendSubmitOptions {
  input: string
  images: ChatImage[]
  files: ChatFile[]
  pendingEditAnswerGroupId: string | null
  omitHistoryForNextSend: boolean
  isInteractionLocked: boolean
  textareaRef: RefObject<HTMLTextAreaElement>
  adjustHeight: () => void
  resetComposer: () => void
  restoreAttachments: (nextImages: ChatImage[], nextFiles: ChatFile[]) => void
  setInput: Dispatch<SetStateAction<string>>
  setPendingEditAnswerGroupId: Dispatch<SetStateAction<string | null>>
  setOmitHistoryForNextSend: Dispatch<SetStateAction<boolean>>
  ensureActiveSession: (sessionTitleSeed: string) => Promise<string | null>
  syncSessionMetaFromPanels: (sessionId: string) => void
  onStreamingChange: (panelId: string, streaming: boolean) => void
  setActiveStreamControl: (control: ActiveStreamControl | null) => void
}

export const useComposerSendSubmit = ({
  input,
  images,
  files,
  pendingEditAnswerGroupId,
  omitHistoryForNextSend,
  isInteractionLocked,
  textareaRef,
  adjustHeight,
  resetComposer,
  restoreAttachments,
  setInput,
  setPendingEditAnswerGroupId,
  setOmitHistoryForNextSend,
  ensureActiveSession,
  syncSessionMetaFromPanels,
  onStreamingChange,
  setActiveStreamControl,
}: UseComposerSendSubmitOptions) => {
  const panels = useChatStore((state) => state.panels)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const webSearchEnabled = useChatStore((state) => state.webSearchEnabled)
  const knowledgeBaseEnabled = useChatStore((state) => state.knowledgeBaseEnabled)
  const enabledMcpServers = useChatStore((state) => state.enabledMcpServers)
  const sessions = useChatStore((state) => state.sessions)
  const addUserMessage = useChatStore((state) => state.addUserMessage)
  const setAssistantStreaming = useChatStore((state) => state.setAssistantStreaming)
  const addErrorMessage = useChatStore((state) => state.addErrorMessage)
  const removeMessage = useChatStore((state) => state.removeMessage)
  const truncateMessagesFromAnswerGroup = useChatStore(
    (state) => state.truncateMessagesFromAnswerGroup,
  )
  const updateSessionTitle = useChatStore((state) => state.updateSessionTitle)

  const [isLoading, setIsLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const streamingMsgIds = useRef<Map<string, string>>(new Map())

  const handleStop = () => {
    abortControllerRef.current?.abort()
    setIsLoading(false)
    stopComposerPanelStreams({
      panels: useChatStore.getState().panels,
      streamingMessageIds: streamingMsgIds.current,
      setAssistantStreaming,
      removeMessage,
      onStreamingChange,
    })
    abortControllerRef.current = null
    setActiveStreamControl(null)
    const activeSessionId = currentSessionId ?? useChatStore.getState().currentSessionId
    if (activeSessionId) {
      syncSessionMetaFromPanels(activeSessionId)
    }
  }

  const handleSend = async () => {
    const msg = input.trim()
    const pendingImages = [...images]
    const pendingFiles = [...files]
    const editingAnswerGroupId = pendingEditAnswerGroupId?.trim() || ''
    const isEditRegenerationRequested = Boolean(editingAnswerGroupId && currentSessionId)
    const omitHistoryForRequest = omitHistoryForNextSend
    if (
      (msg.length === 0 && pendingImages.length === 0 && pendingFiles.length === 0) ||
      isLoading ||
      isInteractionLocked
    ) {
      return
    }
    const answerGroupId = buildAnswerGroupId(isEditRegenerationRequested ? editingAnswerGroupId : '')

    resetComposer()
    setIsLoading(true)

    let sessionId = currentSessionId
    const sessionTitleSeed =
      msg ||
      (pendingFiles.length > 0 ? pendingFiles[0].name : '') ||
      (pendingImages.length > 0 ? 'Image chat' : '')

    if (!sessionId) {
      sessionId = await ensureActiveSession(sessionTitleSeed)
      if (!sessionId) {
        setIsLoading(false)
        return
      }
    }

    // The composer is cleared before persistence work; keep the payload recoverable on failure.
    const restoreComposerAfterFailure = () => {
      setInput(msg)
      restoreAttachments(pendingImages, pendingFiles)
      setPendingEditAnswerGroupId(isEditRegenerationRequested ? editingAnswerGroupId : null)
      setOmitHistoryForNextSend(omitHistoryForRequest)
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

    setAllPanelsStreaming(panels, true, onStreamingChange)
    const workflowStore = useWorkflowStore.getState()
    resetPanelWorkflows(panels, workflowStore.resetWorkflow)
    const assistantMsgIds = createAssistantMessageIds(panels)
    replaceStreamingMessageIds(streamingMsgIds.current, assistantMsgIds)

    const donePanels = new Set<string>()
    const markPanelComplete = (panelId: string) => {
      markPanelStreamComplete({
        panelId,
        totalPanelCount: panels.length,
        completedPanelIds: donePanels,
        onStreamingChange,
        onAllPanelsComplete: () => {
          syncSessionMetaFromPanels(sessionId)
          setIsLoading(false)
        },
      })
    }

    const controller = streamChat(
      sessionId,
      msg,
      panels.map((panel) => panel.modelConfig),
      webSearchEnabled,
      knowledgeBaseEnabled,
      enabledMcpServers,
      pendingImages,
      pendingFiles,
      answerGroupId,
      (chunk) => {
        const msgId = assistantMsgIds.get(chunk.panel_id)
        if (!msgId) return
        const panel = panels.find((item) => item.id === chunk.panel_id)
        const assistantMeta = {
          answerGroupId,
          modelId: panel?.modelConfig.model,
        }

        dispatchChatStreamChunk({
          chunk,
          messageId: msgId,
          answerGroupId,
          assistantMeta,
          errorFallback: 'Request failed while processing.',
          errorMeta: {
            answerGroupId,
            retryMode: 'rerun',
          },
          clearAssistantOnError: true,
          onDone: () => {
            markPanelComplete(chunk.panel_id)
          },
          onError: () => {
            markPanelComplete(chunk.panel_id)
          },
        })
      },
      () => {
        syncSessionMetaFromPanels(sessionId)
        setIsLoading(false)
        finishComposerPanelStreams({
          panels,
          streamingMessageIds: streamingMsgIds.current,
          onStreamingChange,
        })
        abortControllerRef.current = null
        setActiveStreamControl(null)
      },
      (err) => {
        const failure = classifyStreamFailure(err ?? '')
        reportComposerStreamError({
          panels,
          streamingMessageIds: streamingMsgIds.current,
          failure,
          errorMeta: {
            answerGroupId,
            retryMode: 'rerun',
          },
          setAssistantStreaming,
          addErrorMessage,
          onStreamingChange,
        })
        syncSessionMetaFromPanels(sessionId)
        setIsLoading(false)
        abortControllerRef.current = null
        setActiveStreamControl(null)
        console.error('Stream error:', err)
      },
      omitHistoryForRequest,
    )

    abortControllerRef.current = controller
    setActiveStreamControl({
      mode: 'parallel',
      stop: handleStop,
    })
  }

  return {
    isLoading,
    handleSend,
    handleStop,
  }
}
