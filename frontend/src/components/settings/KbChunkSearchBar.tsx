import React from 'react'
import { RefreshCw, Search } from 'lucide-react'

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
}) => (
  <>
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wide">
        鐭ヨ瘑搴撳垏鐗囨祻瑙堝櫒
      </h4>
      <Button
        variant="ghost"
        onClick={onRefresh}
        loading={loading}
        className="gap-1.5 text-xs"
        data-testid="settings-kb-chunk-refresh"
      >
        <RefreshCw size={12} />
        鍒锋柊鍒囩墖
      </Button>
    </div>

    <div className="mb-3 flex flex-col gap-2 sm:flex-row">
      <input
        data-testid="settings-kb-chunk-query"
        className="input-base flex-1 text-sm"
        placeholder="鎼滅储鍒囩墖鍐呭鎴栨潵婧?.."
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        onKeyDown={(event) => event.key === 'Enter' && onSearch()}
      />
      <select
        data-testid="settings-kb-chunk-source-filter"
        className="input-base text-sm sm:w-52"
        value={sourceFilter}
        onChange={(event) => onSourceFilterChange(event.target.value)}
      >
        <option value="">鍏ㄩ儴鏉ユ簮</option>
        {sourceOptions.map((source) => (
          <option key={source} value={source}>
            {source}
          </option>
        ))}
      </select>
      <Button variant="primary" onClick={onSearch} loading={loading} data-testid="settings-kb-chunk-search">
        <Search size={13} />
        鎼滅储
      </Button>
    </div>
  </>
)
