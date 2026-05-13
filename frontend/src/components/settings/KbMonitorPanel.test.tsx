import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { KbMonitorPanel } from './KbMonitorPanel'
import type { KbMonitorController } from './useKbMonitor'

vi.mock('./KbHealthSummaryPanel', () => ({
  KbHealthSummaryPanel: () => <div data-testid="mock-kb-health-summary" />,
}))

vi.mock('./KbChunkBrowser', () => ({
  KbChunkBrowser: () => <div data-testid="mock-kb-chunk-browser" />,
}))

vi.mock('./KbRetrievalTestPanel', () => ({
  KbRetrievalTestPanel: () => <div data-testid="mock-kb-retrieval-test" />,
}))

vi.mock('./KbDangerZone', () => ({
  KbDangerZone: () => <div data-testid="mock-kb-danger-zone" />,
}))

function monitor(overrides: Partial<KbMonitorController> = {}): KbMonitorController {
  return {
    health: null,
    loadingHealth: false,
    actionError: null,
    chunkBrowserProps: {} as KbMonitorController['chunkBrowserProps'],
    retrievalTestProps: {} as KbMonitorController['retrievalTestProps'],
    dangerZoneProps: {} as KbMonitorController['dangerZoneProps'],
    deletingKnowledgeBase: false,
    isDeleteKnowledgeBaseConfirming: vi.fn(() => false),
    refreshHealth: vi.fn(async () => undefined),
    refreshCurrent: vi.fn(async () => undefined),
    deleteKnowledgeBase: vi.fn(async () => 'deleted' as const),
    ...overrides,
  }
}

describe('KbMonitorPanel', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('shows empty state when health reports an empty index', () => {
    render(
      <KbMonitorPanel
        monitor={monitor({
          health: {
            index_status: 'empty',
            total_chunks: 0,
            store_path: 'memory://kb',
            store_size_mb: 0,
            documents: [],
            embedding_model: 'test-embedding',
            last_updated: null,
          },
        })}
      />,
    )

    expect(screen.getByTestId('settings-kb-empty-state')).toBeInTheDocument()
    expect(screen.queryByTestId('mock-kb-health-summary')).not.toBeInTheDocument()
  })
})
