import { describe, expect, it, vi } from 'vitest'

import type { ChatFile, ChatImage } from '../../api/client'
import {
  createComposerSendPayload,
  restoreComposerDraftAfterFailure,
} from './composerSendPayload'

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

function buildPayload(overrides: Partial<Parameters<typeof createComposerSendPayload>[0]> = {}) {
  return createComposerSendPayload({
    input: ' hello ',
    images: [],
    files: [],
    pendingEditAnswerGroupId: null,
    currentSessionId: 'session-1',
    omitHistoryForNextSend: false,
    isLoading: false,
    isInteractionLocked: false,
    createAnswerGroupId: (preferred) => preferred || 'generated-answer-group',
    ...overrides,
  })
}

describe('composerSendPayload', () => {
  it('returns null when there is nothing to send or the composer is blocked', () => {
    expect(buildPayload({ input: '   ' })).toBeNull()
    expect(buildPayload({ isLoading: true })).toBeNull()
    expect(buildPayload({ isInteractionLocked: true })).toBeNull()
  })

  it('normalizes text messages and clones attachment arrays', () => {
    const images = [image]
    const files = [file]
    const payload = buildPayload({
      input: '  hello world  ',
      images,
      files,
      omitHistoryForNextSend: true,
    })

    expect(payload).toMatchObject({
      message: 'hello world',
      answerGroupId: 'generated-answer-group',
      sessionTitleSeed: 'hello world',
      omitHistoryForRequest: true,
      isEditRegenerationRequested: false,
    })
    expect(payload?.pendingImages).toEqual(images)
    expect(payload?.pendingImages).not.toBe(images)
    expect(payload?.pendingFiles).toEqual(files)
    expect(payload?.pendingFiles).not.toBe(files)
  })

  it('uses the first file or image fallback as the session title seed', () => {
    expect(buildPayload({ input: '', files: [file] })?.sessionTitleSeed).toBe('dataset.csv')
    expect(buildPayload({ input: '', images: [image] })?.sessionTitleSeed).toBe('Image chat')
  })

  it('reuses the edited answer group only when there is an active session', () => {
    const createAnswerGroupId = vi.fn((preferred?: string | null) => preferred || 'new-group')

    const editPayload = buildPayload({
      pendingEditAnswerGroupId: ' answer-group-1 ',
      currentSessionId: 'session-1',
      createAnswerGroupId,
    })
    const newSessionPayload = buildPayload({
      pendingEditAnswerGroupId: ' answer-group-1 ',
      currentSessionId: null,
      createAnswerGroupId,
    })

    expect(editPayload).toMatchObject({
      editingAnswerGroupId: 'answer-group-1',
      isEditRegenerationRequested: true,
      answerGroupId: 'answer-group-1',
    })
    expect(newSessionPayload).toMatchObject({
      editingAnswerGroupId: 'answer-group-1',
      isEditRegenerationRequested: false,
      answerGroupId: 'new-group',
    })
    expect(createAnswerGroupId).toHaveBeenNthCalledWith(1, 'answer-group-1')
    expect(createAnswerGroupId).toHaveBeenNthCalledWith(2, '')
  })

  it('restores the composer draft after a failed submit', () => {
    const payload = buildPayload({
      input: ' retry me ',
      images: [image],
      files: [file],
      pendingEditAnswerGroupId: 'answer-group-1',
      currentSessionId: 'session-1',
      omitHistoryForNextSend: true,
    })
    if (!payload) throw new Error('Expected payload')

    const setInput = vi.fn()
    const restoreAttachments = vi.fn()
    const setPendingEditAnswerGroupId = vi.fn()
    const setOmitHistoryForNextSend = vi.fn()
    const afterRestore = vi.fn()

    restoreComposerDraftAfterFailure({
      payload,
      setInput,
      restoreAttachments,
      setPendingEditAnswerGroupId,
      setOmitHistoryForNextSend,
      afterRestore,
    })

    expect(setInput).toHaveBeenCalledWith('retry me')
    expect(restoreAttachments).toHaveBeenCalledWith([image], [file])
    expect(setPendingEditAnswerGroupId).toHaveBeenCalledWith('answer-group-1')
    expect(setOmitHistoryForNextSend).toHaveBeenCalledWith(true)
    expect(afterRestore).toHaveBeenCalledTimes(1)
  })

  it('clears edit state on restore when the send was not an edit regeneration', () => {
    const payload = buildPayload({
      pendingEditAnswerGroupId: 'answer-group-1',
      currentSessionId: null,
    })
    if (!payload) throw new Error('Expected payload')

    const setPendingEditAnswerGroupId = vi.fn()

    restoreComposerDraftAfterFailure({
      payload,
      setInput: vi.fn(),
      restoreAttachments: vi.fn(),
      setPendingEditAnswerGroupId,
      setOmitHistoryForNextSend: vi.fn(),
    })

    expect(setPendingEditAnswerGroupId).toHaveBeenCalledWith(null)
  })
})
