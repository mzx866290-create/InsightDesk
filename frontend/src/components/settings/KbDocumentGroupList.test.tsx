import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { KnowledgeBaseChunk } from '../../api/client'
import { KbDocumentGroupList } from './KbDocumentGroupList'
import type { DocGroup } from './knowledgeBaseModalModel'

const chunk = (patch: Partial<KnowledgeBaseChunk> = {}): KnowledgeBaseChunk => ({
  chunk_id: 'chunk-1',
  position: 0,
  source: 'doc-a.md',
  content: 'content',
  preview: 'chunk preview content',
  char_count: 21,
  metadata: {},
  ...patch,
})

const group = (patch: Partial<DocGroup> = {}): DocGroup => ({
  source: 'doc-a.md',
  chunks: [
    chunk({ chunk_id: 'chunk-1', position: 1, preview: 'first chunk preview', char_count: 18 }),
    chunk({ chunk_id: 'chunk-2', position: 2, preview: 'second chunk preview', char_count: 19 }),
  ],
  totalChars: 37,
  ...patch,
})

describe('KbDocumentGroupList', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders empty states for all documents and filtered results', () => {
    const props = {
      groups: [],
      expandedSources: new Set<string>(),
      deletingChunk: null,
      deletingSource: null,
      onToggleSource: vi.fn(),
      onRequestDeleteChunk: vi.fn(),
      onRequestDeleteSource: vi.fn(),
    }

    const { rerender } = render(<KbDocumentGroupList {...props} isFiltering={false} />)
    expect(screen.getByText('知识库暂无文档，请上传文件')).toBeInTheDocument()

    rerender(<KbDocumentGroupList {...props} isFiltering />)
    expect(screen.getByText('未找到匹配的文档')).toBeInTheDocument()
  })

  it('renders document statistics and forwards row/delete actions', () => {
    const onToggleSource = vi.fn()
    const onRequestDeleteSource = vi.fn()

    render(
      <KbDocumentGroupList
        groups={[group()]}
        expandedSources={new Set<string>()}
        deletingChunk={null}
        deletingSource={null}
        isFiltering={false}
        onToggleSource={onToggleSource}
        onRequestDeleteChunk={vi.fn()}
        onRequestDeleteSource={onRequestDeleteSource}
      />,
    )

    expect(screen.getByText('共 1 个文档，2 个分块')).toBeInTheDocument()
    expect(screen.getByText('doc-a.md')).toBeInTheDocument()
    expect(screen.getByText('2 块')).toBeInTheDocument()

    fireEvent.click(screen.getByText('doc-a.md'))
    expect(onToggleSource).toHaveBeenCalledWith('doc-a.md')

    const deleteSourceButton = screen.getByTitle('删除该文档的所有分块')
    fireEvent.click(deleteSourceButton)
    expect(onRequestDeleteSource).toHaveBeenCalledWith('doc-a.md')
    expect(onToggleSource).toHaveBeenCalledTimes(1)
  })

  it('renders expanded chunks and forwards trimmed chunk delete labels', () => {
    const onRequestDeleteChunk = vi.fn()
    const longPreview = 'abcdefghijklmnopqrstuvwxyz1234567890'

    render(
      <KbDocumentGroupList
        groups={[group({
          chunks: [chunk({ chunk_id: 'chunk-long', position: 3, preview: longPreview, char_count: 36 })],
          totalChars: 36,
        })]}
        expandedSources={new Set(['doc-a.md'])}
        deletingChunk={null}
        deletingSource={null}
        isFiltering={false}
        onToggleSource={vi.fn()}
        onRequestDeleteChunk={onRequestDeleteChunk}
        onRequestDeleteSource={vi.fn()}
      />,
    )

    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText(longPreview)).toBeInTheDocument()
    expect(screen.getByText('36字')).toBeInTheDocument()

    const chunkRow = screen.getByText(longPreview).closest('div')
    expect(chunkRow).not.toBeNull()
    fireEvent.click(within(chunkRow as HTMLElement).getByRole('button'))

    expect(onRequestDeleteChunk).toHaveBeenCalledWith('chunk-long', longPreview.slice(0, 30))
  })

  it('disables the matching delete controls while deleting', () => {
    render(
      <KbDocumentGroupList
        groups={[group()]}
        expandedSources={new Set(['doc-a.md'])}
        deletingChunk="chunk-1"
        deletingSource="doc-a.md"
        isFiltering={false}
        onToggleSource={vi.fn()}
        onRequestDeleteChunk={vi.fn()}
        onRequestDeleteSource={vi.fn()}
      />,
    )

    expect(screen.getByTitle('删除该文档的所有分块')).toBeDisabled()
    const firstChunkRow = screen.getByText('first chunk preview').closest('div')
    expect(firstChunkRow).not.toBeNull()
    expect(within(firstChunkRow as HTMLElement).getByRole('button')).toBeDisabled()
  })
})
