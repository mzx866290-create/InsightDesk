import type { UserMessagePatch } from '../../stores/chatMessageModel'
import type { ComposerSendPayload } from './composerSendPayload'

type EditRegenerationPayload = Pick<
  ComposerSendPayload,
  'answerGroupId' | 'message' | 'pendingImages' | 'pendingFiles'
>

interface ApplyComposerEditRegenerationOptions {
  sessionId: string
  payload: EditRegenerationPayload
  truncateSessionMessagesFromAnswerGroup: (
    sessionId: string,
    payload: {
      answer_group_id: string
      content: string
      images: EditRegenerationPayload['pendingImages']
      files: EditRegenerationPayload['pendingFiles']
    },
  ) => Promise<unknown>
  truncateMessagesFromAnswerGroup: (
    answerGroupId: string,
    userPatch: UserMessagePatch,
  ) => void
  now?: () => number
}

export async function applyComposerEditRegeneration({
  sessionId,
  payload,
  truncateSessionMessagesFromAnswerGroup,
  truncateMessagesFromAnswerGroup,
  now = Date.now,
}: ApplyComposerEditRegenerationOptions): Promise<void> {
  await truncateSessionMessagesFromAnswerGroup(sessionId, {
    answer_group_id: payload.answerGroupId,
    content: payload.message,
    images: payload.pendingImages,
    files: payload.pendingFiles,
  })

  truncateMessagesFromAnswerGroup(payload.answerGroupId, {
    content: payload.message,
    images: payload.pendingImages,
    files: payload.pendingFiles,
    timestamp: now() / 1000,
  })
}
