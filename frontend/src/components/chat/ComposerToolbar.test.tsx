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

  it('routes mode and source strategy changes through callbacks', () => {
    const onSelectResearchMode = vi.fn()
    const onSelectResearchSourceStrategy = vi.fn()

    renderToolbar({ onSelectResearchMode, onSelectResearchSourceStrategy })

    fireEvent.click(screen.getByTestId('composer-research-mode-deep'))
    fireEvent.click(screen.getByTestId('composer-research-source-community_first'))

    expect(onSelectResearchMode).toHaveBeenCalledWith('deep')
    expect(onSelectResearchSourceStrategy).toHaveBeenCalledWith('community_first')
  })

  it('routes tool buttons and send actions through callbacks', () => {
    const onToggleOmitHistory = vi.fn()
    const onToggleWebSearch = vi.fn()
    const onToggleKnowledgeBase = vi.fn()
    const onChooseAttachment = vi.fn()
    const onChooseImage = vi.fn()
    const onStartResearch = vi.fn()
    const onSend = vi.fn()

    renderToolbar({
      onToggleOmitHistory,
      onToggleWebSearch,
      onToggleKnowledgeBase,
      onChooseAttachment,
      onChooseImage,
      onStartResearch,
      onSend,
    })

    fireEvent.click(screen.getByTestId('composer-omit-history-toggle'))
    fireEvent.click(screen.getByTestId('composer-web-search-toggle'))
    fireEvent.click(screen.getByTestId('composer-knowledge-base-toggle'))
    fireEvent.click(screen.getByTestId('composer-attachment-button'))
    fireEvent.click(screen.getByTitle('上传图片'))
    fireEvent.click(screen.getByTestId('composer-research'))
    fireEvent.click(screen.getByTestId('composer-send'))

    expect(onToggleOmitHistory).toHaveBeenCalledTimes(1)
    expect(onToggleWebSearch).toHaveBeenCalledTimes(1)
    expect(onToggleKnowledgeBase).toHaveBeenCalledTimes(1)
    expect(onChooseAttachment).toHaveBeenCalledTimes(1)
    expect(onChooseImage).toHaveBeenCalledTimes(1)
    expect(onStartResearch).toHaveBeenCalledTimes(1)
    expect(onSend).toHaveBeenCalledTimes(1)
  })

  it('shows a stop button instead of send while a stream can be stopped', () => {
    const activeStopHandler = vi.fn()

    renderToolbar({ activeStopHandler })

    fireEvent.click(screen.getByTitle('停止生成'))

    expect(activeStopHandler).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('composer-send')).not.toBeInTheDocument()
  })

  it('disables send and research actions when they are unavailable', () => {
    renderToolbar({ canSend: false, canResearch: false })

    expect(screen.getByTestId('composer-send')).toBeDisabled()
    expect(screen.getByTestId('composer-research')).toBeDisabled()
  })
})
