import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Panel } from '../../stores/chatStore'
import { ChatPanelHeader } from './ChatPanelHeader'

vi.mock('./ModelSelector', () => ({
  ModelSelector: () => <div data-testid="mock-model-selector" />,
}))

const panel = {
  id: 'panel-1',
  messages: [{ id: 'message-1', role: 'user', content: 'Hello' }],
  modelConfig: { model: 'gpt-4o-mini' },
} as unknown as Panel

function renderHeader(overrides: Partial<React.ComponentProps<typeof ChatPanelHeader>> = {}) {
  return render(
    <ChatPanelHeader
      panel={panel}
      canRemove={false}
      isStreaming={false}
      loadingElapsedMs={0}
      isInteractionLocked={false}
      isStoppingSingleRunAvailable={false}
      activeStreamControl={null}
      msgCount={1}
      contextUsed={1}
      contextLimit={16}
      hasWorkflowActivity={false}
      workflowVisible={false}
      searchOpen={false}
      searchQuery=""
      matchedCount={0}
      onRemovePanel={vi.fn()}
      onToggleWorkflowVisible={vi.fn()}
      onToggleSearch={vi.fn()}
      onSearchQueryChange={vi.fn()}
      onExport={vi.fn()}
      {...overrides}
    />,
  )
}

describe('ChatPanelHeader', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('keeps panel-scoped actions and leaves session reset to the shared menu', () => {
    const onExport = vi.fn()
    renderHeader({ onExport })

    expect(screen.getByTestId('mock-model-selector')).toBeInTheDocument()
    expect(screen.queryByTitle('清除上下文')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTitle('导出当前面板（Markdown）'))
    expect(onExport).toHaveBeenCalledTimes(1)
  })
})
