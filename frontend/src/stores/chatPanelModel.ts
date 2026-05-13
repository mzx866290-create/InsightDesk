import type { ChatFile, ChatImage, Message, ModelConfig, SourceItem } from '../api/client'
import { normalizeModelConfig } from '../api/client'
import { appendChunkToMessages } from './chatMessageModel'
import type {
  AssistantAnswerGroupPatch,
  AssistantMessageMeta,
  BuildErrorMessageOptions,
  BuildUserMessageOptions,
  ErrorMessageMeta,
  PanelMessage,
  UserMessagePatch,
} from './chatMessageModel'
import {
  createErrorMessage,
  createUserMessage,
  mapMessages,
  removeErrorMessagesForAnswerGroup,
  removeMessageFromMessages,
  replaceAssistantMessageByAnswerGroup,
  setAssistantMessageInMessages,
  setAssistantStreamingInMessages,
  setSourcesInMessages,
  setTaskIdInMessages,
  truncatePanelMessagesFromAnswerGroup,
  updateMessageInMessages,
} from './chatMessageModel'

export interface Panel {
  id: string
  modelConfig: ModelConfig
  messages: PanelMessage[]
}

export interface MessageStateSlice {
  panels: Panel[]
}

export interface MessageActionSlice {
  addUserMessage: (
    content: string,
    images?: ChatImage[],
    files?: ChatFile[],
    answerGroupId?: string,
  ) => string
  appendChunk: (
    panelId: string,
    msgId: string,
    chunk: string,
    meta?: AssistantMessageMeta,
  ) => void
  setAssistantMessage: (
    panelId: string,
    msgId: string,
    content: string,
    streaming: boolean,
  ) => void
  setAssistantStreaming: (panelId: string, msgId: string, streaming: boolean) => void
  setSources: (
    panelId: string,
    msgId: string,
    sources: SourceItem[],
    meta?: AssistantMessageMeta,
  ) => void
  addErrorMessage: (
    panelId: string,
    content: string,
    errorCode?: string,
    suggestion?: string,
    meta?: ErrorMessageMeta,
  ) => void
  setTaskId: (panelId: string, msgId: string, taskId: string, taskType?: string) => void
  loadMessages: (panelId: string, messages: Message[]) => void
  updateMessage: (panelId: string, msgId: string, patch: Partial<PanelMessage>) => void
  removeMessage: (panelId: string, msgId: string) => void
  truncateMessagesFromAnswerGroup: (
    answerGroupId: string,
    userPatch?: UserMessagePatch,
  ) => void
  replaceAssistantMessageByAnswerGroup: (
    panelId: string,
    answerGroupId: string,
    patch: AssistantAnswerGroupPatch,
  ) => void
  clearMessages: () => void
}

type MessageStateWriter<State extends MessageStateSlice> = (
  updater: (state: State) => Pick<State, 'panels'>,
) => void

export function defaultModelConfig(panelId: string): ModelConfig {
  return normalizeModelConfig({
    panel_id: panelId,
    connection_type: 'ollama',
    provider: 'ollama',
    model: 'qwen3.5-2B:latest',
    base_url: 'http://localhost:11434',
    api_key: '',
    temperature: 0.3,
    agent_mode: 'auto',
  })
}

export function sanitizePersistedModelConfig(modelConfig: ModelConfig): ModelConfig {
  return {
    ...modelConfig,
    // 避免把 Provider 凭据写入浏览器持久化存储。
    api_key: '',
  }
}

