import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createSession, getSessionMessages } from '../../../api/client';
import type { Message, MessagesResponse, Session } from '../../../api/client';
import { useChatStore } from '../../../stores/chatStore';
import { useSidebarSessionNavigation } from './useSidebarSessionNavigation';

vi.mock('../../../api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../../api/client')>();
  return {
    ...original,
    createSession: vi.fn(),
    getSessionMessages: vi.fn(),
  };
});

function session(sessionId: string): Session {
  return {
    session_id: sessionId,
    title: sessionId,
    created_at: 1,
    updated_at: 1,
    message_count: 1,
    is_archived: false,
    is_favorite: false,
    is_pinned: false,
    session_order: 0,
    tags: [],
    workspace_id: 'workspace-1',
  };
}

function messagesResponse(content: string): MessagesResponse {
  return {
    messages: [{ role: 'user', content }] as Message[],
    context_limit: 16,
    total_messages: 1,
    panels: [],
    panel_messages: {},
  };
}

describe('useSidebarSessionNavigation', () => {
  const loadMessagesToAllPanels = vi.fn();
  const setCurrentSession = vi.fn();

  beforeEach(() => {
    vi.mocked(createSession).mockReset();
    vi.mocked(getSessionMessages).mockReset();
    loadMessagesToAllPanels.mockReset();
    setCurrentSession.mockReset();
    useChatStore.setState({
      loadMessagesToAllPanels,
      setCurrentSession,
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('ignores a stale response when the user switches sessions quickly', async () => {
    let resolveFirst: (value: MessagesResponse) => void = () => undefined;
    let resolveSecond: (value: MessagesResponse) => void = () => undefined;
    vi.mocked(getSessionMessages).mockImplementation(
      (sessionId) =>
        new Promise<MessagesResponse>((resolve) => {
          if (sessionId === 'session-1') {
            resolveFirst = resolve;
          } else {
            resolveSecond = resolve;
          }
        })
    );

    const { result } = renderHook(() =>
      useSidebarSessionNavigation({
        currentWorkspaceId: 'workspace-1',
        currentSessionId: null,
        storePanels: useChatStore.getState().panels,
        search: '',
        isMobile: false,
        syncWorkspaceForSession: vi.fn().mockResolvedValue(undefined),
        setSearch: vi.fn(),
        setViewMode: vi.fn(),
        setTagFilter: vi.fn(),
        setMovingSessionId: vi.fn(),
      })
    );

    let firstOpen = Promise.resolve();
    let secondOpen = Promise.resolve();
    act(() => {
      firstOpen = result.current.openSession(session('session-1'));
      secondOpen = result.current.openSession(session('session-2'));
    });

    await act(async () => {
      resolveSecond(messagesResponse('newest'));
      await secondOpen;
    });
    await act(async () => {
      resolveFirst(messagesResponse('stale'));
      await firstOpen;
    });

    expect(setCurrentSession).toHaveBeenLastCalledWith('session-2');
    expect(loadMessagesToAllPanels).toHaveBeenCalledTimes(1);
    expect(loadMessagesToAllPanels).toHaveBeenCalledWith(
      expect.arrayContaining([expect.objectContaining({ content: 'newest' })])
    );
  });
});
