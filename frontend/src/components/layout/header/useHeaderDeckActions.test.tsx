import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getDeck } from '../../../api/client'
import type { DeckSpec, ModelConfig, TaskRecord } from '../../../api/client'
import { createAndTrackTask, useTaskStore } from '../../../stores/taskStore'
import { useHeaderDeckActions } from './useHeaderDeckActions'
import type { HeaderDeckGenerationPayload } from './useHeaderDeckActions'

vi.mock('../../../api/client', () => ({
  getDeck: vi.fn(),
}))

vi.mock('../../../stores/taskStore', () => ({
  createAndTrackTask: vi.fn(),
  useTaskStore: vi.fn(),
}))

const panelConfig: ModelConfig = {
  panel_id: 'panel-1',
  model: 'gpt-test',
  base_url: 'https://api.example.test/v1',
  api_key: 'sk-test',
  temperature: 0.7,
  agent_mode: 'plain_chat',
}

const deckPayload: HeaderDeckGenerationPayload = {
  panel_config: panelConfig,
  target_slide_count: 8,
  theme: 'midnight',
  template_id: 'template-1',
  template_options: { density: 'compact' },
}

function taskRecord(overrides: Partial<TaskRecord> = {}): TaskRecord {
  return {
    task_id: 'task-1',
    task_type: 'generate_deck',
    status: 'running',
    progress: 10,
    params: {},
    session_id: 'session-1',
    created_at: 1,
    ...overrides,
  }
}

function deckSpec(overrides: Partial<DeckSpec> = {}): DeckSpec {
  return {
    version: '1.0',
    deck_id: 'deck-1',
    status: 'ready',
    meta: {} as DeckSpec['meta'],
    generation: {} as DeckSpec['generation'],
    slides: [],
    source_registry: [],
    ...overrides,
  }
}

describe('useHeaderDeckActions', () => {
  let tasks: Record<string, TaskRecord>

  beforeEach(() => {
    tasks = {}
    vi.mocked(getDeck).mockReset()
    vi.mocked(createAndTrackTask).mockReset()
    vi.mocked(useTaskStore).mockImplementation((selector) =>
      selector({
        tasks,
        addTask: vi.fn(),
        addTasks: vi.fn(),
        updateTask: vi.fn(),
        startPolling: vi.fn(),
        stopPolling: vi.fn(),
        getTask: (taskId) => tasks[taskId],
        syncRecentTasks: vi.fn(),
        cancelTask: vi.fn(),
      }),
    )
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('opens deck generation config only when generation can start', () => {
    const { result } = renderHook(() =>
      useHeaderDeckActions({
        currentSessionId: 'session-1',
        knowledgeBaseEnabled: true,
        setActionFeedback: vi.fn(),
      }),
    )

    act(() => {
      result.current.handleGenerateReport()
    })

    expect(result.current.deckConfigOpen).toBe(true)
  })

  it('creates a tracked deck generation task with the selected payload', async () => {
    const setActionFeedback = vi.fn()
    vi.mocked(createAndTrackTask).mockResolvedValue(taskRecord())

    const { result } = renderHook(() =>
      useHeaderDeckActions({
        currentSessionId: 'session-1',
        knowledgeBaseEnabled: true,
        setActionFeedback,
      }),
    )

    await act(async () => {
      await result.current.handleGenerateDeck(deckPayload)
    })

    expect(createAndTrackTask).toHaveBeenCalledWith(
      'generate_deck',
      {
        panel_config: panelConfig,
        knowledge_base_enabled: true,
        target_slide_count: 8,
        theme: 'midnight',
        template_id: 'template-1',
        template_options: { density: 'compact' },
      },
      'session-1',
    )
    expect(result.current.deckTaskId).toBe('task-1')
    expect(setActionFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ tone: 'success' }),
    )
  })

  it('opens the generated deck when a tracked task completes', async () => {
    const setActionFeedback = vi.fn()
    const completedTask = taskRecord({
      status: 'completed',
      progress: 100,
      params: { deck_id: 'deck-1' },
    })
    const generatedDeck = deckSpec()
    vi.mocked(createAndTrackTask).mockResolvedValue(taskRecord())
    vi.mocked(getDeck).mockResolvedValue(generatedDeck)

    const { result, rerender } = renderHook(() =>
      useHeaderDeckActions({
        currentSessionId: 'session-1',
        knowledgeBaseEnabled: false,
        setActionFeedback,
      }),
    )

    await act(async () => {
      await result.current.handleGenerateDeck(deckPayload)
    })

    tasks = { 'task-1': completedTask }
    rerender()

    await waitFor(() => expect(getDeck).toHaveBeenCalledWith('deck-1'))
    await waitFor(() => expect(result.current.deckOpen).toBe(true))

    expect(result.current.deckData).toEqual(generatedDeck)
    expect(setActionFeedback).toHaveBeenLastCalledWith(null)
  })
})
