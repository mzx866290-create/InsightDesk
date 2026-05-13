import { afterEach, describe, expect, it, vi } from 'vitest'

import type { KnowledgeBaseChunk } from '../../api/client'
import { formatDate, formatSize, groupChunksBySource } from './knowledgeBaseModalModel'

const createChunk = (overrides: Partial<KnowledgeBaseChunk>): KnowledgeBaseChunk => ({
  chunk_id: 'chunk-1',
  position: 0,
  source: 'doc-a.md',
  content: 'content',
  preview: 'preview',
  char_count: 10,
  metadata: {},
  ...overrides,
})

describe('knowledgeBaseModalModel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('groups chunks by source while preserving first-seen source order and counts', () => {
    const groups = groupChunksBySource([
      createChunk({ chunk_id: 'a-1', source: 'doc-a.md', char_count: 10 }),
      createChunk({ chunk_id: 'b-1', source: 'doc-b.md', char_count: 7 }),
      createChunk({ chunk_id: 'a-2', source: 'doc-a.md', char_count: 5 }),
      createChunk({ chunk_id: 'unknown-1', source: '', char_count: 3 }),
    ])

    expect(groups).toHaveLength(3)
    expect(groups.map((group) => group.source)).toEqual(['doc-a.md', 'doc-b.md', '\u672a\u77e5\u6765\u6e90'])
    expect(groups.map((group) => group.chunks.map((chunk) => chunk.chunk_id))).toEqual([
      ['a-1', 'a-2'],
      ['b-1'],
      ['unknown-1'],
    ])
    expect(groups.map((group) => group.totalChars)).toEqual([15, 7, 3])
  })

  it('formats sizes in KB below 1 MB and MB otherwise', () => {
    expect(formatSize(0)).toBe('0 KB')
    expect(formatSize(0.5)).toBe('512 KB')
    expect(formatSize(1)).toBe('1.0 MB')
    expect(formatSize(12.345)).toBe('12.3 MB')
  })

  it('formats timestamps and falls back for missing dates', () => {
    const toLocaleStringSpy = vi
      .spyOn(Date.prototype, 'toLocaleString')
      .mockReturnValue('2026/05/07 08:09')

    expect(formatDate(null)).toBe('\u2014')
    expect(formatDate(0)).toBe('\u2014')
    expect(formatDate(1715040550)).toBe('2026/05/07 08:09')

    expect(toLocaleStringSpy).toHaveBeenCalledWith('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  })
})
