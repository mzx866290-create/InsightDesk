import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RESEARCH_SOURCE_STRATEGY_OPTIONS } from './composerResearchConfig'
import { ComposerToolbar } from './ComposerToolbar'

function renderToolbar(overrides: Partial<React.ComponentProps<typeof ComposerToolbar>> = {}) {
  const props: React.ComponentProps<typeof ComposerToolbar> = {
    researchMode: 'quick',
    researchSourceStrategy: 'web_only',
    researchSourceStrategyOptions: RESEARCH_SOURCE_STRATEGY_OPTIONS,
    omitHistoryForNextSend: false,
    webSearchEnabled: false,
    knowledgeBaseEnabled: false,
    composerBusy: false,
    composerLocked: false,
    canResearch: true,
    canSend: true,
    hasOnlyComposerDataFiles: false,
    effectiveComposerResearchMode: 'quick',
    researchButtonLabel: '研究',
    researchButtonTitle: '以快研模式发起联网研究',
    isResearchStarting: false,
    activeStopHandler: null,
    stopButtonTitle: '停止生成',
    onSelectResearchMode: vi.fn(),
    onSelectResearchSourceStrategy: vi.fn(),
    onToggleOmitHistory: vi.fn(),
    onToggleWebSearch: vi.fn(),
    onToggleKnowledgeBase: vi.fn(),
    onChooseAttachment: vi.fn(),
    onChooseImage: vi.fn(),
    onStartResearch: vi.fn(),
    onSend: vi.fn(),
    ...overrides,
  }

  return {
    props,
    ...render(<ComposerToolbar {...props} />),
  }
}

describe('ComposerToolbar', () => {
  afterEach(() => {
    cleanup()
  })

  it('routes toggle callbacks through buttons', () => {
    const onToggleOmitHistory = vi.fn()
    const onToggleWebSearch = vi.fn()
    const onToggleKnowledgeBase = vi.fn()
    const onStartResearch = vi.fn()

    renderToolbar({
      onToggleOmitHistory,
      onToggleWebSearch,
      onToggleKnowledgeBase,
      onStartResearch,
    })

    fireEvent.click(screen.getByTestId('composer-omit-history-toggle'))
    fireEvent.click(screen.getByTestId('composer-web-search-toggle'))
    fireEvent.click(screen.getByTestId('composer-knowledge-base-toggle'))
    fireEvent.click(screen.getByTestId('composer-research'))

    expect(onToggleOmitHistory).toHaveBeenCalledTimes(1)
    expect(onToggleWebSearch).toHaveBeenCalledTimes(1)
    expect(onToggleKnowledgeBase).toHaveBeenCalledTimes(1)
    expect(onStartResearch).toHaveBeenCalledTimes(1)
  })

  it('expands strategy panel and routes mode/source changes', () => {
    const onSelectResearchMode = vi.fn()
    const onSelectResearchSourceStrategy = vi.fn()

    renderToolbar({ onSelectResearchMode, onSelectResearchSourceStrategy })

    fireEvent.click(screen.getByTitle('研究策略设置'))

    fireEvent.click(screen.getByTestId('composer-research-mode-deep'))
    fireEvent.click(screen.getByTestId('composer-research-source-community_first'))

    expect(onSelectResearchMode).toHaveBeenCalledWith('deep')
    expect(onSelectResearchSourceStrategy).toHaveBeenCalledWith('community_first')
  })

  it('disables research action when unavailable', () => {
    renderToolbar({ canResearch: false })

    expect(screen.getByTestId('composer-research')).toBeDisabled()
  })
})
