import React from 'react'
import { RefreshCw, Search } from 'lucide-react'

interface KnowledgeBaseDocumentsToolbarProps {
  searchQuery: string
  onSearchQueryChange: (query: string) => void
  onRefresh: () => void | Promise<void>
}

export const KnowledgeBaseDocumentsToolbar: React.FC<KnowledgeBaseDocumentsToolbarProps> = ({
  searchQuery,
  onSearchQueryChange,
  onRefresh,
}) => (
  <div className="flex gap-2">
    <div className="relative flex-1">
      <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
      <input
        data-testid="kb-documents-search-input"
        value={searchQuery}
        onChange={event => onSearchQueryChange(event.target.value)}
        placeholder="搜索文档名..."
        className="w-full pl-8 pr-3 py-1.5 text-sm bg-bg-tertiary border border-bg-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
      />
    </div>
    <button
      data-testid="kb-documents-refresh-button"
      onClick={() => {
        void onRefresh()
      }}
      className="px-3 py-1.5 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover border border-bg-border transition-colors flex items-center gap-1"
    >
      <RefreshCw size={11} />
      刷新
    </button>
  </div>
)
