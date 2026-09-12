import React from 'react'
import { RefreshCw, Search } from 'lucide-react'

import { useI18n } from '../../i18n'
import { Button } from '../ui/Button'

export interface KbChunkSearchBarProps {
  loading: boolean
  query: string
  sourceFilter: string
  sourceOptions: string[]
  onQueryChange: (value: string) => void
  onSourceFilterChange: (value: string) => void
  onSearch: () => void
  onRefresh: () => void
}

export const KbChunkSearchBar: React.FC<KbChunkSearchBarProps> = ({
  loading,
  query,
  sourceFilter,
  sourceOptions,
  onQueryChange,
  onSourceFilterChange,
  onSearch,
  onRefresh,
}) => {
  const { t } = useI18n()

  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-xs font-medium uppercase tracking-wide text-text-secondary">
          {t('settings.kbChunks.title')}
        </h4>
        <Button
          variant="ghost"
          onClick={onRefresh}
          loading={loading}
          className="min-h-11 gap-1.5 text-xs"
          data-testid="settings-kb-chunk-refresh"
        >
          <RefreshCw size={12} />
          {t('settings.kbChunks.refresh')}
        </Button>
      </div>

      <div className="mb-3 flex flex-col gap-2 sm:flex-row">
        <input
          data-testid="settings-kb-chunk-query"
          className="input-base min-h-11 flex-1 text-sm"
          placeholder={t('settings.kbChunks.searchPlaceholder')}
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && onSearch()}
        />
        <select
          data-testid="settings-kb-chunk-source-filter"
          className="input-base min-h-11 text-sm sm:w-52"
          value={sourceFilter}
          onChange={(event) => onSourceFilterChange(event.target.value)}
        >
          <option value="">{t('settings.kbChunks.allSources')}</option>
          {sourceOptions.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>
        <Button
          variant="primary"
          onClick={onSearch}
          loading={loading}
          className="min-h-11"
          data-testid="settings-kb-chunk-search"
        >
          <Search size={13} />
          {t('settings.kbChunks.search')}
        </Button>
      </div>
    </>
  )
}
