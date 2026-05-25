import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createSession,
  createSessionShareLink,
  resetSession,
} from '../../../api/client'
import type { Session } from '../../../api/client'
import { useHeaderSessionActions } from './useHeaderSessionActions'

vi.mock('../../../api/client', () => ({
  createSession: vi.fn(),
  createSessionShareLink: vi.fn(),
  resetSession: vi.fn(),
}))

function renderSessionActions(overrides: Partial<Parameters<typeof useHeaderSessionActions>[0]> = {}) {
  return renderHook(() =>
    useHeaderSessionActions({
      currentSessionId: 'session-1',
      currentWorkspaceId: 'workspace-1',
      addSession: vi.fn(),
      adjustWorkspaceSessionCount: vi.fn(),
      setCurrentSession: vi.fn(),
      clearMessages: vi.fn(),
      updateSession: vi.fn(),
      setActionFeedback: vi.fn(),
      ...overrides,
    }),
  )
}

describe('useHeaderSessionActions', () => {
  beforeEach(() => {
    vi.mocked(createSession).mockReset()
    vi.mocked(createSessionShareLink).mockReset()
    vi.mocked(resetSession).mockReset()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('creates a session and selects it as the current chat', async () => {
    const addSession = vi.fn()
    const adjustWorkspaceSessionCount = vi.fn()
    const setCurrentSession = vi.fn()
    const clearMessages = vi.fn()
    vi.mocked(createSession).mockResolvedValue({
      session_id: 'session-new',
      title: 'New chat',
      workspace_id: 'workspace-created',
    } as Session)

    const { result } = renderSessionActions({
      addSession,
      adjustWorkspaceSessionCount,
      setCurrentSession,
      clearMessages,
    })

    await act(async () => {
      await result.current.handleNewChat()
    })

    expect(createSession).toHaveBeenCalledWith(expect.any(String), {
      workspace_id: 'workspace-1',
    })
    expect(addSession).toHaveBeenCalledWith(
      expect.objectContaining({
        session_id: 'session-new',
        title: 'New chat',
        workspace_id: 'workspace-created',
        message_count: 0,
      }),
    )
    expect(adjustWorkspaceSessionCount).toHaveBeenCalledWith('workspace-created', 1)
    expect(setCurrentSession).toHaveBeenCalledWith('session-new')
    expect(clearMessages).toHaveBeenCalledTimes(1)
  })

  it('requires confirmation before resetting the active session', async () => {
    vi.useFakeTimers()
    const clearMessages = vi.fn()
    const updateSession = vi.fn()
    const setActionFeedback = vi.fn()
    vi.mocked(resetSession).mockResolvedValue(undefined)

    const { result } = renderSessionActions({
      clearMessages,
      updateSession,
      setActionFeedback,
    })

    await act(async () => {
      await result.current.handleResetSession()
    })

    expect(result.current.resetConfirm).toBe(true)
    expect(resetSession).not.toHaveBeenCalled()

    await act(async () => {
      await result.current.handleResetSession()
    })

    expect(resetSession).toHaveBeenCalledWith('session-1')
    expect(updateSession).toHaveBeenCalledWith(
      'session-1',
      expect.objectContaining({ message_count: 0 }),
    )
    expect(clearMessages).toHaveBeenCalledTimes(1)
    expect(setActionFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ tone: 'success' }),
    )
    expect(result.current.resetConfirm).toBe(false)
  })

  it('copies a generated share link to the clipboard', async () => {
    vi.useFakeTimers()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    const setActionFeedback = vi.fn()
    vi.mocked(createSessionShareLink).mockResolvedValue({
      resource_type: 'session',
      resource_id: 'session-1',
      share_token: 'share-token-1',
      share_url: 'https://example.test/share/session-1',
    })

    const { result } = renderSessionActions({ setActionFeedback })

    await act(async () => {
      await result.current.handleShareSession()
    })

    expect(createSessionShareLink).toHaveBeenCalledWith('session-1')
    expect(writeText).toHaveBeenCalledWith('https://example.test/share/session-1')
    expect(result.current.sessionShareCopied).toBe(true)
    expect(setActionFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ tone: 'success' }),
    )
  })
})
