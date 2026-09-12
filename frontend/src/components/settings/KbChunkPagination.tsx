import React from 'react'

import { useI18n } from '../../i18n'
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
}) => {
  const { t } = useI18n()
  const pageSummary = t('settings.kbChunks.pageSummary')
    .replace('{current}', String(pagination.currentPage))
    .replace('{pages}', String(pagination.totalPages))
    .replace('{total}', String(total))

  return (
    <div className="mt-3 flex flex-col gap-2 text-xs text-text-secondary sm:flex-row sm:items-center sm:justify-between">
      <span>{pageSummary}</span>
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          onClick={onPreviousPage}
          disabled={offset <= 0 || loading}
          className="min-h-11 flex-1 text-xs sm:flex-none"
        >
          {t('settings.kbChunks.previousPage')}
        </Button>
        <Button
          variant="ghost"
          onClick={onNextPage}
          disabled={offset + KB_CHUNK_PAGE_SIZE >= total || loading}
          className="min-h-11 flex-1 text-xs sm:flex-none"
        >
          {t('settings.kbChunks.nextPage')}
        </Button>
      </div>
    </div>
  )
}
