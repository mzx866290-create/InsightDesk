import type { ChatFile, ChatImage } from '../../api/client'

export interface ComposerSendPayloadOptions {
  input: string
  images: ChatImage[]
  files: ChatFile[]
  pendingEditAnswerGroupId: string | null
  currentSessionId: string | null
  omitHistoryForNextSend: boolean
  isLoading: boolean
  isInteractionLocked: boolean
  createAnswerGroupId: (preferredAnswerGroupId?: string | null) => string
}

export interface ComposerSendPayload {
  message: string
  pendingImages: ChatImage[]
  pendingFiles: ChatFile[]
  editingAnswerGroupId: string
  isEditRegenerationRequested: boolean
  omitHistoryForRequest: boolean
  answerGroupId: string
  sessionTitleSeed: string
}

export interface RestoreComposerDraftOptions {
  payload: ComposerSendPayload
  setInput: (value: string) => void
  restoreAttachments: (nextImages: ChatImage[], nextFiles: ChatFile[]) => void
  setPendingEditAnswerGroupId: (value: string | null) => void
  setOmitHistoryForNextSend: (value: boolean) => void
  afterRestore?: () => void
}

export function createComposerSendPayload({
  input,
  images,
  files,
  pendingEditAnswerGroupId,
  currentSessionId,
  omitHistoryForNextSend,
  isLoading,
  isInteractionLocked,
  createAnswerGroupId,
}: ComposerSendPayloadOptions): ComposerSendPayload | null {
  const message = input.trim()
  const pendingImages = [...images]
  const pendingFiles = [...files]
  const editingAnswerGroupId = pendingEditAnswerGroupId?.trim() || ''
  const isEditRegenerationRequested = Boolean(editingAnswerGroupId && currentSessionId)

  if (
    (message.length === 0 && pendingImages.length === 0 && pendingFiles.length === 0) ||
    isLoading ||
    isInteractionLocked
  ) {
    return null
  }

  return {
    message,
    pendingImages,
    pendingFiles,
    editingAnswerGroupId,
    isEditRegenerationRequested,
    omitHistoryForRequest: omitHistoryForNextSend,
    answerGroupId: createAnswerGroupId(
      isEditRegenerationRequested ? editingAnswerGroupId : '',
    ),
    sessionTitleSeed:
      message ||
      (pendingFiles.length > 0 ? pendingFiles[0].name : '') ||
      (pendingImages.length > 0 ? 'Image chat' : ''),
  }
}

export function restoreComposerDraftAfterFailure({
  payload,
  setInput,
  restoreAttachments,
  setPendingEditAnswerGroupId,
  setOmitHistoryForNextSend,
  afterRestore,
}: RestoreComposerDraftOptions): void {
  setInput(payload.message)
  restoreAttachments(payload.pendingImages, payload.pendingFiles)
  setPendingEditAnswerGroupId(
    payload.isEditRegenerationRequested ? payload.editingAnswerGroupId : null,
  )
  setOmitHistoryForNextSend(payload.omitHistoryForRequest)
  afterRestore?.()
}
