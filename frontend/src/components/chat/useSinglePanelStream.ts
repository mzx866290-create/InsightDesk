import React from 'react'

import { streamSingleChat, type ChatFile, type ChatImage } from '../../api/client'
import { dispatchChatStreamChunk } from '../../hooks/useChatStreaming'
import { useChatStore, type Panel, type PanelMessage } from '../../stores/chatStore'
import { useWorkflowStore } from '../../stores/workflowStore'
import type { ActiveStreamControl } from './streamControl'

type SinglePanelRetryMode = NonNullable<PanelMessage['retryMode']>

export interface SinglePanelStreamOptions {
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

interface UseSinglePanelStreamOptions {
  panel: Panel
  currentSessionId: string | null
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  enabledMcpServers: string[]
  isInteractionLocked: boolean
  isStreaming: boolean
  rerunAbortControllerRef: React.MutableRefObject<AbortController | null>
  onStreamingChange: (panelId: string, streaming: boolean) => void
  setActiveStreamControl: (control: ActiveStreamControl | null) => void
  touchSession: () => void
}

export function useSinglePanelStream({
  panel,
  currentSessionId,
  webSearchEnabled,
  knowledgeBaseEnabled,
  enabledMcpServers,
  isInteractionLocked,
  isStreaming,
  rerunAbortControllerRef,
  onStreamingChange,
  setActiveStreamControl,
  touchSession,
}: UseSinglePanelStreamOptions) {
  const {
    removeMessage,
    replaceAssistantMessageByAnswerGroup,
    appendChunk,
    setAssistantStreaming,
    addErrorMessage,
  } = useChatStore.getState()
  const { clearWorkflow, hydrateWorkflow, resetWorkflow } = useWorkflowStore()

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
          tokenUsage: existingAssistantMessage.tokenUsage,
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
        tokenUsage: undefined,
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
        dispatchChatStreamChunk({
          chunk,
          messageId: targetMessageId,
          answerGroupId,
          assistantMeta,
          expectedPanelId: panel.id,
          errorFallback: sseErrorFallback,
          errorMeta: {
            answerGroupId,
            retryMode,
          },
          beforeError: () => {
            rerunAbortControllerRef.current = null
            restorePreviousAssistant()
          },
          onDone: () => {
            rerunAbortControllerRef.current = null
            onStreamingChange(panel.id, false)
            setActiveStreamControl(null)
            touchSession()
          },
          onError: () => {
            onStreamingChange(panel.id, false)
            setActiveStreamControl(null)
          },
        })
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

  return runSinglePanelStream
}
