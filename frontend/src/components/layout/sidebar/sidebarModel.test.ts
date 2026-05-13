import { describe, expect, it } from 'vitest'

import type { Bookmark, Message, Session } from '../../../api/client'
import {
  applyOptimisticSessionOrder,
  buildBookmarkGroups,
  buildReorderedSessionIds,
  canDragSortSessions,
  collectSessionTags,
  countSessionsByView,
  filterBookmarksByKeyword,
  filterSessionsByView,
  findLatestWorkflowNodes,
  formatSessionTimestamp,
  getSessionEmptyStateMessage,
  mapMessages,
  parseSessionTagDraft,
} from './sidebarModel'

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
    workspace_id: patch.workspace_id ?? 'default',
    search_preview: patch.search_preview,
    search_source: patch.search_source,
  }
}

function makeBookmark(patch: Partial<Bookmark> & Pick<Bookmark, 'id'>): Bookmark {
  return {
    id: patch.id,
    sessionId: patch.sessionId ?? 'session-a',
    sessionTitle: patch.sessionTitle ?? 'Session A',
    messageId: patch.messageId,
    panelId: patch.panelId ?? 'panel-a',
    answerGroupId: patch.answerGroupId ?? 'answer-a',
    role: patch.role ?? 'assistant',
    content: patch.content ?? '',
    modelId: patch.modelId,
    createdAt: patch.createdAt ?? 1,
    updatedAt: patch.updatedAt ?? patch.createdAt ?? 1,
    source: patch.source,
  }
}

