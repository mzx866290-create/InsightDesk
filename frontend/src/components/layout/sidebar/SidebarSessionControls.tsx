import { Bookmark, Search, Tag } from 'lucide-react'
import type { SessionViewMode } from './sidebarConstants'
import type { SessionModeCounts } from './sidebarModel'

interface SidebarSessionControlsProps {
  search: string
  showBookmarks: boolean
  bookmarkSearch: string
  bookmarksCount: number
  counts: SessionModeCounts
  viewMode: SessionViewMode
  allTags: string[]
  tagFilter: string | null
  canDragSort: boolean
  filteredSessionCount: number
  error: string
  onSearchChange: (value: string) => void
  onToggleBookmarks: () => void
  onBookmarkSearchChange: (value: string) => void
  onViewModeChange: (mode: SessionViewMode) => void
  onTagFilterChange: (tag: string | null) => void
}

export function SidebarSessionControls({
  search,
  showBookmarks,
  bookmarkSearch,
  bookmarksCount,
  counts,
  viewMode,
  allTags,
  tagFilter,
  canDragSort,
  filteredSessionCount,
  error,
  onSearchChange,
  onToggleBookmarks,
  onBookmarkSearchChange,
  onViewModeChange,
  onTagFilterChange,
}: SidebarSessionControlsProps) {
  const isNotice = error.startsWith('演示模式')

  return (
    <div className="px-3 pb-3">
      <label className="flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
        <Search size={13} className="text-text-secondary" />
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索标题、标签或消息内容"
          className="w-full bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary"
        />
      </label>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onToggleBookmarks}
          className={`rounded-full px-2.5 py-1 text-[11px] transition-colors flex items-center gap-1 ${
            showBookmarks
              ? 'bg-amber-400/15 text-amber-400'
              : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
          }`}
        >
          <Bookmark size={10} />
          书签 {bookmarksCount > 0 ? bookmarksCount : ''}
        </button>
        {([
          ['all', `全部 ${counts.all}`],
          ['favorite', `收藏 ${counts.favorite}`],
          ['archived', `归档 ${counts.archived}`],
        ] as Array<[SessionViewMode, string]>).map(([value, label]) => {
          const active = viewMode === value
          return (
            <button
              key={value}
              type="button"
              onClick={() => onViewModeChange(value)}
              className={`rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                active
                  ? 'bg-accent-blue/15 text-accent-blue'
                  : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
              }`}
            >
              {label}
            </button>
          )
        })}
      </div>
      {showBookmarks && (
        <label className="mt-3 flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
          <Search size={13} className="text-text-secondary" />
          <input
            value={bookmarkSearch}
            onChange={(event) => onBookmarkSearchChange(event.target.value)}
            placeholder="Search bookmarks, sessions, or models"
            className="w-full bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary"
          />
        </label>
      )}
      {!showBookmarks && allTags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {allTags.map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => onTagFilterChange(tagFilter === tag ? null : tag)}
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] transition-colors ${
                tagFilter === tag
                  ? 'bg-accent-blue/20 text-accent-blue ring-1 ring-accent-blue/30'
                  : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
              }`}
            >
              <Tag size={8} />
              {tag}
            </button>
          ))}
        </div>
      )}
      {canDragSort && filteredSessionCount > 1 && (
        <p className="mt-2 text-[10px] text-text-secondary/65">
          提示：可拖拽会话调整顺序
        </p>
      )}

      {error && (
        <div
          data-testid="sidebar-session-error"
          className={`mt-3 rounded-xl border px-3 py-2 text-xs ${
            isNotice
              ? 'border-accent-blue/30 bg-accent-blue/10 text-accent-blue'
              : 'border-accent-red/30 bg-accent-red/10 text-accent-red'
          }`}
        >
          {error}
        </div>
      )}
    </div>
  )
}