export function newPanel(): Panel {
  const id = `panel-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  return { id, modelConfig: defaultModelConfig(id), messages: [] }
}

export function addPanelToList(
  panels: Panel[],
  createPanel: () => Panel = newPanel,
  maxPanels = 6,
): Panel[] {
  if (panels.length >= maxPanels) return panels
  return [...panels, createPanel()]
}

export function removePanelFromList(
  panels: Panel[],
  panelId: string,
): Panel[] {
  if (panels.length <= 1) return panels
  return panels.filter((panel) => panel.id !== panelId)
}

export function updatePanelModelConfig(
  panels: Panel[],
  panelId: string,
  config: Partial<ModelConfig>,
): Panel[] {
  return panels.map((panel) =>
    panel.id === panelId
      ? {
          ...panel,
          modelConfig: normalizeModelConfig({
            ...panel.modelConfig,
            ...config,
            panel_id: panelId,
          }),
        }
      : panel,
  )
}

export function normalizePanels(panels: Panel[]): Panel[] {
  return panels.map((panel) => ({
    ...panel,
    modelConfig: normalizeModelConfig({
      ...panel.modelConfig,
      panel_id: panel.id,
    }),
  }))
}

function updatePanelMessages(
  panels: Panel[],
  panelId: string,
  transform: (messages: PanelMessage[]) => PanelMessage[],
): Panel[] {
  return panels.map((panel) => {
    if (panel.id !== panelId) return panel
    const nextMessages = transform(panel.messages)
    if (nextMessages === panel.messages) return panel
    return {
      ...panel,
      messages: nextMessages,
    }
  })
}

export function addUserMessageToPanels(
  panels: Panel[],
  message: PanelMessage,
): Panel[] {
  return panels.map((panel) => ({
    ...panel,
    messages: [...panel.messages, { ...message }],
  }))
}

export function addUserMessageToPanelState(
  panels: Panel[],
  content: string,
  images: ChatImage[] = [],
  files: ChatFile[] = [],
  answerGroupId?: string,
  options: BuildUserMessageOptions = {},
): { panels: Panel[]; messageId: string } {
  const message = createUserMessage(content, images, files, answerGroupId, options)
  return {
    panels: addUserMessageToPanels(panels, message),
    messageId: message.id,
  }
}

export function clearMessagesFromPanels(panels: Panel[]): Panel[] {
  return panels.map((panel) => ({ ...panel, messages: [] }))
}

export function loadMessagesIntoAllPanels(
  panels: Panel[],
  messages: Message[],
): Panel[] {
  return panels.map((panel) => ({
    ...panel,
    messages: mapMessages(messages),
  }))
}

export function loadMessagesIntoPanel(
  panels: Panel[],
  panelId: string,
  messages: Message[],
): Panel[] {
  return updatePanelMessages(panels, panelId, () => mapMessages(messages))
}

export function truncateAnswerGroupFromPanels(
  panels: Panel[],
  answerGroupId: string,
  userPatch: UserMessagePatch = {},
): Panel[] {
  return panels.map((panel) => {
    const nextMessages = truncatePanelMessagesFromAnswerGroup(
      panel.messages,
      answerGroupId,
      userPatch,
    )
    if (nextMessages === panel.messages) return panel
    return {
      ...panel,
      messages: nextMessages,
    }
  })
}

export function replaceAssistantMessageByAnswerGroupInPanel(
  panels: Panel[],
  panelId: string,
  answerGroupId: string,
  patch: AssistantAnswerGroupPatch,
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) =>
    replaceAssistantMessageByAnswerGroup(messages, answerGroupId, patch),
  )
}

export function appendChunkToPanel(
  panels: Panel[],
  panelId: string,
  msgId: string,
  chunk: string,
  meta: AssistantMessageMeta = {},
  options: BuildUserMessageOptions = {},
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) =>
    appendChunkToMessages(
      removeErrorMessagesForAnswerGroup(messages, meta.answerGroupId),
      panelId,
      msgId,
      chunk,
      meta,
      options,
    ),
  )
}

export function setAssistantMessageInPanel(
  panels: Panel[],
  panelId: string,
  msgId: string,
  content: string,
  streaming: boolean,
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) =>
    setAssistantMessageInMessages(messages, msgId, content, streaming),
  )
}

export function setSourcesInPanel(
  panels: Panel[],
  panelId: string,
  msgId: string,
  sources: SourceItem[],
  meta: AssistantMessageMeta = {},
  options: BuildUserMessageOptions = {},
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) =>
    setSourcesInMessages(
      removeErrorMessagesForAnswerGroup(messages, meta.answerGroupId),
      panelId,
      msgId,
      sources,
      meta,
      options,
    ),
  )
}

export function addErrorMessageToPanels(
  panels: Panel[],
  panelId: string,
  content: string,
  errorCode?: string,
  suggestion?: string,
  meta: ErrorMessageMeta = {},
  options: BuildErrorMessageOptions = {},
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) => [
    ...removeErrorMessagesForAnswerGroup(messages, meta.answerGroupId, meta.retryMode),
    createErrorMessage(panelId, content, errorCode, suggestion, meta, options),
  ])
}

export function setTaskIdInPanel(
  panels: Panel[],
  panelId: string,
  msgId: string,
  taskId: string,
  taskType?: string,
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) =>
    setTaskIdInMessages(messages, msgId, taskId, taskType),
  )
}

export function updateMessageInPanel(
  panels: Panel[],
  panelId: string,
  msgId: string,
  patch: Partial<PanelMessage>,
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) =>
    updateMessageInMessages(messages, msgId, patch),
  )
}

export function removeMessageFromPanel(
  panels: Panel[],
  panelId: string,
  msgId: string,
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) =>
    removeMessageFromMessages(messages, msgId),
  )
}

export function setAssistantStreamingInPanel(
  panels: Panel[],
  panelId: string,
  msgId: string,
  streaming: boolean,
): Panel[] {
  return updatePanelMessages(panels, panelId, (messages) =>
    setAssistantStreamingInMessages(messages, msgId, streaming),
  )
}

export function clearMessagesFromPanelList(panels: Panel[]): Panel[] {
  return clearMessagesFromPanels(panels)
}

export function createMessageActions<State extends MessageStateSlice>(
  set: MessageStateWriter<State>,
): MessageActionSlice {
  return {
    addUserMessage: (content, images = [], files = [], answerGroupId) => {
      let messageId = ''
      set((state) => {
        const result = addUserMessageToPanelState(
          state.panels,
          content,
          images,
          files,
          answerGroupId,
        )
        messageId = result.messageId
        return { panels: result.panels }
      })
      return messageId
    },
    appendChunk: (panelId, msgId, chunk, meta = {}) =>
      set((state) => ({
        panels: appendChunkToPanel(state.panels, panelId, msgId, chunk, meta),
      })),
    setAssistantMessage: (panelId, msgId, content, streaming) =>
      set((state) => ({
        panels: setAssistantMessageInPanel(state.panels, panelId, msgId, content, streaming),
      })),
    setAssistantStreaming: (panelId, msgId, streaming) =>
      set((state) => ({
        panels: setAssistantStreamingInPanel(state.panels, panelId, msgId, streaming),
      })),
    setSources: (panelId, msgId, sources, meta = {}) =>
      set((state) => ({
        panels: setSourcesInPanel(state.panels, panelId, msgId, sources, meta),
      })),
    addErrorMessage: (panelId, content, errorCode, suggestion, meta) =>
      set((state) => ({
        panels: addErrorMessageToPanels(
          state.panels,
          panelId,
          content,
          errorCode,
          suggestion,
          meta,
        ),
      })),
    setTaskId: (panelId, msgId, taskId, taskType) =>
      set((state) => ({
        panels: setTaskIdInPanel(state.panels, panelId, msgId, taskId, taskType),
      })),
    loadMessages: (panelId, messages) =>
      set((state) => ({
        panels: loadMessagesIntoPanel(state.panels, panelId, messages),
      })),
    updateMessage: (panelId, msgId, patch) =>
      set((state) => ({
        panels: updateMessageInPanel(state.panels, panelId, msgId, patch),
      })),
    removeMessage: (panelId, msgId) =>
      set((state) => ({
        panels: removeMessageFromPanel(state.panels, panelId, msgId),
      })),
    truncateMessagesFromAnswerGroup: (answerGroupId, userPatch = {}) =>
      set((state) => ({
        panels: truncateAnswerGroupFromPanels(state.panels, answerGroupId, userPatch),
      })),
    replaceAssistantMessageByAnswerGroup: (panelId, answerGroupId, patch) =>
      set((state) => ({
        panels: replaceAssistantMessageByAnswerGroupInPanel(
          state.panels,
          panelId,
          answerGroupId,
          patch,
        ),
      })),
    clearMessages: () =>
      set((state) => ({
        panels: clearMessagesFromPanelList(state.panels),
      })),
  }
}
