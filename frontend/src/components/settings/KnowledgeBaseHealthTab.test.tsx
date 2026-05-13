import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getKBHealth } from '../../api/client'
import type { KBHealthData } from '../../api/client'
import { KnowledgeBaseHealthTab } from './KnowledgeBaseHealthTab'

vi.mock('../../api/client', () => ({
  getKBHealth: vi.fn(),
}))

const healthPayload: KBHealthData = {
  index_status: 'healthy',
  total_chunks: 12,
  store_path: 'F:/kb/faiss',
  store_size_mb: 3.4,
  documents: [{ name: 'intro.md', chunks: 4 }],
  embedding_model: 'bge-small',
  last_updated: 1_715_000_000,
}

describe('KnowledgeBaseHealthTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getKBHealth).mockResolvedValue(healthPayload)
  })

  afterEach(() => {
    cleanup()
  })

  it('renders health summary and toggles document list', async () => {
    render(<KnowledgeBaseHealthTab />)

    await screen.findByTestId('settings-kb-health-summary')

    expect(screen.getByTestId('settings-kb-health-status')).toHaveTextContent('健康')
    expect(screen.getByTestId('settings-kb-health-total-chunks')).toHaveTextContent('12')
    expect(screen.queryByTestId('settings-kb-documents-list')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('settings-kb-documents-toggle'))

    expect(screen.getByTestId('settings-kb-documents-list')).toBeInTheDocument()
    expect(screen.getByText('intro.md')).toBeInTheDocument()
  })

  it('shows an isolated load error and retries', async () => {
    vi.mocked(getKBHealth)
      .mockRejectedValueOnce(new Error('health failed'))
      .mockResolvedValueOnce(healthPayload)

    render(<KnowledgeBaseHealthTab />)

    expect(await screen.findByText('health failed')).toBeInTheDocument()

    fireEvent.click(screen.getByText('重试'))

    await waitFor(() => {
      expect(getKBHealth).toHaveBeenCalledTimes(2)
    })
    expect(await screen.findByTestId('settings-kb-health-summary')).toBeInTheDocument()
  })
})
