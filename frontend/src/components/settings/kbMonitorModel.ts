export const KB_CHUNK_PAGE_SIZE = 12
export const KB_CHUNK_DELETE_CONFIRM_TIMEOUT_MS = 4000
export const KB_DELETE_CONFIRM_TIMEOUT_MS = 4000
export const EMPTY_CHUNK_CONTENT_ERROR = '\u5207\u7247\u5185\u5bb9\u4e0d\u80fd\u4e3a\u7a7a'
export const EMPTY_CHUNK_SOURCE_ERROR = '\u6765\u6e90\u4e0d\u80fd\u4e3a\u7a7a'
export const KNOWLEDGE_BASE_DELETE_FAILED_PREFIX = '鍒犻櫎澶辫触锛?'

export type DeleteKnowledgeBaseResult = 'confirmation_requested' | 'deleted' | 'failed'
export type KbRetrievalModeValue = 'semantic' | 'keyword' | 'hybrid'

export interface ChunkLoadParams {
  offset?: number
  query?: string
  source?: string
}

export interface ChunkLoadRequest {
  offset: number
  query: string
  source: string
  limit: number
}

export interface ChunkSearchFilters {
  query: string
  source: string
}

export interface ChunkPagination {
  currentPage: number
  totalPages: number
  previousOffset: number
  nextOffset: number
}

export interface RetrievalTestSettings {
  mode: KbRetrievalModeValue
  searchK: number
  fetchK: number
  useRerank: boolean
}

export interface RetrievalTestOptions {
  retrieval_mode: KbRetrievalModeValue
  search_k: number
  fetch_k: number
  use_rerank: boolean
}

export function createChunkLoadRequest(
  params?: ChunkLoadParams,
  pageSize = KB_CHUNK_PAGE_SIZE,
): ChunkLoadRequest {
  return {
    query: params?.query ?? '',
    source: params?.source ?? '',
    offset: params?.offset ?? 0,
    limit: pageSize,
  }
}

export function getAppliedChunkLoadParams(
  offset: number,
  filters: ChunkSearchFilters,
): ChunkLoadParams {
  return {
    offset,
    query: filters.query,
    source: filters.source,
  }
}

export function getTrimmedChunkSearchFilters(query: string, source: string): ChunkSearchFilters {
  return {
    query: query.trim(),
    source: source.trim(),
  }
}

export function getChunkSaveValidationError(content: string, source: string): string | null {
  if (!content.trim()) return EMPTY_CHUNK_CONTENT_ERROR
  if (!source.trim()) return EMPTY_CHUNK_SOURCE_ERROR

  return null
}

export function shouldRequestChunkDeleteConfirmation(confirmingChunkId: string | null, chunkId: string): boolean {
  return confirmingChunkId !== chunkId
}

export function getKnowledgeBaseDeleteTargetPath(path?: string): string | null {
  return path ?? null
}

export function shouldRequestKnowledgeBaseDeleteConfirmation(
  confirming: boolean,
  confirmingPath: string | null,
  path?: string,
): boolean {
  return !confirming || confirmingPath !== getKnowledgeBaseDeleteTargetPath(path)
}

export function createRetrievalTestOptions(settings: RetrievalTestSettings): RetrievalTestOptions {
  return {
    retrieval_mode: settings.mode,
    search_k: settings.searchK,
    fetch_k: settings.fetchK,
    use_rerank: settings.useRerank,
  }
}

export function getChunkPagination(total: number, offset: number, pageSize = KB_CHUNK_PAGE_SIZE): ChunkPagination {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.min(totalPages, Math.floor(offset / pageSize) + 1)

  return {
    currentPage,
    totalPages,
    previousOffset: Math.max(0, offset - pageSize),
    nextOffset: offset + pageSize,
  }
}

export function getNextOffsetAfterChunkDelete(
  currentOffset: number,
  currentPageItemCount: number,
  pageSize = KB_CHUNK_PAGE_SIZE,
): number {
  if (currentPageItemCount === 1 && currentOffset > 0) {
    return Math.max(0, currentOffset - pageSize)
  }

  return currentOffset
}

export function formatCount(value: number): string {
  return value.toLocaleString()
}

export function formatUnixSecondsDate(timestamp?: number | null, locale = 'zh-CN'): string {
  if (!timestamp) return ''
  return new Date(timestamp * 1000).toLocaleString(locale)
}
