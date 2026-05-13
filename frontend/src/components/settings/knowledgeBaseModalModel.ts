import type { KnowledgeBaseChunk } from '../../api/client'

export type TabKey = 'documents' | 'upload' | 'retrieval' | 'health'

export interface DocGroup {
  source: string
  chunks: KnowledgeBaseChunk[]
  totalChars: number
}

export function groupChunksBySource(chunks: KnowledgeBaseChunk[]): DocGroup[] {
  const map = new Map<string, KnowledgeBaseChunk[]>()
  for (const chunk of chunks) {
    const key = chunk.source || '\u672a\u77e5\u6765\u6e90'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(chunk)
  }

  return Array.from(map.entries()).map(([source, items]) => ({
    source,
    chunks: items,
    totalChars: items.reduce((sum, chunk) => sum + chunk.char_count, 0),
  }))
}

export function formatSize(mb: number): string {
  if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`
  return `${mb.toFixed(1)} MB`
}

export function formatDate(ts: number | null): string {
  if (!ts) return '\u2014'
  return new Date(ts * 1000).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
