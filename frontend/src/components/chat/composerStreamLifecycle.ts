import type { ErrorMessageMeta, Panel } from '../../stores/chatStoreModel'

type ComposerPanel = Pick<Panel, 'id' | 'messages'>

type StreamingChangeHandler = (panelId: string, streaming: boolean) => void
type SetAssistantStreamingHandler = (
  panelId: string,
  messageId: string,
  streaming: boolean,
) => void
type RemoveMessageHandler = (panelId: string, messageId: string) => void
type AddErrorMessageHandler = (
  panelId: string,
  content: string,
  errorCode?: string,
  suggestion?: string,
  meta?: ErrorMessageMeta,
) => void

export interface ComposerStreamFailure {
  content: string
  errorCode: string
  suggestion?: string
}

export function hasVisibleAssistantState(
  panels: ComposerPanel[],
  panelId: string,
  messageId: string,
): boolean {
  const panel = panels.find((item) => item.id === panelId)
  const message = panel?.messages.find(
    (item) => item.id === messageId && item.role === 'assistant',
  )

  return Boolean(
    message &&
      (
        message.content.trim().length > 0 ||
        (message.sources?.length ?? 0) > 0 ||
        message.taskId
      ),
  )
}

export function createAssistantMessageIds(
  panels: Array<Pick<Panel, 'id'>>,
  now: () => number = Date.now,
): Map<string, string> {
  const ids = new Map<string, string>()
  panels.forEach((panel) => {
    ids.set(panel.id, `assistant-${panel.id}-${now()}`)
  })
  return ids
}

export function replaceStreamingMessageIds(
  target: Map<string, string>,
  nextIds: Map<string, string>,
): void {
  target.clear()
  nextIds.forEach((messageId, panelId) => {
    target.set(panelId, messageId)
  })
}

export function setAllPanelsStreaming(
  panels: Array<Pick<Panel, 'id'>>,
  streaming: boolean,
  onStreamingChange: StreamingChangeHandler,
): void {
  panels.forEach((panel) => onStreamingChange(panel.id, streaming))
}

export function resetPanelWorkflows(
  panels: Array<Pick<Panel, 'id'>>,
  resetWorkflow: (panelId: string) => void,
): void {
  panels.forEach((panel) => {
    resetWorkflow(panel.id)
  })
}

export function markPanelStreamComplete({
  panelId,
  totalPanelCount,
  completedPanelIds,
  onStreamingChange,
  onAllPanelsComplete,
}: {
  panelId: string
  totalPanelCount: number
  completedPanelIds: Set<string>
  onStreamingChange: StreamingChangeHandler
  onAllPanelsComplete: () => void
}): void {
  onStreamingChange(panelId, false)
  completedPanelIds.add(panelId)
  if (completedPanelIds.size === totalPanelCount) {
    onAllPanelsComplete()
  }
}

export function stopComposerPanelStreams({
  panels,
  streamingMessageIds,
  setAssistantStreaming,
  removeMessage,
  onStreamingChange,
  hasVisibleState = (panelId, messageId) =>
    hasVisibleAssistantState(panels, panelId, messageId),
}: {
  panels: ComposerPanel[]
  streamingMessageIds: Map<string, string>
  setAssistantStreaming: SetAssistantStreamingHandler
  removeMessage: RemoveMessageHandler
  onStreamingChange: StreamingChangeHandler
  hasVisibleState?: (panelId: string, messageId: string) => boolean
}): void {
  panels.forEach((panel) => {
    const messageId = streamingMessageIds.get(panel.id)
    if (messageId) {
      if (hasVisibleState(panel.id, messageId)) {
        setAssistantStreaming(panel.id, messageId, false)
      } else {
        removeMessage(panel.id, messageId)
      }
    }
    onStreamingChange(panel.id, false)
  })
  streamingMessageIds.clear()
}

export function finishComposerPanelStreams({
  panels,
  streamingMessageIds,
  onStreamingChange,
}: {
  panels: Array<Pick<Panel, 'id'>>
  streamingMessageIds: Map<string, string>
  onStreamingChange: StreamingChangeHandler
}): void {
  setAllPanelsStreaming(panels, false, onStreamingChange)
  streamingMessageIds.clear()
}

export function reportComposerStreamError({
  panels,
  streamingMessageIds,
  failure,
  errorMeta,
  setAssistantStreaming,
  addErrorMessage,
  onStreamingChange,
}: {
  panels: Array<Pick<Panel, 'id'>>
  streamingMessageIds: Map<string, string>
  failure: ComposerStreamFailure
  errorMeta: ErrorMessageMeta
  setAssistantStreaming: SetAssistantStreamingHandler
  addErrorMessage: AddErrorMessageHandler
  onStreamingChange: StreamingChangeHandler
}): void {
  panels.forEach((panel) => {
    const messageId = streamingMessageIds.get(panel.id)
    if (messageId) {
      setAssistantStreaming(panel.id, messageId, false)
    }
    addErrorMessage(
      panel.id,
      failure.content,
      failure.errorCode,
      failure.suggestion,
      errorMeta,
    )
    onStreamingChange(panel.id, false)
  })
  streamingMessageIds.clear()
}
