import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { getDeliveryTemplateCatalog } from '../../api/client'
import type { ModelConfig } from '../../api/client'
import { DeckGenerationModal } from './DeckGenerationModal'

vi.mock('../../api/client', () => ({
  getConnectionTypeLabel: vi.fn(() => 'OpenAI Compatible'),
  getDeliveryTemplateCatalog: vi.fn(),
}))

const panelConfig: ModelConfig = {
  panel_id: 'panel-1',
  connection_type: 'openai_compatible',
  model: 'gpt-4.1-mini',
  base_url: 'https://api.example.com/v1',
  api_key: '',
  temperature: 0.3,
  agent_mode: 'plain_chat',
}

describe('DeckGenerationModal', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('applies selected delivery template options to deck generation payload', async () => {
    vi.mocked(getDeliveryTemplateCatalog).mockResolvedValue({
      templates: [
        {
          id: 'executive_report',
          name: 'Executive Report',
          description: 'Report template should not appear in deck picker.',
          artifact_type: 'report',
          category: 'business',
          tags: ['report'],
          target_format: 'markdown',
          preview: 'Summary → Actions',
          suggested_options: { tone: 'executive' },
          metadata: { source: 'builtin' },
        },
        {
          id: 'board_deck',
          name: 'Board Deck',
          description: 'Board-ready presentation.',
          artifact_type: 'deck',
          category: 'presentation',
          tags: ['deck', 'pptx'],
          target_format: 'pptx',
          preview: 'Cover → Insights',
          suggested_options: {
            target_slide_count: 8,
            theme: 'midnight',
            knowledge_base_enabled: true,
          },
          metadata: { source: 'manifest' },
        },
      ],
      summary: { total: 2, builtin: 1, manifest: 1, report: 1, deck: 1 },
      manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 1,
        issue_count: 0,
        issues: [],
      },
    })
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const onClose = vi.fn()

    render(
      <DeckGenerationModal
        open
        panels={[{ id: 'panel-1', modelConfig: panelConfig }]}
        knowledgeBaseEnabled
        initialPanelId="panel-1"
        initialSlideCount={6}
        initialTheme="default"
        onClose={onClose}
        onSubmit={onSubmit}
      />,
    )

    fireEvent.click(await screen.findByText('Board Deck'))
    expect(screen.queryByText('Executive Report')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('deck-generation-submit'))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        panel_config: panelConfig,
        target_slide_count: 8,
        theme: 'midnight',
        template_id: 'board_deck',
        template_options: {
          target_slide_count: 8,
          theme: 'midnight',
          knowledge_base_enabled: true,
        },
      })
    })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
