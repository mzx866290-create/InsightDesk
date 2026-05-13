import type {
  AnswerGroupTokenUsage,
  ChatFile,
  ChatImage,
  Message,
  MessageFeedbackValue,
  SourceItem,
} from '../api/client'
import type { WorkflowNode } from './workflowStore'

export type ErrorRetryMode = 'rerun' | 'continue'

export interface PanelMessage {
  id: string
  serverMessageId?: number
  role: 'user' | 'assistant' | 'error'
  content: string
  images?: ChatImage[]
  files?: ChatFile[]
  modelId?: string
  panelId?: string
  answerGroupId?: string
  streaming?: boolean
  sources?: SourceItem[]
  errorCode?: string
  suggestion?: string
  taskId?: string
  taskType?: string
  workflowNodes?: WorkflowNode[]
  tokenUsage?: AnswerGroupTokenUsage
  timestamp?: number
  feedbackValue?: MessageFeedbackValue
  retryMode?: ErrorRetryMode
}

export type AssistantMessageMeta = Partial<Pick<PanelMessage, 'modelId' | 'answerGroupId'>>
export type ErrorMessageMeta = Partial<Pick<PanelMessage, 'answerGroupId' | 'retryMode'>>
export type UserMessagePatch = Partial<
  Pick<PanelMessage, 'content' | 'images' | 'files' | 'timestamp'>
>
export type AssistantAnswerGroupPatch = Partial<
  Pick<
    PanelMessage,
    | 'content'
    | 'sources'
    | 'modelId'
    | 'streaming'
    | 'taskId'
    | 'taskType'
    | 'workflowNodes'
    | 'tokenUsage'
    | 'serverMessageId'
    | 'timestamp'
    | 'feedbackValue'
    | 'panelId'
  >
>

export interface BuildUserMessageOptions {
  now?: () => number
}

export interface BuildErrorMessageOptions {
  now?: () => number
  randomSuffix?: () => string
}

function defaultRandomSuffix(): string {
  return Math.random().toString(36).slice(2, 7)
}

export function createUserMessage(
  content: string,
  images: ChatImage[] = [],
  files: ChatFile[] = [],
  answerGroupId?: string,
  options: BuildUserMessageOptions = {},
): PanelMessage {
  const now = options.now ?? Date.now
  const timestamp = now() / 1000
  return {
    id: `msg-${Math.floor(timestamp * 1000)}`,
    role: 'user',
    content,
    images,
    files,
    answerGroupId,
    timestamp,
  }
}

export function createErrorMessage(
  panelId: string,
  content: string,
  errorCode?: string,
  suggestion?: string,
  meta: ErrorMessageMeta = {},
  options: BuildErrorMessageOptions = {},
): PanelMessage {
  const now = options.now ?? Date.now
  const randomSuffix = options.randomSuffix ?? defaultRandomSuffix
  const current = now()
  return {
    id: `error-${current}-${randomSuffix()}`,
    role: 'error',
    content,
    errorCode,
    suggestion,
    panelId,
    answerGroupId: meta.answerGroupId,
    retryMode: meta.retryMode,
    timestamp: current / 1000,
  }
}

export function appendChunkToMessages(
  messages: PanelMessage[],
  panelId: string,
  msgId: string,
  chunk: string,
  meta: AssistantMessageMeta = {},
  options: BuildUserMessageOptions = {},
): PanelMessage[] {
  const existing = messages.find((message) => message.id === msgId)
  if (existing) {
    return messages.map((message) =>
      message.id === msgId
        ? { ...message, content: message.content + chunk, streaming: true }
        : message,
    )
  }

  const now = options.now ?? Date.now
  return [
    ...messages,
    {
      id: msgId,
      role: 'assistant',
      content: chunk,
      streaming: true,
      modelId: meta.modelId,
      panelId,
      answerGroupId: meta.answerGroupId,
      timestamp: now() / 1000,
      feedbackValue: 0,
    },
  ]
}

export function setAssistantMessageInMessages(
  messages: PanelMessage[],
  msgId: string,
  content: string,
  streaming: boolean,
): PanelMessage[] {
  return messages.map((message) =>
    message.id === msgId ? { ...message, content, streaming } : message,
  )
}

export function setSourcesInMessages(
  messages: PanelMessage[],
  panelId: string,
  msgId: string,
  sources: SourceItem[],
  meta: AssistantMessageMeta = {},
  options: BuildUserMessageOptions = {},
): PanelMessage[] {
  const existing = messages.find((message) => message.id === msgId)
  if (existing) {
    return messages.map((message) =>
      message.id === msgId ? { ...message, sources } : message,
    )
  }

  const now = options.now ?? Date.now
  return [
    ...messages,
    {
      id: msgId,
      role: 'assistant',
      content: '',
      streaming: true,
      sources,
      modelId: meta.modelId,
      panelId,
      answerGroupId: meta.answerGroupId,
      timestamp: now() / 1000,
      feedbackValue: 0,
    },
  ]
}

export function setTaskIdInMessages(
  messages: PanelMessage[],
  msgId: string,
  taskId: string,
  taskType?: string,
): PanelMessage[] {
  return messages.map((message) =>
    message.id === msgId ? { ...message, taskId, taskType } : message,
  )
}

export function updateMessageInMessages(
  messages: PanelMessage[],
  msgId: string,
  patch: Partial<PanelMessage>,
): PanelMessage[] {
  return messages.map((message) =>
    message.id === msgId ? { ...message, ...patch } : message,
  )
}

export function removeMessageFromMessages(
  messages: PanelMessage[],
  msgId: string,
): PanelMessage[] {
  return messages.filter((message) => message.id !== msgId)
}

export function removeErrorMessagesForAnswerGroup(
  messages: PanelMessage[],
  answerGroupId?: string,
  retryMode?: ErrorRetryMode,
): PanelMessage[] {
  if (!answerGroupId) return messages
  return messages.filter((message) => {
    if (message.role !== 'error' || message.answerGroupId !== answerGroupId) return true
    if (!retryMode) return false
    return Boolean(message.retryMode && message.retryMode !== retryMode)
  })
}

export function setAssistantStreamingInMessages(
  messages: PanelMessage[],
  msgId: string,
  streaming: boolean,
): PanelMessage[] {
  return messages.map((message) =>
    message.id === msgId ? { ...message, streaming } : message,
  )
}

export function mapMessages(messages: Message[]): PanelMessage[] {
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
    tokenUsage: message.token_usage,
    timestamp: message.timestamp,
    feedbackValue: message.feedback_value,
  }))
}

export function truncatePanelMessagesFromAnswerGroup(
  messages: PanelMessage[],
  answerGroupId: string,
  userPatch: UserMessagePatch = {},
): PanelMessage[] {
  const userMessageIndex = messages.findIndex(
    (message) => message.role === 'user' && message.answerGroupId === answerGroupId,
  )
  if (userMessageIndex < 0) return messages

  return messages.slice(0, userMessageIndex + 1).map((message, index) => {
    if (index !== userMessageIndex) return message
    return {
      ...message,
      ...userPatch,
    }
  })
}

export function replaceAssistantMessageByAnswerGroup(
  messages: PanelMessage[],
  answerGroupId: string,
  patch: AssistantAnswerGroupPatch,
): PanelMessage[] {
  const cleanedMessages = removeErrorMessagesForAnswerGroup(messages, answerGroupId)
  return cleanedMessages.map((message) =>
    message.role === 'assistant' && message.answerGroupId === answerGroupId
      ? { ...message, ...patch }
      : message,
  )
}
