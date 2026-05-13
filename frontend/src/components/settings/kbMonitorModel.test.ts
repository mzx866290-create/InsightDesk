import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  EMPTY_CHUNK_CONTENT_ERROR,
  EMPTY_CHUNK_SOURCE_ERROR,
  createChunkLoadRequest,
  createRetrievalTestOptions,
  formatCount,
  formatUnixSecondsDate,
  getAppliedChunkLoadParams,
  getChunkPagination,
  getChunkSaveValidationError,
  getKnowledgeBaseDeleteTargetPath,
  getNextOffsetAfterChunkDelete,
  getTrimmedChunkSearchFilters,
  shouldRequestKnowledgeBaseDeleteConfirmation,
  shouldRequestChunkDeleteConfirmation,
} from './kbMonitorModel'

describe('kbMonitorModel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('calculates pagination with stable page bounds', () => {
    expect(getChunkPagination(0, 0)).toEqual({
      currentPage: 1,
      totalPages: 1,
      previousOffset: 0,
      nextOffset: 12,
    })

    expect(getChunkPagination(25, 12)).toEqual({
      currentPage: 2,
      totalPages: 3,
      previousOffset: 0,
      nextOffset: 24,
    })

    expect(getChunkPagination(25, 999, 10)).toEqual({
      currentPage: 3,
      totalPages: 3,
      previousOffset: 989,
      nextOffset: 1009,
    })
  })

  it('moves back one page only when deleting the last item on a non-first page', () => {
    expect(getNextOffsetAfterChunkDelete(24, 1)).toBe(12)
    expect(getNextOffsetAfterChunkDelete(12, 1)).toBe(0)
    expect(getNextOffsetAfterChunkDelete(12, 2)).toBe(12)
    expect(getNextOffsetAfterChunkDelete(0, 1)).toBe(0)
  })

  it('builds chunk load params and trims search filters', () => {
    expect(createChunkLoadRequest()).toEqual({
      query: '',
      source: '',
      offset: 0,
      limit: 12,
    })
    expect(createChunkLoadRequest({ query: 'term', source: 'doc.md', offset: 24 }, 25)).toEqual({
      query: 'term',
      source: 'doc.md',
      offset: 24,
      limit: 25,
    })
    expect(getAppliedChunkLoadParams(12, { query: 'term', source: 'doc.md' })).toEqual({
      offset: 12,
      query: 'term',
      source: 'doc.md',
    })
    expect(getTrimmedChunkSearchFilters('  term  ', '  doc.md  ')).toEqual({
      query: 'term',
      source: 'doc.md',
    })
  })

  it('validates chunk edits and delete confirmation state', () => {
    expect(getChunkSaveValidationError('   ', 'doc.md')).toBe(EMPTY_CHUNK_CONTENT_ERROR)
    expect(getChunkSaveValidationError('content', '   ')).toBe(EMPTY_CHUNK_SOURCE_ERROR)
    expect(getChunkSaveValidationError('content', 'doc.md')).toBeNull()
    expect(shouldRequestChunkDeleteConfirmation(null, 'chunk-1')).toBe(true)
    expect(shouldRequestChunkDeleteConfirmation('chunk-2', 'chunk-1')).toBe(true)
    expect(shouldRequestChunkDeleteConfirmation('chunk-1', 'chunk-1')).toBe(false)
  })

  it('normalizes knowledge base delete confirmation state', () => {
    expect(getKnowledgeBaseDeleteTargetPath()).toBeNull()
    expect(getKnowledgeBaseDeleteTargetPath('kb/docs')).toBe('kb/docs')
    expect(shouldRequestKnowledgeBaseDeleteConfirmation(false, null)).toBe(true)
    expect(shouldRequestKnowledgeBaseDeleteConfirmation(true, null)).toBe(false)
    expect(shouldRequestKnowledgeBaseDeleteConfirmation(true, 'kb/docs', 'kb/docs')).toBe(false)
    expect(shouldRequestKnowledgeBaseDeleteConfirmation(true, 'kb/docs', 'other/docs')).toBe(true)
  })

  it('maps retrieval test settings to API options', () => {
    expect(
      createRetrievalTestOptions({
        mode: 'hybrid',
        searchK: 8,
        fetchK: 20,
        useRerank: true,
      }),
    ).toEqual({
      retrieval_mode: 'hybrid',
      search_k: 8,
      fetch_k: 20,
      use_rerank: true,
    })
  })

  it('formats counts and timestamps for display', () => {
    const toLocaleStringSpy = vi
      .spyOn(Date.prototype, 'toLocaleString')
      .mockReturnValue('2026/05/07 08:09:10')

    expect(formatCount(1234567)).toBe('1,234,567')
    expect(formatUnixSecondsDate(1715040550, 'zh-CN')).toBe('2026/05/07 08:09:10')
    expect(formatUnixSecondsDate(undefined)).toBe('')
    expect(formatUnixSecondsDate(null)).toBe('')
    expect(formatUnixSecondsDate(0)).toBe('')

    expect(toLocaleStringSpy).toHaveBeenCalledWith('zh-CN')
  })
})