describe('sidebarModel', () => {
  it('maps stored API messages into panel messages', () => {
    const messages: Message[] = [
      {
        role: 'assistant',
        content: 'answer',
        model_id: 'qwen-live',
        answer_group_id: 'answer-1',
        task_id: 'task-1',
        task_type: 'research',
        token_usage: {
          prompt_tokens: 12,
          completion_tokens: 30,
          total_tokens: 42,
          estimated: false,
        },
      },
    ]

    expect(mapMessages(messages)).toEqual([
      expect.objectContaining({
        id: 'loaded-0',
        role: 'assistant',
        content: 'answer',
        modelId: 'qwen-live',
        answerGroupId: 'answer-1',
        taskId: 'task-1',
        taskType: 'research',
        tokenUsage: expect.objectContaining({
          total_tokens: 42,
        }),
      }),
    ])
  })

  it('finds the latest assistant workflow nodes', () => {
    const messages: Message[] = [
      {
        role: 'assistant',
        content: 'old',
        workflow_nodes: [
          {
            id: 'old-node',
            name: 'old-node',
            displayName: 'Old',
            status: 'completed',
          },
        ],
      },
      {
        role: 'user',
        content: 'ignore user nodes',
        workflow_nodes: [
          {
            id: 'user-node',
            name: 'user-node',
            displayName: 'User',
            status: 'completed',
          },
        ],
      },
      {
        role: 'assistant',
        content: 'new',
        workflow_nodes: [
          {
            id: 'new-node',
            name: 'new-node',
            displayName: 'New',
            status: 'running',
          },
        ],
      },
    ]

    expect(findLatestWorkflowNodes(messages)).toEqual([
      {
        id: 'new-node',
        name: 'new-node',
        displayName: 'New',
        status: 'running',
      },
    ])
    expect(findLatestWorkflowNodes([{ role: 'assistant', content: 'no nodes' }])).toEqual([])
  })

  it('counts sessions by visible view buckets', () => {
    const sessions = [
      makeSession({ session_id: 'normal' }),
      makeSession({ session_id: 'favorite', is_favorite: true }),
      makeSession({ session_id: 'archived-favorite', is_archived: true, is_favorite: true }),
    ]

    expect(countSessionsByView(sessions)).toEqual({
      all: 2,
      favorite: 1,
      archived: 1,
    })
  })

  it('collects stable session tags with a configurable limit', () => {
    const sessions = [
      makeSession({ session_id: 'a', tags: ['research', 'urgent'] }),
      makeSession({ session_id: 'b', tags: ['urgent', 'draft'] }),
    ]

    expect(collectSessionTags(sessions, 2)).toEqual(['research', 'urgent'])
  })

  it('filters sessions by mode and tag without showing archived items in normal views', () => {
    const sessions = [
      makeSession({ session_id: 'normal', tags: ['research'] }),
      makeSession({ session_id: 'favorite', is_favorite: true, tags: ['research'] }),
      makeSession({ session_id: 'archived', is_archived: true, tags: ['research'] }),
      makeSession({ session_id: 'other-tag', tags: ['draft'] }),
    ]

    expect(filterSessionsByView(sessions, 'all', 'research').map((item) => item.session_id))
      .toEqual(['normal', 'favorite'])
    expect(filterSessionsByView(sessions, 'favorite', null).map((item) => item.session_id))
      .toEqual(['favorite'])
    expect(filterSessionsByView(sessions, 'archived', null).map((item) => item.session_id))
      .toEqual(['archived'])
  })

  it('parses session tag drafts from comma and newline separated text', () => {
    expect(parseSessionTagDraft(' research, urgent，draft\n\n qa ')).toEqual([
      'research',
      'urgent',
      'draft',
      'qa',
    ])
  })

  it('formats session timestamps as time for today and date for older sessions', () => {
    const now = new Date('2026-05-11T12:00:00+08:00')

    expect(formatSessionTimestamp(new Date('2026-05-11T10:30:00+08:00').getTime() / 1000, now))
      .toMatch(/10:30/)
    expect(formatSessionTimestamp(new Date('2026-05-09T10:30:00+08:00').getTime() / 1000, now))
      .toContain('5月9日')
  })

  it('builds empty state copy from search and view mode', () => {
    expect(getSessionEmptyStateMessage('query', 'all')).toBe('No matching cross-session results.')
    expect(getSessionEmptyStateMessage('', 'favorite')).toBe('No favorite sessions yet.')
    expect(getSessionEmptyStateMessage('', 'archived')).toBe('No archived sessions.')
    expect(getSessionEmptyStateMessage('', 'all')).toBe('暂无对话记录')
  })

  it('guards drag sorting while filtered, bookmarked, or already reordering', () => {
    expect(canDragSortSessions({
      search: '',
      showBookmarks: false,
      viewMode: 'all',
      reorderingSessions: false,
    })).toBe(true)
    expect(canDragSortSessions({
      search: 'needle',
      showBookmarks: false,
      viewMode: 'all',
      reorderingSessions: false,
    })).toBe(false)
    expect(canDragSortSessions({
      search: '',
      showBookmarks: true,
      viewMode: 'all',
      reorderingSessions: false,
    })).toBe(false)
  })

  it('builds reordered ids and optimistic session order', () => {
    const sessions = [
      makeSession({ session_id: 'a', session_order: 3 }),
      makeSession({ session_id: 'b', session_order: 2 }),
      makeSession({ session_id: 'c', session_order: 1 }),
      makeSession({ session_id: 'hidden', session_order: 99 }),
    ]
    const visibleSessions = sessions.slice(0, 3)

    const nextOrder = buildReorderedSessionIds(visibleSessions, 'c', 'a')

    expect(nextOrder).toEqual(['c', 'a', 'b'])
    expect(buildReorderedSessionIds(visibleSessions, 'missing', 'a')).toBeNull()
    expect(applyOptimisticSessionOrder(sessions, nextOrder ?? []).map((session) => [
      session.session_id,
      session.session_order,
    ])).toEqual([
      ['a', 2],
      ['b', 1],
      ['c', 3],
      ['hidden', 99],
    ])
  })

  it('filters bookmarks across session title, content, and model id', () => {
    const bookmarks = [
      makeBookmark({ id: 'title', sessionTitle: 'Research notes' }),
      makeBookmark({ id: 'content', content: 'Contains Jira ticket' }),
      makeBookmark({ id: 'model', modelId: 'deepseek-chat' }),
      makeBookmark({ id: 'other', content: 'unrelated' }),
    ]

    expect(filterBookmarksByKeyword(bookmarks, 'jira').map((item) => item.id))
      .toEqual(['content'])
    expect(filterBookmarksByKeyword(bookmarks, 'DEEPSEEK').map((item) => item.id))
      .toEqual(['model'])
    expect(filterBookmarksByKeyword(bookmarks, '   ')).toBe(bookmarks)
  })

  it('groups bookmarks by session and sorts groups and items by recency', () => {
    const bookmarks = [
      makeBookmark({ id: 'old-a', sessionId: 'a', sessionTitle: 'Alpha', createdAt: 10, updatedAt: 20 }),
      makeBookmark({ id: 'new-a', sessionId: 'a', sessionTitle: 'Alpha', createdAt: 10, updatedAt: 50 }),
      makeBookmark({ id: 'b', sessionId: 'b', sessionTitle: 'Beta', createdAt: 30, updatedAt: 30 }),
      makeBookmark({ id: 'untitled', sessionId: '', sessionTitle: '  ', createdAt: 60, updatedAt: 0 }),
    ]

    const groups = buildBookmarkGroups(bookmarks)

    expect(groups.map((group) => group.key)).toEqual(['session-title:Untitled session', 'a', 'b'])
    expect(groups[1].items.map((item) => item.id)).toEqual(['new-a', 'old-a'])
  })
})
