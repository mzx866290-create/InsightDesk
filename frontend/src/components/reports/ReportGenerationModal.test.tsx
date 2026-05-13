import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { getDeliveryTemplateCatalog } from '../../api/client'
import { ReportGenerationModal } from './ReportGenerationModal'

vi.mock('../../api/client', () => ({
  getDeliveryTemplateCatalog: vi.fn(),
}))

describe('ReportGenerationModal', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('submits selected report delivery template options', async () => {
    vi.mocked(getDeliveryTemplateCatalog).mockResolvedValue({
      templates: [
        {
          id: 'research_brief',
          name: 'Research Brief',
          description: 'Evidence-first research summary.',
          artifact_type: 'report',
          category: 'research',
          tags: ['research', 'evidence'],
          target_format: 'markdown',
          preview: 'Question → Evidence → Synthesis',
          suggested_options: {
            scope: 'answer_group',
            include_citations: true,
            conflict_review: true,
          },
          metadata: { source: 'builtin' },
        },
        {
          id: 'board_deck',
          name: 'Board Deck',
          description: 'Deck template should not appear in report picker.',
          artifact_type: 'deck',
          category: 'presentation',
          tags: ['deck'],
          target_format: 'pptx',
          preview: 'Cover → Insights',
          suggested_options: { target_slide_count: 8 },
          metadata: { source: 'builtin' },
        },
      ],
      summary: { total: 2, builtin: 2, manifest: 0, report: 1, deck: 1 },
      manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 0,
        issue_count: 0,
        issues: [],
      },
    })
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const onClose = vi.fn()

    render(
      <ReportGenerationModal
        open
        onClose={onClose}
        onSubmit={onSubmit}
      />,
    )

    fireEvent.click(await screen.findByText('Research Brief'))
    expect(screen.queryByText('Board Deck')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('report-generation-submit'))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        template_id: 'research_brief',
        template_options: {
          scope: 'answer_group',
          include_citations: true,
          conflict_review: true,
        },
      })
    })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
