import React from 'react'

import { Button } from '../ui/Button'
import { KB_CHUNK_PAGE_SIZE, type ChunkPagination } from './kbMonitorModel'

export interface KbChunkPaginationProps {
  pagination: ChunkPagination
  offset: number
  total: number
  loading: boolean
  onPreviousPage: () => void
  onNextPage: () => void
}

export const KbChunkPagination: React.FC<KbChunkPaginationProps> = ({
  pagination,
  offset,
  total,
  loading,
  onPreviousPage,
  onNextPage,
}) => (
  <div className="mt-3 flex items-center justify-between text-xs text-text-secondary">
    <span>
      绗?{pagination.currentPage} / {pagination.totalPages} 椤碉紝鍏?{total} 鏉?    </span>
    <div className="flex items-center gap-2">
      <Button
        variant="ghost"
        onClick={onPreviousPage}
        disabled={offset <= 0 || loading}
        className="text-xs"
      >
        涓婁竴椤?      </Button>
      <Button
        variant="ghost"
        onClick={onNextPage}
        disabled={offset + KB_CHUNK_PAGE_SIZE >= total || loading}
        className="text-xs"
      >
        涓嬩竴椤?      </Button>
    </div>
  </div>
)
