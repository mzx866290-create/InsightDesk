import { describe, expect, it, vi } from 'vitest'

import type { Bookmark, Message, ModelConfig, Session, SourceItem, Workspace } from '../api/client'
import {
  addPanelToList,
  addErrorMessageToPanels,
  addOrReplaceBookmark,
  createBookmarkActions,
  addSessionToList,
  addUserMessageToPanelState,
  adjustWorkspaceSessionCount,
  appendChunkToMessages,
  appendChunkToPanel,
  applyCloudModelProfileToPanels,
  applyModelPresetToPanels,
  clearMessagesFromPanelList,
  buildComposerSeed,
  createMessageActions,
  createErrorMessage,
  createUserMessage,
  defaultComposerSeed,
  defaultEnabledMcpServers,
  defaultModelConfig,
  getNextLanguage,
  getNextTheme,
  hasBookmark,
  addUserMessageToPanels,
  loadMessagesIntoAllPanels,
  loadMessagesIntoPanel,
  mapMessages,
  mergeRemoteBookmarksWithLocalLegacy,
  migrateChatStoreState,
  normalizeBookmarkMessage,
  normalizeEnabledMcpServers,
  normalizePanels,
  patchSession,
  patchWorkspace,
  partializeChatStoreState,
  replaceAssistantMessageByAnswerGroup,
  replaceAssistantMessageByAnswerGroupInPanel,
  removeBookmarkById,
  removeCloudModelProfileById,
  removePanelFromList,
  removeMessageFromMessages,
  removeMessageFromPanel,
  removeModelPresetById,
  removeSessionFromList,
  saveCloudModelProfile,
  saveModelPreset,
  sameBookmarkTarget,
  sanitizePersistedModelConfig,
  setAssistantMessageInMessages,
  setAssistantStreamingInMessages,
  setAttachmentWorkspaceState,
  setMemoryWorkspaceState,
  setSourcesInMessages,
  setSourcesInPanel,
  setTaskIdInMessages,
  sortBookmarks,
  sortSessionsByUpdatedAt,
  sortWorkspaces,
  toggleAttachmentWorkspaceState,
  toggleMemoryWorkspaceState,
  truncateAnswerGroupFromPanels,
  truncatePanelMessagesFromAnswerGroup,
  updateMessageInMessages,
  updateMessageInPanel,
  updatePanelModelConfig,
  upsertWorkspace,
} from './chatStoreModel'
import type { Panel, PanelMessage } from './chatStoreModel'

function makeSession(patch: Partial<Session> & Pick<Session, 'session_id'>): Session {
  return {
    session_id: patch.session_id,
    title: patch.title ?? patch.session_id,
    created_at: patch.created_at ?? 1,
    updated_at: patch.updated_at ?? 1,
    message_count: patch.message_count ?? 0,
    is_archived: patch.is_archived ?? false,
    is_favorite: patch.is_favorite ?? false,
    is_pinned: patch.is_pinned ?? false,
    session_order: patch.session_order ?? 0,
    tags: patch.tags ?? [],
    workspace_id: patch.workspace_id ?? 'workspace-1',
  }
}

function makeWorkspace(
  patch: Partial<Workspace> & Pick<Workspace, 'workspace_id'>,
): Workspace {
  return {
    workspace_id: patch.workspace_id,
    name: patch.name ?? patch.workspace_id,
    description: patch.description ?? '',
    color: patch.color ?? 'slate',
    is_active: patch.is_active ?? false,
    created_at: patch.created_at ?? 1,
    updated_at: patch.updated_at ?? 1,
    session_count: patch.session_count ?? 0,
  }
}

function makeBookmark(patch: Partial<Bookmark> & Pick<Bookmark, 'id'>): Bookmark {
  return {
    id: patch.id,
    sessionId: patch.sessionId ?? 'session-1',
    sessionTitle: patch.sessionTitle ?? 'Session',
    messageId: patch.messageId,
    panelId: patch.panelId ?? 'panel-1',
    answerGroupId: patch.answerGroupId ?? 'answer-1',
    role: patch.role ?? 'assistant',
    content: patch.content ?? 'content',
    modelId: patch.modelId,
    createdAt: patch.createdAt ?? 100,
    updatedAt: patch.updatedAt ?? 100,
    source: patch.source,
  }
}

function createMessageActionHarness(panels: Panel[]) {
  const state = { panels }
  const set = (updater: (value: typeof state) => Pick<typeof state, 'panels'>) => {
    Object.assign(state, updater(state))
  }

  return {
    state,
    actions: createMessageActions(set),
  }
}

