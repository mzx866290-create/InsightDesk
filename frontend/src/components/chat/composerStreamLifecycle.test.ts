import { describe, expect, it, vi } from 'vitest'

import type { Panel } from '../../stores/chatStoreModel'
import { defaultModelConfig } from '../../stores/chatStoreModel'
import {
  createAssistantMessageIds,
  finishComposerPanelStreams,
  hasVisibleAssistantState,
  markPanelStreamComplete,
  replaceStreamingMessageIds,
  reportComposerStreamError,
  resetPanelWorkflows,
  setAllPanelsStreaming,
  stopComposerPanelStreams,
} from './composerStreamLifecycle'

function panel(id: string, messages: Panel['messages'] = []): Panel {
  return {
    id,
    modelConfig: defaultModelConfig(id),
    messages,
  }
}

describe('composerStreamLifecycle', () => {
  it('detects whether a streaming assistant placeholder has visible state', () => {
    const panels = [
      panel('panel-1', [
        { id: 'blank', role: 'assistant', content: '   ' },
        { id: 'content', role: 'assistant', content: 'answer' },
        { id: 'source', role: 'assistant', content: '', sources: [{} as never] },
        { id: 'task', role: 'assistant', content: '', taskId: 'task-1' },
        { id: 'user', role: 'user', content: 'hello' },
      ]),
    ]

    expect(hasVisibleAssistantState(panels, 'panel-1', 'blank')).toBe(false)
    expect(hasVisibleAssistantState(panels, 'panel-1', 'content')).toBe(true)
    expect(hasVisibleAssistantState(panels, 'panel-1', 'source')).toBe(true)
    expect(hasVisibleAssistantState(panels, 'panel-1', 'task')).toBe(true)
    expect(hasVisibleAssistantState(panels, 'panel-1', 'user')).toBe(false)
    expect(hasVisibleAssistantState(panels, 'missing', 'content')).toBe(false)
  })

  it('creates and replaces assistant message id maps', () => {
    const ids = createAssistantMessageIds(
      [panel('panel-1'), panel('panel-2')],
      () => 1234,
    )
    const target = new Map([['old-panel', 'old-message']])

    replaceStreamingMessageIds(target, ids)

    expect([...target.entries()]).toEqual([
      ['panel-1', 'assistant-panel-1-1234'],
      ['panel-2', 'assistant-panel-2-1234'],
    ])
  })

  it('sets streaming state and resets workflows for all panels', () => {
    const onStreamingChange = vi.fn()
    const resetWorkflow = vi.fn()
    const panels = [panel('panel-1'), panel('panel-2')]

    setAllPanelsStreaming(panels, true, onStreamingChange)
    resetPanelWorkflows(panels, resetWorkflow)

    expect(onStreamingChange).toHaveBeenCalledWith('panel-1', true)
    expect(onStreamingChange).toHaveBeenCalledWith('panel-2', true)
    expect(resetWorkflow).toHaveBeenCalledWith('panel-1')
    expect(resetWorkflow).toHaveBeenCalledWith('panel-2')
  })

  it('marks panels complete and fires the all-done callback once all panels finish', () => {
    const onStreamingChange = vi.fn()
    const onAllPanelsComplete = vi.fn()
    const completedPanelIds = new Set<string>()

    markPanelStreamComplete({
      panelId: 'panel-1',
      totalPanelCount: 2,
      completedPanelIds,
      onStreamingChange,
      onAllPanelsComplete,
    })
    markPanelStreamComplete({
      panelId: 'panel-2',
      totalPanelCount: 2,
      completedPanelIds,
      onStreamingChange,
      onAllPanelsComplete,
    })

    expect(onStreamingChange).toHaveBeenCalledWith('panel-1', false)
    expect(onStreamingChange).toHaveBeenCalledWith('panel-2', false)
    expect(onAllPanelsComplete).toHaveBeenCalledTimes(1)
  })

  it('stops streams by removing blank placeholders and preserving visible assistant messages', () => {
    const streamingMessageIds = new Map([
      ['panel-1', 'blank'],
      ['panel-2', 'content'],
    ])
    const setAssistantStreaming = vi.fn()
    const removeMessage = vi.fn()
    const onStreamingChange = vi.fn()

    stopComposerPanelStreams({
      panels: [
        panel('panel-1', [{ id: 'blank', role: 'assistant', content: '' }]),
        panel('panel-2', [{ id: 'content', role: 'assistant', content: 'answer' }]),
      ],
      streamingMessageIds,
      setAssistantStreaming,
      removeMessage,
      onStreamingChange,
    })

    expect(removeMessage).toHaveBeenCalledWith('panel-1', 'blank')
    expect(setAssistantStreaming).toHaveBeenCalledWith('panel-2', 'content', false)
    expect(onStreamingChange).toHaveBeenCalledWith('panel-1', false)
    expect(onStreamingChange).toHaveBeenCalledWith('panel-2', false)
    expect(streamingMessageIds.size).toBe(0)
  })

  it('finishes all panel streams and clears tracked message ids', () => {
    const streamingMessageIds = new Map([['panel-1', 'assistant-1']])
    const onStreamingChange = vi.fn()

    finishComposerPanelStreams({
      panels: [panel('panel-1'), panel('panel-2')],
      streamingMessageIds,
      onStreamingChange,
    })

    expect(onStreamingChange).toHaveBeenCalledWith('panel-1', false)
    expect(onStreamingChange).toHaveBeenCalledWith('panel-2', false)
    expect(streamingMessageIds.size).toBe(0)
  })

  it('reports stream errors to every panel and clears tracked message ids', () => {
    const streamingMessageIds = new Map([
      ['panel-1', 'assistant-1'],
      ['panel-2', 'assistant-2'],
    ])
    const setAssistantStreaming = vi.fn()
    const addErrorMessage = vi.fn()
    const onStreamingChange = vi.fn()

    reportComposerStreamError({
      panels: [panel('panel-1'), panel('panel-2')],
      streamingMessageIds,
      failure: {
        content: 'Request failed',
        errorCode: 'REQUEST_FAILED',
        suggestion: 'Try again',
      },
      errorMeta: {
        answerGroupId: 'answer-group-1',
        retryMode: 'rerun',
      },
      setAssistantStreaming,
      addErrorMessage,
      onStreamingChange,
    })

    expect(setAssistantStreaming).toHaveBeenCalledWith('panel-1', 'assistant-1', false)
    expect(setAssistantStreaming).toHaveBeenCalledWith('panel-2', 'assistant-2', false)
    expect(addErrorMessage).toHaveBeenCalledWith(
      'panel-1',
      'Request failed',
      'REQUEST_FAILED',
      'Try again',
      { answerGroupId: 'answer-group-1', retryMode: 'rerun' },
    )
    expect(addErrorMessage).toHaveBeenCalledWith(
      'panel-2',
      'Request failed',
      'REQUEST_FAILED',
      'Try again',
      { answerGroupId: 'answer-group-1', retryMode: 'rerun' },
    )
    expect(streamingMessageIds.size).toBe(0)
  })
})
