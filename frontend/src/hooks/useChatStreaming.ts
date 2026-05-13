import type { SSEChunk } from '../api/client'
import { parseWorkflowEvent } from '../api/workflowClient'
import { useChatStore } from '../stores/chatStore'
import type { AssistantMessageMeta, ErrorMessageMeta } from '../stores/chatStoreModel'
import { useTaskStore } from '../stores/taskStore'
import { useWorkflowStore } from '../stores/workflowStore'

interface DispatchChatStreamChunkOptions {
  chunk: SSEChunk
  messageId: string
  answerGroupId: string
  assistantMeta?: AssistantMessageMeta
  errorFallback: string
  errorMeta?: ErrorMessageMeta
  expectedPanelId?: string
  clearAssistantOnError?: boolean
  beforeError?: (chunk: SSEChunk) => void
  onDone?: (chunk: SSEChunk) => void
  onError?: (chunk: SSEChunk) => void
}

/**
 * Shared SSE chunk dispatcher used by ChatPanel and MessageInput.
 */
export function dispatchChatStreamChunk({
  chunk,
  messageId,
  answerGroupId,
  assistantMeta,
  errorFallback,
  errorMeta,
  expectedPanelId,
  clearAssistantOnError = false,
  beforeError,
  onDone,
  onError,
}: DispatchChatStreamChunkOptions): boolean {
  if (expectedPanelId && chunk.panel_id !== expectedPanelId) return false

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
        retrievalMeta: workflowEvent.retrieval_meta,
        error: workflowEvent.error,
      },
    )
    return true
  }

  const chatStore = useChatStore.getState()

  if (chunk.type === 'chunk' && chunk.content) {
    chatStore.appendChunk(chunk.panel_id, messageId, chunk.content, assistantMeta)
    return true
  }

  if (chunk.type === 'sources' && chunk.sources) {
    chatStore.setSources(chunk.panel_id, messageId, chunk.sources, assistantMeta)
    return true
  }

  if (chunk.type === 'token_usage' && chunk.token_usage) {
    chatStore.updateMessage(chunk.panel_id, messageId, { tokenUsage: chunk.token_usage })
    return true
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
    chatStore.setTaskId(chunk.panel_id, messageId, chunk.task_id, chunk.task_type)
    return true
  }

  if (chunk.type === 'done') {
    const workflowSnapshot = useWorkflowStore.getState().getWorkflow(chunk.panel_id)?.nodes
    if (workflowSnapshot && workflowSnapshot.length > 0) {
      chatStore.replaceAssistantMessageByAnswerGroup(chunk.panel_id, answerGroupId, {
        workflowNodes: workflowSnapshot,
      })
    }
    chatStore.setAssistantStreaming(chunk.panel_id, messageId, false)
    onDone?.(chunk)
    return true
  }

  if (chunk.type === 'error') {
    beforeError?.(chunk)
    if (clearAssistantOnError) {
      chatStore.setAssistantMessage(chunk.panel_id, messageId, '', false)
    }
    chatStore.addErrorMessage(
      chunk.panel_id,
      chunk.content ?? errorFallback,
      chunk.error_code,
      chunk.suggestion,
      errorMeta,
    )
    onError?.(chunk)
    return true
  }

  return false
}