describe('chatStoreModel', () => {
  it('sorts sessions by pinned state, manual order, and latest update', () => {
    const sorted = sortSessionsByUpdatedAt([
      makeSession({ session_id: 'old', updated_at: 10 }),
      makeSession({ session_id: 'ranked-low', updated_at: 20, session_order: 1 }),
      makeSession({ session_id: 'pinned', updated_at: 5, is_pinned: true }),
      makeSession({ session_id: 'ranked-high', updated_at: 1, session_order: 3 }),
      makeSession({ session_id: 'latest', updated_at: 30 }),
    ])

    expect(sorted.map((session) => session.session_id)).toEqual([
      'pinned',
      'ranked-high',
      'ranked-low',
      'latest',
      'old',
    ])
  })

  it('sorts active workspaces first and then by latest update', () => {
    const sorted = sortWorkspaces([
      makeWorkspace({ workspace_id: 'inactive-new', updated_at: 30 }),
      makeWorkspace({ workspace_id: 'active-old', is_active: true, updated_at: 10 }),
      makeWorkspace({ workspace_id: 'inactive-old', updated_at: 1 }),
      makeWorkspace({ workspace_id: 'active-new', is_active: true, updated_at: 20 }),
    ])

    expect(sorted.map((workspace) => workspace.workspace_id)).toEqual([
      'active-new',
      'active-old',
      'inactive-new',
      'inactive-old',
    ])
  })

  it('upserts and patches workspaces while preserving workspace ordering rules', () => {
    const existing = [
      makeWorkspace({ workspace_id: 'inactive-old', updated_at: 1 }),
      makeWorkspace({ workspace_id: 'active-old', is_active: true, updated_at: 10 }),
    ]

    const inserted = upsertWorkspace(
      existing,
      makeWorkspace({ workspace_id: 'active-new', is_active: true, updated_at: 30 }),
    )
    expect(inserted.map((workspace) => workspace.workspace_id)).toEqual([
      'active-new',
      'active-old',
      'inactive-old',
    ])

    const replaced = upsertWorkspace(
      inserted,
      makeWorkspace({ workspace_id: 'active-old', is_active: false, updated_at: 40 }),
    )
    expect(replaced.map((workspace) => workspace.workspace_id)).toEqual([
      'active-new',
      'active-old',
      'inactive-old',
    ])
    expect(replaced.filter((workspace) => workspace.workspace_id === 'active-old')).toHaveLength(1)
    expect(replaced.find((workspace) => workspace.workspace_id === 'active-old')).toMatchObject({
      is_active: false,
      updated_at: 40,
    })

    const patched = patchWorkspace(replaced, 'inactive-old', {
      is_active: true,
      updated_at: 50,
    })
    expect(patched.map((workspace) => workspace.workspace_id)).toEqual([
      'inactive-old',
      'active-new',
      'active-old',
    ])
  })

  it('adjusts workspace session counts without going below zero', () => {
    const workspaces = [
      makeWorkspace({ workspace_id: 'workspace-1', session_count: 1, updated_at: 10 }),
      makeWorkspace({ workspace_id: 'workspace-2', session_count: 3, updated_at: 20 }),
    ]

    const decremented = adjustWorkspaceSessionCount(workspaces, 'workspace-1', -5)
    expect(decremented.find((workspace) => workspace.workspace_id === 'workspace-1'))
      .toMatchObject({ session_count: 0 })

    const incremented = adjustWorkspaceSessionCount(workspaces, 'workspace-2', 2)
    expect(incremented.find((workspace) => workspace.workspace_id === 'workspace-2'))
      .toMatchObject({ session_count: 5 })
  })

  it('adds, removes, and patches sessions through sortable list helpers', () => {
    const sessions = [
      makeSession({ session_id: 'old', updated_at: 10 }),
      makeSession({ session_id: 'latest', updated_at: 30 }),
    ]

    const added = addSessionToList(
      sessions,
      makeSession({ session_id: 'pinned', updated_at: 1, is_pinned: true }),
    )
    expect(added.map((session) => session.session_id)).toEqual([
      'pinned',
      'latest',
      'old',
    ])

    const removed = removeSessionFromList(added, 'latest')
    expect(removed.map((session) => session.session_id)).toEqual(['pinned', 'old'])

    const patched = patchSession(removed, 'old', {
      title: 'Renamed',
      updated_at: 99,
    })
    expect(patched.map((session) => session.session_id)).toEqual(['pinned', 'old'])
    expect(patched.find((session) => session.session_id === 'old')).toMatchObject({
      title: 'Renamed',
      updated_at: 99,
    })
  })

  it('adds and removes panels while respecting panel count boundaries', () => {
    const panel = { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] }
    const added = addPanelToList([panel], () => ({
      id: 'panel-2',
      modelConfig: defaultModelConfig('panel-2'),
      messages: [],
    }))

    expect(added.map((item) => item.id)).toEqual(['panel-1', 'panel-2'])
    expect(removePanelFromList([panel], 'panel-1')).toEqual([panel])
    expect(removePanelFromList(added, 'panel-1').map((item) => item.id)).toEqual(['panel-2'])

    const fullPanels = Array.from({ length: 6 }, (_, index) => ({
      id: `panel-${index}`,
      modelConfig: defaultModelConfig(`panel-${index}`),
      messages: [],
    }))
    expect(addPanelToList(fullPanels, () => panel)).toBe(fullPanels)
  })

  it('updates and normalizes panel model configs with the panel id as source of truth', () => {
    const panels: Panel[] = [
      { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] },
      { id: 'panel-2', modelConfig: defaultModelConfig('panel-2'), messages: [] },
    ]

    const updated = updatePanelModelConfig(panels, 'panel-2', {
      model: 'updated-model',
      panel_id: 'wrong-panel',
    })
    expect(updated[0]).toBe(panels[0])
    expect(updated[1].modelConfig).toMatchObject({
      model: 'updated-model',
      panel_id: 'panel-2',
    })

    const normalized = normalizePanels([
      {
        id: 'panel-normalized',
        modelConfig: { ...defaultModelConfig('old-panel'), panel_id: 'old-panel' },
        messages: [{ id: 'msg-1', role: 'user', content: 'kept' }],
      },
    ])
    expect(normalized[0].modelConfig.panel_id).toBe('panel-normalized')
    expect(normalized[0].messages).toEqual([{ id: 'msg-1', role: 'user', content: 'kept' }])
  })

  it('creates user and error messages with deterministic timestamps and ids', () => {
    const user = createUserMessage(
      'hello',
      [{ name: 'image.png', media_type: 'image/png', data_url: 'data:' }],
      [{ name: 'doc.txt', media_type: 'text/plain', size_bytes: 10 }],
      'answer-1',
      { now: () => 1_000 },
    )
    expect(user).toMatchObject({
      id: 'msg-1000',
      role: 'user',
      content: 'hello',
      answerGroupId: 'answer-1',
      timestamp: 1,
    })

    const error = createErrorMessage(
      'panel-1',
      'failed',
      'E_TEST',
      'retry',
      { answerGroupId: 'answer-1', retryMode: 'continue' },
      { now: () => 2_000, randomSuffix: () => 'abcd' },
    )
    expect(error).toMatchObject({
      id: 'error-2000-abcd',
      role: 'error',
      content: 'failed',
      errorCode: 'E_TEST',
      suggestion: 'retry',
      panelId: 'panel-1',
      answerGroupId: 'answer-1',
      retryMode: 'continue',
      timestamp: 2,
    })
  })

  it('replaces retry errors for the same answer group and retry mode', () => {
    const panels: Panel[] = [
      { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] },
    ]

    const first = addErrorMessageToPanels(
      panels,
      'panel-1',
      'auth failed',
      'AUTH_FAILED',
      'check key',
      { answerGroupId: 'answer-1', retryMode: 'rerun' },
      { now: () => 1_000, randomSuffix: () => 'aaaa' },
    )
    const second = addErrorMessageToPanels(
      first,
      'panel-1',
      'auth failed again',
      'AUTH_FAILED',
      'check key again',
      { answerGroupId: 'answer-1', retryMode: 'rerun' },
      { now: () => 2_000, randomSuffix: () => 'bbbb' },
    )

    const errors = second[0].messages.filter((message) => message.role === 'error')
    expect(errors).toHaveLength(1)
    expect(errors[0]).toMatchObject({
      id: 'error-2000-bbbb',
      content: 'auth failed again',
      answerGroupId: 'answer-1',
      retryMode: 'rerun',
    })
  })

  it('clears stale answer-group errors when replacement content arrives', () => {
    const messages: PanelMessage[] = [
      { id: 'user-1', role: 'user', content: 'question', answerGroupId: 'answer-1' },
      { id: 'assistant-1', role: 'assistant', content: 'old', answerGroupId: 'answer-1' },
      { id: 'error-1', role: 'error', content: 'auth failed', answerGroupId: 'answer-1' },
      { id: 'error-2', role: 'error', content: 'other failed', answerGroupId: 'answer-2' },
    ]
    const panels: Panel[] = [
      { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages },
    ]
    const sources: SourceItem[] = [{ type: 'web', title: 'Doc', snippet: 'Snippet' }]

    const replaced = replaceAssistantMessageByAnswerGroup(messages, 'answer-1', {
      content: 'new',
      streaming: false,
    })
    expect(replaced.map((message) => message.id)).toEqual([
      'user-1',
      'assistant-1',
      'error-2',
    ])
    expect(replaced[1]).toMatchObject({ content: 'new', streaming: false })

    const chunked = appendChunkToPanel(
      panels,
      'panel-1',
      'assistant-1',
      ' chunk',
      { answerGroupId: 'answer-1' },
    )
    expect(chunked[0].messages.map((message) => message.id)).toEqual([
      'user-1',
      'assistant-1',
      'error-2',
    ])
    expect(chunked[0].messages[1].content).toBe('old chunk')

    const withSources = setSourcesInPanel(
      panels,
      'panel-1',
      'assistant-1',
      sources,
      { answerGroupId: 'answer-1' },
    )
    expect(withSources[0].messages.map((message) => message.id)).toEqual([
      'user-1',
      'assistant-1',
      'error-2',
    ])
    expect(withSources[0].messages[1].sources).toEqual(sources)
  })

  it('upserts assistant streaming messages when chunks or sources arrive first', () => {
    const sources: SourceItem[] = [{ type: 'web', title: 'Doc', snippet: 'Snippet' }]
    const createdByChunk = appendChunkToMessages(
      [],
      'panel-1',
      'assistant-1',
      'hello',
      { modelId: 'qwen', answerGroupId: 'answer-1' },
      { now: () => 1_000 },
    )

    expect(createdByChunk[0]).toMatchObject({
      id: 'assistant-1',
      role: 'assistant',
      content: 'hello',
      streaming: true,
      modelId: 'qwen',
      panelId: 'panel-1',
      answerGroupId: 'answer-1',
      timestamp: 1,
      feedbackValue: 0,
    })

    const appended = appendChunkToMessages(createdByChunk, 'panel-1', 'assistant-1', ' world')
    expect(appended[0]).toMatchObject({ content: 'hello world', streaming: true })

    const createdBySources = setSourcesInMessages(
      [],
      'panel-1',
      'assistant-2',
      sources,
      { modelId: 'qwen', answerGroupId: 'answer-2' },
      { now: () => 2_000 },
    )
    expect(createdBySources[0]).toMatchObject({
      id: 'assistant-2',
      role: 'assistant',
      content: '',
      streaming: true,
      sources,
      modelId: 'qwen',
      panelId: 'panel-1',
      answerGroupId: 'answer-2',
      timestamp: 2,
      feedbackValue: 0,
    })
    expect(setSourcesInMessages(createdByChunk, 'panel-1', 'assistant-1', sources)[0].sources)
      .toEqual(sources)
  })

  it('patches common message fields through message-list helpers', () => {
    const messages: PanelMessage[] = [
      { id: 'assistant-1', role: 'assistant', content: 'old', streaming: true },
      { id: 'assistant-2', role: 'assistant', content: 'keep' },
    ]

    expect(setAssistantMessageInMessages(messages, 'assistant-1', 'new', false)[0])
      .toMatchObject({ content: 'new', streaming: false })
    expect(setAssistantStreamingInMessages(messages, 'assistant-1', false)[0])
      .toMatchObject({ streaming: false })
    expect(setTaskIdInMessages(messages, 'assistant-1', 'task-1', 'chat')[0])
      .toMatchObject({ taskId: 'task-1', taskType: 'chat' })
    expect(updateMessageInMessages(messages, 'assistant-1', { feedbackValue: 1 })[0])
      .toMatchObject({ feedbackValue: 1 })
    expect(removeMessageFromMessages(messages, 'assistant-1').map((message) => message.id))
      .toEqual(['assistant-2'])
  })

  it('applies message helpers only to the target panel', () => {
    const panels: Panel[] = [
      {
        id: 'panel-1',
        modelConfig: defaultModelConfig('panel-1'),
        messages: [{ id: 'assistant-1', role: 'assistant', content: 'old' }],
      },
      {
        id: 'panel-2',
        modelConfig: defaultModelConfig('panel-2'),
        messages: [{ id: 'assistant-2', role: 'assistant', content: 'keep' }],
      },
    ]
    const sources: SourceItem[] = [{ type: 'web', title: 'Doc', snippet: 'Snippet' }]

    const appended = appendChunkToPanel(panels, 'panel-1', 'assistant-1', ' chunk')
    expect(appended[0].messages[0]).toMatchObject({ content: 'old chunk' })
    expect(appended[1]).toBe(panels[1])

    const withSources = setSourcesInPanel(panels, 'panel-1', 'assistant-1', sources)
    expect(withSources[0].messages[0].sources).toEqual(sources)
    expect(withSources[1]).toBe(panels[1])

    const withError = addErrorMessageToPanels(
      panels,
      'panel-1',
      'failed',
      undefined,
      undefined,
      {},
      { now: () => 1_000, randomSuffix: () => 'abcd' },
    )
    expect(withError[0].messages[withError[0].messages.length - 1]).toMatchObject({
      id: 'error-1000-abcd',
      role: 'error',
    })
    expect(updateMessageInPanel(panels, 'panel-1', 'assistant-1', { content: 'patched' })[0]
      .messages[0].content).toBe('patched')
    expect(removeMessageFromPanel(panels, 'panel-1', 'assistant-1')[0].messages).toEqual([])
    expect(clearMessagesFromPanelList(panels).every((panel) => panel.messages.length === 0))
      .toBe(true)
  })

  it('maps backend messages into panel messages without dropping metadata', () => {
    const messages: Message[] = [
      {
        id: 42,
        role: 'assistant',
        content: 'answer',
        model_id: 'qwen',
        panel_id: 'panel-1',
        answer_group_id: 'answer-1',
        task_id: 'task-1',
        task_type: 'chat',
        token_usage: {
          prompt_tokens: 10,
          completion_tokens: 5,
          total_tokens: 15,
          estimated: false,
        },
        timestamp: 123,
        feedback_value: 1,
        sources: [{ type: 'web', title: 'Doc', snippet: 'Snippet' }],
        images: [{ name: 'image.png', media_type: 'image/png', data_url: 'data:' }],
        files: [{ name: 'file.txt', media_type: 'text/plain', size_bytes: 4 }],
      },
      {
        role: 'user',
        content: 'question',
      },
    ]

    expect(mapMessages(messages)).toEqual([
      {
        id: 'db-42',
        serverMessageId: 42,
        role: 'assistant',
        content: 'answer',
        images: messages[0].images,
        files: messages[0].files,
        sources: messages[0].sources,
        modelId: 'qwen',
        panelId: 'panel-1',
        answerGroupId: 'answer-1',
        taskId: 'task-1',
        taskType: 'chat',
        workflowNodes: undefined,
        tokenUsage: messages[0].token_usage,
        timestamp: 123,
        feedbackValue: 1,
      },
      {
        id: 'loaded-1',
        serverMessageId: undefined,
        role: 'user',
        content: 'question',
        images: undefined,
        files: undefined,
        sources: undefined,
        modelId: undefined,
        panelId: undefined,
        answerGroupId: undefined,
        taskId: undefined,
        taskType: undefined,
        workflowNodes: undefined,
        tokenUsage: undefined,
        timestamp: undefined,
        feedbackValue: undefined,
      },
    ])
  })

  it('loads backend messages into all panels or only the requested panel', () => {
    const panels: Panel[] = [
      {
        id: 'panel-1',
        modelConfig: defaultModelConfig('panel-1'),
        messages: [{ id: 'old-1', role: 'user', content: 'old 1' }],
      },
      {
        id: 'panel-2',
        modelConfig: defaultModelConfig('panel-2'),
        messages: [{ id: 'old-2', role: 'assistant', content: 'old 2' }],
      },
    ]
    const messages: Message[] = [
      {
        id: 7,
        role: 'user',
        content: 'loaded',
        answer_group_id: 'answer-1',
      },
    ]

    const allPanels = loadMessagesIntoAllPanels(panels, messages)
    expect(allPanels.map((panel) => panel.messages[0])).toEqual([
      expect.objectContaining({ id: 'db-7', content: 'loaded', answerGroupId: 'answer-1' }),
      expect.objectContaining({ id: 'db-7', content: 'loaded', answerGroupId: 'answer-1' }),
    ])

    const targetPanel = loadMessagesIntoPanel(panels, 'panel-2', messages)
    expect(targetPanel[0]).toBe(panels[0])
    expect(targetPanel[1].messages).toEqual([
      expect.objectContaining({ id: 'db-7', content: 'loaded' }),
    ])
  })

  it('adds a copied user message to every panel without sharing message references', () => {
    const panels: Panel[] = [
      { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] },
      { id: 'panel-2', modelConfig: defaultModelConfig('panel-2'), messages: [] },
    ]
    const message: PanelMessage = {
      id: 'user-1',
      role: 'user',
      content: 'question',
      answerGroupId: 'answer-1',
    }

    const updated = addUserMessageToPanels(panels, message)

    expect(updated.map((panel) => panel.messages[0])).toEqual([
      message,
      message,
    ])
    expect(updated[0].messages[0]).not.toBe(message)
    expect(updated[0].messages[0]).not.toBe(updated[1].messages[0])
  })

  it('builds a user message panel state update and returns the created message id', () => {
    const panels: Panel[] = [
      { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] },
      { id: 'panel-2', modelConfig: defaultModelConfig('panel-2'), messages: [] },
    ]

    const result = addUserMessageToPanelState(
      panels,
      'question',
      [{ name: 'image.png', media_type: 'image/png', data_url: 'data:' }],
      [{ name: 'doc.txt', media_type: 'text/plain', size_bytes: 10 }],
      'answer-1',
      { now: () => 1_000 },
    )

    expect(result.messageId).toBe('msg-1000')
    expect(result.panels.map((panel) => panel.messages[0])).toEqual([
      expect.objectContaining({
        id: 'msg-1000',
        role: 'user',
        content: 'question',
        answerGroupId: 'answer-1',
        timestamp: 1,
      }),
      expect.objectContaining({
        id: 'msg-1000',
        role: 'user',
        content: 'question',
        answerGroupId: 'answer-1',
        timestamp: 1,
      }),
    ])
    expect(result.panels[0].messages[0]).not.toBe(result.panels[1].messages[0])
  })

  it('builds message actions that add a user message and return its id', () => {
    vi.useFakeTimers()
    vi.setSystemTime(1_000)

    try {
      const { state, actions } = createMessageActionHarness([
        { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] },
        { id: 'panel-2', modelConfig: defaultModelConfig('panel-2'), messages: [] },
      ])

      const messageId = actions.addUserMessage(
        'question',
        [{ name: 'image.png', media_type: 'image/png', data_url: 'data:' }],
        [{ name: 'doc.txt', media_type: 'text/plain', size_bytes: 10 }],
        'answer-1',
      )

      expect(messageId).toBe('msg-1000')
      expect(state.panels.map((panel) => panel.messages[0])).toEqual([
        expect.objectContaining({ id: 'msg-1000', content: 'question', answerGroupId: 'answer-1' }),
        expect.objectContaining({ id: 'msg-1000', content: 'question', answerGroupId: 'answer-1' }),
      ])
      expect(state.panels[0].messages[0]).not.toBe(state.panels[1].messages[0])
    } finally {
      vi.useRealTimers()
    }
  })

  it('builds message actions that create and append assistant chunks', () => {
    vi.useFakeTimers()
    vi.setSystemTime(2_000)

    try {
      const { state, actions } = createMessageActionHarness([
        { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] },
        { id: 'panel-2', modelConfig: defaultModelConfig('panel-2'), messages: [] },
      ])

      actions.appendChunk(
        'panel-1',
        'assistant-1',
        'hello',
        { modelId: 'qwen', answerGroupId: 'answer-1' },
      )
      actions.appendChunk('panel-1', 'assistant-1', ' world')

      expect(state.panels[0].messages).toEqual([
        expect.objectContaining({
          id: 'assistant-1',
          role: 'assistant',
          content: 'hello world',
          streaming: true,
          modelId: 'qwen',
          panelId: 'panel-1',
          answerGroupId: 'answer-1',
          timestamp: 2,
          feedbackValue: 0,
        }),
      ])
      expect(state.panels[1].messages).toEqual([])
    } finally {
      vi.useRealTimers()
    }
  })

  it('builds message actions that set sources and task metadata', () => {
    const sources: SourceItem[] = [{ type: 'web', title: 'Doc', snippet: 'Snippet' }]
    const { state, actions } = createMessageActionHarness([
      {
        id: 'panel-1',
        modelConfig: defaultModelConfig('panel-1'),
        messages: [{ id: 'assistant-1', role: 'assistant', content: 'answer' }],
      },
    ])

    actions.setSources(
      'panel-1',
      'assistant-1',
      sources,
      { modelId: 'qwen', answerGroupId: 'answer-1' },
    )
    actions.setTaskId('panel-1', 'assistant-1', 'task-1', 'chat')

    expect(state.panels[0].messages[0]).toMatchObject({
      id: 'assistant-1',
      sources,
      taskId: 'task-1',
      taskType: 'chat',
    })
  })

  it('builds message actions that remove one message or clear every panel', () => {
    const { state, actions } = createMessageActionHarness([
      {
        id: 'panel-1',
        modelConfig: defaultModelConfig('panel-1'),
        messages: [
          { id: 'remove-me', role: 'assistant', content: 'old' },
          { id: 'keep-me', role: 'assistant', content: 'keep' },
        ],
      },
      {
        id: 'panel-2',
        modelConfig: defaultModelConfig('panel-2'),
        messages: [{ id: 'other', role: 'user', content: 'other' }],
      },
    ])

    actions.removeMessage('panel-1', 'remove-me')
    expect(state.panels[0].messages.map((message) => message.id)).toEqual(['keep-me'])
    expect(state.panels[1].messages.map((message) => message.id)).toEqual(['other'])

    actions.clearMessages()
    expect(state.panels.every((panel) => panel.messages.length === 0)).toBe(true)
  })

  it('clears API keys before model configs are persisted', () => {
    const modelConfig: ModelConfig = {
      ...defaultModelConfig('panel-1'),
      api_key: 'secret-key',
      api_key_ref: 'server-ref',
      model: 'custom-model',
    }

    expect(sanitizePersistedModelConfig(modelConfig)).toEqual({
      ...modelConfig,
      api_key: '',
    })
  })

  it('normalizes bookmarks and keeps timestamp units in seconds', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-07T00:00:00Z'))

    expect(
      normalizeBookmarkMessage({
        ...makeBookmark({
          id: 'bookmark-1',
          createdAt: Number.NaN,
          updatedAt: 1_715_000_000_000,
          source: undefined,
        }),
        sessionId: undefined as unknown as string,
        panelId: undefined as unknown as string,
      }),
    ).toMatchObject({
      sessionId: '',
      panelId: '',
      createdAt: 1_778_112_000,
      updatedAt: 1_715_000_000,
      source: 'remote',
    })

    vi.useRealTimers()
  })

  it('matches bookmark targets by message id, answer group, or local legacy id', () => {
    expect(
      sameBookmarkTarget(
        makeBookmark({ id: 'a', messageId: 7 }),
        makeBookmark({ id: 'b', messageId: 7, answerGroupId: 'other' }),
      ),
    ).toBe(true)

    expect(
      sameBookmarkTarget(
        makeBookmark({ id: 'a', role: 'user', answerGroupId: 'answer-1', panelId: 'p1' }),
        makeBookmark({ id: 'b', role: 'user', answerGroupId: 'answer-1', panelId: 'p2' }),
      ),
    ).toBe(true)

    expect(
      sameBookmarkTarget(
        makeBookmark({ id: 'a', role: 'assistant', answerGroupId: 'answer-1', panelId: 'p1' }),
        makeBookmark({ id: 'b', role: 'assistant', answerGroupId: 'answer-1', panelId: 'p2' }),
      ),
    ).toBe(false)

    expect(
      sameBookmarkTarget(
        makeBookmark({ id: 'legacy', source: 'local', answerGroupId: '' }),
        makeBookmark({ id: 'legacy', source: 'local', answerGroupId: '' }),
      ),
    ).toBe(true)
  })

  it('sorts, merges, and replaces bookmarks without creating duplicate targets', () => {
    const localDuplicate = makeBookmark({
      id: 'local-duplicate',
      messageId: 10,
      source: 'local',
      updatedAt: 300,
    })
    const localOnly = makeBookmark({
      id: 'local-only',
      messageId: 11,
      source: 'local',
      updatedAt: 200,
    })
    const remote = makeBookmark({
      id: 'remote',
      messageId: 10,
      source: 'remote',
      updatedAt: 100,
    })

    expect(sortBookmarks([localOnly, remote]).map((bookmark) => bookmark.id)).toEqual([
      'local-only',
      'remote',
    ])
    expect(
      mergeRemoteBookmarksWithLocalLegacy([remote], [localDuplicate, localOnly]).map(
        (bookmark) => bookmark.id,
      ),
    ).toEqual(['local-only', 'remote'])
    expect(
      addOrReplaceBookmark([localDuplicate, localOnly], {
        ...remote,
        updatedAt: 400,
      }).map((bookmark) => bookmark.id),
    ).toEqual(['remote', 'local-only'])
    expect(hasBookmark([remote, localOnly], 'remote')).toBe(true)
    expect(hasBookmark([remote, localOnly], 'missing')).toBe(false)
    expect(removeBookmarkById([remote, localOnly], 'remote').map((bookmark) => bookmark.id))
      .toEqual(['local-only'])
  })

  it('builds bookmark actions that preserve merge and replace behavior', () => {
    const initial = {
      bookmarks: [
        makeBookmark({
          id: 'local-only',
          messageId: 11,
          source: 'local',
          updatedAt: 200,
        }),
      ],
    }
    const state = { ...initial }
    const set = (updater: (value: typeof state) => Pick<typeof state, 'bookmarks'>) => {
      Object.assign(state, updater(state))
    }
    const actions = createBookmarkActions(set, () => state)

    actions.setBookmarks([
      makeBookmark({
        id: 'remote',
        messageId: 10,
        source: 'remote',
        updatedAt: 100,
      }),
      makeBookmark({
        id: 'remote-newer',
        messageId: 11,
        source: 'remote',
        updatedAt: 300,
      }),
    ])
    expect(state.bookmarks.map((bookmark) => bookmark.id)).toEqual(['remote-newer', 'remote'])

    actions.addBookmark({
      ...makeBookmark({
        id: 'remote-newer',
        messageId: 11,
        source: 'remote',
        updatedAt: 400,
      }),
    })
    expect(state.bookmarks.map((bookmark) => bookmark.id)).toEqual(['remote-newer', 'remote'])

    expect(actions.isBookmarked('remote-newer')).toBe(true)
    actions.removeBookmark('remote-newer')
    expect(state.bookmarks.map((bookmark) => bookmark.id)).toEqual(['remote'])
    expect(actions.isBookmarked('remote-newer')).toBe(false)
  })

  it('normalizes small UI model rules used by the store', () => {
    expect(normalizeEnabledMcpServers([' web-search ', '', 'knowledge-base', 'web-search']))
      .toEqual(['web-search', 'knowledge-base'])
    expect(defaultEnabledMcpServers()).toEqual([])
    expect(defaultEnabledMcpServers()).not.toBe(defaultEnabledMcpServers())
    expect(defaultComposerSeed()).toEqual({
      token: 0,
      text: '',
      images: [],
      files: [],
      editAnswerGroupId: null,
    })
    expect(defaultComposerSeed()).not.toBe(defaultComposerSeed())
    expect(getNextTheme('dark')).toBe('light')
    expect(getNextTheme('light')).toBe('system')
    expect(getNextTheme('system')).toBe('dark')
    expect(getNextLanguage('zh-CN')).toBe('en-US')
    expect(getNextLanguage('en-US')).toBe('zh-CN')
  })

  it('keeps attachment and memory workspace states mutually exclusive', () => {
    expect(
      toggleAttachmentWorkspaceState({
        attachmentWorkspaceOpen: false,
        memoryWorkspaceOpen: true,
      }),
    ).toEqual({
      attachmentWorkspaceOpen: true,
      memoryWorkspaceOpen: false,
    })
    expect(
      toggleAttachmentWorkspaceState({
        attachmentWorkspaceOpen: true,
        memoryWorkspaceOpen: true,
      }),
    ).toEqual({
      attachmentWorkspaceOpen: false,
      memoryWorkspaceOpen: true,
    })
    expect(setAttachmentWorkspaceState({ memoryWorkspaceOpen: true }, true)).toEqual({
      attachmentWorkspaceOpen: true,
      memoryWorkspaceOpen: false,
    })

    expect(
      toggleMemoryWorkspaceState({
        attachmentWorkspaceOpen: true,
        memoryWorkspaceOpen: false,
      }),
    ).toEqual({
      attachmentWorkspaceOpen: false,
      memoryWorkspaceOpen: true,
    })
    expect(
      toggleMemoryWorkspaceState({
        attachmentWorkspaceOpen: true,
        memoryWorkspaceOpen: true,
      }),
    ).toEqual({
      attachmentWorkspaceOpen: true,
      memoryWorkspaceOpen: false,
    })
    expect(setMemoryWorkspaceState({ attachmentWorkspaceOpen: true }, true)).toEqual({
      attachmentWorkspaceOpen: false,
      memoryWorkspaceOpen: true,
    })
  })

  it('builds composer seed payloads and increments the token', () => {
    const current = {
      token: 4,
      text: 'old',
      images: [{ name: 'old.png', media_type: 'image/png', data_url: 'data:old' }],
      files: [{ name: 'old.txt', media_type: 'text/plain', size_bytes: 1 }],
      editAnswerGroupId: 'old-answer',
    }

    expect(
      buildComposerSeed(current, {
        text: 'new',
        images: [{ name: 'new.png', media_type: 'image/png', data_url: 'data:new' }],
        files: [{ name: 'new.txt', media_type: 'text/plain', size_bytes: 2 }],
        editAnswerGroupId: 'answer-2',
      }),
    ).toEqual({
      token: 5,
      text: 'new',
      images: [{ name: 'new.png', media_type: 'image/png', data_url: 'data:new' }],
      files: [{ name: 'new.txt', media_type: 'text/plain', size_bytes: 2 }],
      editAnswerGroupId: 'answer-2',
    })

    expect(buildComposerSeed(current, {})).toEqual({
      token: 5,
      text: '',
      images: [],
      files: [],
      editAnswerGroupId: null,
    })
  })

  it('saves model presets by trimmed unique name and updates existing names case-insensitively', () => {
    const baseConfig = defaultModelConfig('panel-1')
    const saved = saveModelPreset([], '  Local fast  ', baseConfig, {
      now: () => 1_000,
      randomSuffix: () => 'abc12',
    })

    expect(saved).toEqual([
      {
        id: 'preset-1000-abc12',
        name: 'Local fast',
        modelConfig: {
          ...baseConfig,
          panel_id: 'panel-1',
        },
        createdAt: 1_000,
        updatedAt: 1_000,
      },
    ])
    expect(saveModelPreset(saved, '   ', baseConfig)).toBe(saved)

    const updated = saveModelPreset(
      saved,
      'local FAST',
      { ...baseConfig, model: 'qwen-updated', panel_id: '' },
      { now: () => 2_000, randomSuffix: () => 'unused' },
    )

    expect(updated).toHaveLength(1)
    expect(updated[0]).toMatchObject({
      id: 'preset-1000-abc12',
      name: 'local FAST',
      createdAt: 1_000,
      updatedAt: 2_000,
    })
    expect(updated[0].modelConfig).toMatchObject({
      model: 'qwen-updated',
      panel_id: 'preset-2000',
    })
  })

  it('applies model presets to a target panel without mutating other panels', () => {
    const panels = [
      { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] },
      { id: 'panel-2', modelConfig: defaultModelConfig('panel-2'), messages: [] },
    ]
    const presets = saveModelPreset(
      [],
      'Preset',
      { ...defaultModelConfig('source-panel'), model: 'preset-model' },
      { now: () => 1_000, randomSuffix: () => 'abc12' },
    )

    const applied = applyModelPresetToPanels(panels, presets, 'panel-2', 'preset-1000-abc12')

    expect(applied[0]).toBe(panels[0])
    expect(applied[1].modelConfig).toMatchObject({
      model: 'preset-model',
      panel_id: 'panel-2',
    })
    expect(applyModelPresetToPanels(panels, presets, 'panel-2', 'missing')).toBe(panels)
  })

  it('saves cloud model profiles with OpenAI-compatible defaults and updates by id or name', () => {
    const baseConfig: ModelConfig = {
      ...defaultModelConfig('panel-1'),
      connection_type: 'ollama',
      provider: 'ollama',
      model: 'cloud-model',
      panel_id: '',
    }
    const saved = saveCloudModelProfile(
      [],
      { name: '  Cloud profile  ', modelConfig: baseConfig },
      { now: () => 1_000, randomSuffix: () => 'abc12' },
    )

    expect(saved[0]).toMatchObject({
      id: 'cloud-profile-1000-abc12',
      name: 'Cloud profile',
      createdAt: 1_000,
      updatedAt: 1_000,
    })
    expect(saved[0].modelConfig).toMatchObject({
      panel_id: 'cloud-profile-1000',
      connection_type: 'openai_compatible',
      provider: 'openai_compatible',
    })
    expect(saveCloudModelProfile(saved, { name: '', modelConfig: baseConfig })).toBe(saved)

    const updatedByName = saveCloudModelProfile(
      saved,
      { name: 'cloud PROFILE', modelConfig: { ...baseConfig, model: 'updated-by-name' } },
      { now: () => 2_000, randomSuffix: () => 'unused' },
    )
    expect(updatedByName[0]).toMatchObject({
      id: 'cloud-profile-1000-abc12',
      name: 'cloud PROFILE',
      updatedAt: 2_000,
    })
    expect(updatedByName[0].modelConfig.model).toBe('updated-by-name')

    const updatedById = saveCloudModelProfile(
      updatedByName,
      {
        id: 'cloud-profile-1000-abc12',
        name: 'Explicit id',
        modelConfig: { ...baseConfig, model: 'updated-by-id' },
      },
      { now: () => 3_000 },
    )
    expect(updatedById[0]).toMatchObject({
      id: 'cloud-profile-1000-abc12',
      name: 'Explicit id',
      updatedAt: 3_000,
    })
    expect(updatedById[0].modelConfig.model).toBe('updated-by-id')
  })

  it('applies cloud model profiles to a target panel with provider defaults', () => {
    const panels = [
      { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages: [] },
      { id: 'panel-2', modelConfig: defaultModelConfig('panel-2'), messages: [] },
    ]
    const profiles = saveCloudModelProfile(
      [],
      {
        name: 'Cloud',
        modelConfig: {
          ...defaultModelConfig('source-panel'),
          model: 'cloud-model',
          provider: 'ollama',
          connection_type: 'ollama',
        },
      },
      { now: () => 1_000, randomSuffix: () => 'abc12' },
    )

    const applied = applyCloudModelProfileToPanels(
      panels,
      profiles,
      'panel-2',
      'cloud-profile-1000-abc12',
    )

    expect(applied[0]).toBe(panels[0])
    expect(applied[1].modelConfig).toMatchObject({
      model: 'cloud-model',
      panel_id: 'panel-2',
      connection_type: 'openai_compatible',
      provider: 'openai_compatible',
    })
    expect(applyCloudModelProfileToPanels(panels, profiles, 'panel-2', 'missing')).toBe(panels)
  })

  it('removes model presets and cloud profiles by id without touching other entries', () => {
    const baseConfig = defaultModelConfig('panel-1')
    const modelPresets = [
      {
        id: 'preset-1',
        name: 'One',
        modelConfig: baseConfig,
        createdAt: 1,
        updatedAt: 1,
      },
      {
        id: 'preset-2',
        name: 'Two',
        modelConfig: baseConfig,
        createdAt: 2,
        updatedAt: 2,
      },
    ]
    const cloudProfiles = [
      {
        id: 'profile-1',
        name: 'One',
        modelConfig: baseConfig,
        createdAt: 1,
        updatedAt: 1,
      },
      {
        id: 'profile-2',
        name: 'Two',
        modelConfig: baseConfig,
        createdAt: 2,
        updatedAt: 2,
      },
    ]

    expect(removeModelPresetById(modelPresets, 'preset-1').map((preset) => preset.id))
      .toEqual(['preset-2'])
    expect(removeCloudModelProfileById(cloudProfiles, 'profile-2').map((profile) => profile.id))
      .toEqual(['profile-1'])
  })

  it('truncates messages from an answer group and replaces assistant messages by group', () => {
    const messages: PanelMessage[] = [
      { id: 'u1', role: 'user', content: 'first', answerGroupId: 'a1' },
      { id: 'a1', role: 'assistant', content: 'old', answerGroupId: 'a1' },
      { id: 'u2', role: 'user', content: 'second', answerGroupId: 'a2' },
      { id: 'a2', role: 'assistant', content: 'second answer', answerGroupId: 'a2' },
    ]

    const truncated = truncatePanelMessagesFromAnswerGroup(messages, 'a2', {
      content: 'edited second',
      timestamp: 999,
    })
    expect(truncated).toEqual([
      messages[0],
      messages[1],
      { ...messages[2], content: 'edited second', timestamp: 999 },
    ])
    expect(truncatePanelMessagesFromAnswerGroup(messages, 'missing')).toBe(messages)

    expect(
      replaceAssistantMessageByAnswerGroup(messages, 'a1', {
        content: 'new answer',
        streaming: false,
      }),
    ).toEqual([
      messages[0],
      { ...messages[1], content: 'new answer', streaming: false },
      messages[2],
      messages[3],
    ])

    const panels: Panel[] = [
      { id: 'panel-1', modelConfig: defaultModelConfig('panel-1'), messages },
      {
        id: 'panel-2',
        modelConfig: defaultModelConfig('panel-2'),
        messages: [{ id: 'other', role: 'assistant', content: 'other' }],
      },
    ]
    const truncatedPanels = truncateAnswerGroupFromPanels(panels, 'a2', {
      content: 'edited via panel helper',
    })
    expect(truncatedPanels[0].messages).toEqual([
      messages[0],
      messages[1],
      { ...messages[2], content: 'edited via panel helper' },
    ])
    expect(truncatedPanels[1]).toBe(panels[1])

    const replacedPanels = replaceAssistantMessageByAnswerGroupInPanel(
      panels,
      'panel-1',
      'a1',
      { content: 'panel helper answer', streaming: false },
    )
    expect(replacedPanels[0].messages[1]).toMatchObject({
      content: 'panel helper answer',
      streaming: false,
    })
    expect(replacedPanels[1]).toBe(panels[1])
  })

  it('migrates persisted store state while clearing messages and provider API keys', () => {
    const migrated = migrateChatStoreState(
      {
        sidebarOpen: false,
        webSearchEnabled: true,
        knowledgeBaseEnabled: false,
        researchMode: 'quick',
        researchSourceStrategy: 'community_first',
        enabledMcpServers: [' web-search ', '', 'web-search', 'knowledge-base'],
        theme: 'unsupported',
        language: 'en-US',
        bookmarks: [
          {
            id: '',
            role: 'assistant',
            createdAt: 100,
            updatedAt: 200,
            source: 'remote',
          },
        ],
        memoryWorkspaceOpen: true,
        modelPresets: [
          {
            modelConfig: {
              ...defaultModelConfig('preset-panel'),
              api_key: 'preset-secret',
            },
          },
        ],
        cloudModelProfiles: [
          {
            name: '',
            modelConfig: {
              ...defaultModelConfig('cloud-panel'),
              api_key: 'cloud-secret',
            },
          },
        ],
        panels: [
          {
            id: 'panel-1',
            modelConfig: {
              ...defaultModelConfig('panel-1'),
              model: 'qwen3.5:4b',
              api_key: 'panel-secret',
            },
            messages: [{ id: 'msg-1', role: 'user', content: 'persisted' }],
          },
        ],
      },
      {
        now: () => 1_000,
        createPanel: () => ({
          id: 'fallback-panel',
          modelConfig: defaultModelConfig('fallback-panel'),
          messages: [],
        }),
      },
    )

    expect(migrated).toMatchObject({
      sidebarOpen: false,
      webSearchEnabled: true,
      knowledgeBaseEnabled: false,
      researchMode: 'quick',
      researchSourceStrategy: 'community_first',
      enabledMcpServers: ['web-search', 'knowledge-base'],
      theme: 'system',
      language: 'en-US',
      memoryWorkspaceOpen: false,
    })
    expect(migrated.bookmarks[0]).toMatchObject({
      id: 'legacy-bookmark-0',
      source: 'remote',
    })
    expect(migrated.modelPresets[0]).toMatchObject({
      id: 'preset-migrated-0',
      name: 'Preset 1',
      createdAt: 1_000,
      updatedAt: 1_000,
    })
    expect(migrated.modelPresets[0].modelConfig.api_key).toBe('')
    expect(migrated.cloudModelProfiles[0].modelConfig).toMatchObject({
      connection_type: 'openai_compatible',
      provider: 'openai_compatible',
      api_key: '',
    })
    expect(migrated.panels[0].messages).toEqual([])
    expect(migrated.panels[0].modelConfig).toMatchObject({
      model: 'qwen3.5-2B:latest',
      api_key: '',
    })

    const fallback = migrateChatStoreState({
      enabledMcpServers: ['  ', ''],
      panels: [],
    })
    expect(fallback.enabledMcpServers).toEqual([])
    expect(fallback.enabledMcpServers).not.toBe(defaultEnabledMcpServers())
  })

  it('partializes store state without persisting transient messages or API keys', () => {
    const partialized = partializeChatStoreState({
      currentWorkspaceId: 'workspace-1',
      sidebarOpen: true,
      webSearchEnabled: true,
      knowledgeBaseEnabled: true,
      researchMode: 'deep',
      researchSourceStrategy: 'evidence_strict',
      enabledMcpServers: ['knowledge-base'],
      welcomeGuideDismissed: true,
      activePromptId: 'prompt-1',
      theme: 'dark',
      language: 'zh-CN',
      bookmarks: [makeBookmark({ id: 'bookmark-1' })],
      memoryWorkspaceOpen: false,
      modelPresets: [
        {
          id: 'preset-1',
          name: 'Preset',
          modelConfig: {
            ...defaultModelConfig('preset-1'),
            api_key: 'preset-secret',
          },
          createdAt: 1,
          updatedAt: 2,
        },
      ],
      cloudModelProfiles: [
        {
          id: 'cloud-1',
          name: 'Cloud',
          modelConfig: {
            ...defaultModelConfig('cloud-1'),
            api_key: 'cloud-secret',
          },
          createdAt: 1,
          updatedAt: 2,
        },
      ],
      panels: [
        {
          id: 'panel-1',
          modelConfig: {
            ...defaultModelConfig('panel-1'),
            api_key: 'panel-secret',
          },
          messages: [{ id: 'msg-1', role: 'assistant', content: 'transient' }],
        },
      ],
    })

    expect(partialized.memoryWorkspaceOpen).toBe(false)
    expect(partialized.researchSourceStrategy).toBe('evidence_strict')
    expect(partialized.modelPresets[0].modelConfig.api_key).toBe('')
    expect(partialized.cloudModelProfiles[0].modelConfig.api_key).toBe('')
    expect(partialized.panels[0].modelConfig.api_key).toBe('')
    expect(partialized.panels[0].messages).toEqual([])
  })
})
