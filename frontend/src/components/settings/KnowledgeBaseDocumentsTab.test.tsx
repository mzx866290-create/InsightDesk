import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  deleteKnowledgeBaseChunk,
  getKnowledgeBaseChunks,
  type KnowledgeBaseChunk,
  type KnowledgeBaseChunksResponse,
} from '../../api/client'
import { KnowledgeBaseDocumentsTab } from './KnowledgeBaseDocumentsTab'

vi.mock('../../api/client', () => ({
  deleteKnowledgeBaseChunk: vi.fn(),
  getKnowledgeBaseChunks: vi.fn(),
}))

const chunk = (patch: Partial<KnowledgeBaseChunk>): KnowledgeBaseChunk => ({
  chunk_id: 'chunk-1',
  position: 1,
  source: 'intro.md',
  content: 'content',
  preview: 'preview',
  char_count: 7,
  metadata: {},
  ...patch,
})

const chunksResponse = (
  items: KnowledgeBaseChunk[],
  patch: Partial<KnowledgeBaseChunksResponse> = {},
): KnowledgeBaseChunksResponse => ({
  items,
  total: items.length,
  offset: 0,
  limit: 200,
  has_more: false,
  store_path: 'F:/kb/faiss',
  ...patch,
})

describe('KnowledgeBaseDocumentsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(deleteKnowledgeBaseChunk).mockResolvedValue(undefined)
    vi.mocked(getKnowledgeBaseChunks).mockImplementation(async (params) => {
      const offset = params?.offset ?? 0
      if (offset === 0) {
        return chunksResponse(
          [chunk({ chunk_id: 'intro-1', source: 'intro.md', preview: 'intro preview' })],
          { total: 2, offset: 0, has_more: true },
        )
      }
      return chunksResponse(
        [chunk({ chunk_id: 'guide-1', source: 'guide.md', preview: 'guide preview' })],
        { total: 2, offset, has_more: false },
      )
    })
  })

  afterEach(() => {
    cleanup()
  })

  it('loads every chunk page, filters by document name, and refreshes from the toolbar', async () => {
    render(<KnowledgeBaseDocumentsTab />)

    expect(await screen.findByText('intro.md')).toBeInTheDocument()
    expect(screen.getByText('guide.md')).toBeInTheDocument()
    expect(getKnowledgeBaseChunks).toHaveBeenNthCalledWith(1, { offset: 0, limit: 200 })
    expect(getKnowledgeBaseChunks).toHaveBeenNthCalledWith(2, { offset: 200, limit: 200 })

    fireEvent.change(screen.getByTestId('kb-documents-search-input'), {
      target: { value: 'guide' },
    })

    expect(screen.queryByText('intro.md')).not.toBeInTheDocument()
    expect(screen.getByText('guide.md')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('kb-documents-refresh-button'))

    await waitFor(() => {
      expect(getKnowledgeBaseChunks).toHaveBeenCalledTimes(4)
    })
  })

  it('confirms source deletion, deletes each chunk, and notifies the parent', async () => {
    const onDeleted = vi.fn()
    vi.mocked(getKnowledgeBaseChunks).mockResolvedValue(chunksResponse([
      chunk({ chunk_id: 'chunk-1', source: 'doc-a.md', preview: 'first preview' }),
      chunk({ chunk_id: 'chunk-2', source: 'doc-a.md', preview: 'second preview' }),
    ]))

    render(<KnowledgeBaseDocumentsTab onDeleted={onDeleted} />)

    const sourceHeader = (await screen.findByText('doc-a.md')).closest('div')
    expect(sourceHeader).not.toBeNull()

    fireEvent.click(within(sourceHeader as HTMLElement).getByRole('button'))
    expect(screen.getByTestId('kb-delete-confirm-dialog')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('kb-delete-confirm-submit'))

    await waitFor(() => {
      expect(deleteKnowledgeBaseChunk).toHaveBeenCalledWith('chunk-1')
      expect(deleteKnowledgeBaseChunk).toHaveBeenCalledWith('chunk-2')
    })
    expect(onDeleted).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('kb-delete-confirm-dialog')).not.toBeInTheDocument()
  })

  it('surfaces admin access load errors to the tab and parent handler', async () => {
    const onAdminAccessError = vi.fn()
    vi.mocked(getKnowledgeBaseChunks).mockRejectedValue(new Error('ADMIN_API_TOKEN missing'))

    render(<KnowledgeBaseDocumentsTab onAdminAccessError={onAdminAccessError} />)

    expect(await screen.findByText('ADMIN_API_TOKEN missing')).toBeInTheDocument()
    expect(onAdminAccessError).toHaveBeenCalledWith('ADMIN_API_TOKEN missing')
  })
})
