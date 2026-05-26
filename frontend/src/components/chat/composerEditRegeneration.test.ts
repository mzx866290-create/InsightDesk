import { describe, expect, it, vi } from 'vitest'

import type { ChatFile, ChatImage } from '../../api/client'
import { applyComposerEditRegeneration } from './composerEditRegeneration'

const image: ChatImage = {
  name: 'diagram.png',
  media_type: 'image/png',
  data_url: 'data:image/png;base64,abc',
}

const file: ChatFile = {
  name: 'dataset.csv',
  media_type: 'text/csv',
  data_url: 'data:text/csv;base64,abc',
  size_bytes: 128,
}

describe('applyComposerEditRegeneration', () => {
  it('truncates the remote session before replacing the local answer group', async () => {
    const truncateSessionMessagesFromAnswerGroup = vi.fn().mockResolvedValue({})
    const truncateMessagesFromAnswerGroup = vi.fn()

    await applyComposerEditRegeneration({
      sessionId: 'session-1',
      payload: {
        answerGroupId: 'answer-group-1',
        message: 'updated prompt',
        pendingImages: [image],
        pendingFiles: [file],
      },
      truncateSessionMessagesFromAnswerGroup,
      truncateMessagesFromAnswerGroup,
      now: () => 123_456,
    })

    expect(truncateSessionMessagesFromAnswerGroup).toHaveBeenCalledWith('session-1', {
      answer_group_id: 'answer-group-1',
      content: 'updated prompt',
      images: [image],
      files: [file],
    })
    expect(truncateMessagesFromAnswerGroup).toHaveBeenCalledWith('answer-group-1', {
      content: 'updated prompt',
      images: [image],
      files: [file],
      timestamp: 123.456,
    })
  })

  it('does not mutate local messages when remote truncation fails', async () => {
    const error = new Error('truncate failed')
    const truncateSessionMessagesFromAnswerGroup = vi.fn().mockRejectedValue(error)
    const truncateMessagesFromAnswerGroup = vi.fn()

    await expect(
      applyComposerEditRegeneration({
        sessionId: 'session-1',
        payload: {
          answerGroupId: 'answer-group-1',
          message: 'updated prompt',
          pendingImages: [],
          pendingFiles: [],
        },
        truncateSessionMessagesFromAnswerGroup,
        truncateMessagesFromAnswerGroup,
      }),
    ).rejects.toThrow(error)

    expect(truncateMessagesFromAnswerGroup).not.toHaveBeenCalled()
  })
})
