import { Plus, X } from 'lucide-react'
import type { Bookmark as StoredBookmark } from '../../../api/client'
import type { BookmarkGroup } from './sidebarModel'

interface BookmarkPanelProps {
  bookmarksCount: number
  groups: BookmarkGroup[]
  removingBookmarkId: string | null
  formatTime: (timestamp: number) => string
  onOpenBookmark: (bookmark: StoredBookmark) => void | Promise<void>
  onRemoveBookmark: (bookmarkId: string, source: 'remote' | 'local') => void | Promise<void>
  onSendToComposer: (content: string) => void
}

export function BookmarkPanel({
  bookmarksCount,
  groups,
  removingBookmarkId,
  formatTime,
  onOpenBookmark,
  onRemoveBookmark,
  onSendToComposer,
}: BookmarkPanelProps) {
  if (bookmarksCount === 0) {
    return <div className="py-6 text-center text-xs text-text-secondary">暂无书签消息</div>
  }

  if (groups.length === 0) {
    return (
      <div className="py-6 text-center text-xs text-text-secondary">
        没有找到匹配的书签。
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <section
          key={group.key}
          className="rounded-2xl border border-bg-border bg-bg-secondary/35 p-2"
        >
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <div className="min-w-0">
              <div className="truncate text-xs font-medium text-text-primary">
                {group.title}
              </div>
              <div className="mt-0.5 text-[10px] text-text-secondary/60">
                {group.items.length} 条书签
              </div>
            </div>
            <div className="shrink-0 text-[10px] text-text-secondary/55">
              {formatTime(group.updatedAt)}
            </div>
          </div>
          <div className="space-y-1.5">
            {group.items.map((bookmark) => (
              <div
                key={bookmark.id}
                role="button"
                tabIndex={0}
                onClick={() => {
                  void onOpenBookmark(bookmark)
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    void onOpenBookmark(bookmark)
                  }
                }}
                className="rounded-xl border border-bg-border bg-bg-tertiary/40 px-3 py-2.5 text-xs transition-colors hover:border-accent-blue/35 hover:bg-accent-blue/5"
              >
                <div className="mb-1.5 flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[10px] text-text-secondary/60">
                      {bookmark.modelId ? `${bookmark.modelId} · ` : ''}
                      {formatTime(bookmark.updatedAt || bookmark.createdAt)}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        onSendToComposer(bookmark.content)
                      }}
                      className="rounded p-0.5 text-text-secondary/50 transition-colors hover:text-accent-blue"
                      title="Send to composer"
                    >
                      <Plus size={10} />
                    </button>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        void onRemoveBookmark(bookmark.id, bookmark.source ?? 'remote')
                      }}
                      disabled={removingBookmarkId === bookmark.id}
                      className="rounded p-0.5 text-text-secondary/50 transition-colors hover:text-accent-red"
                      title="移除书签"
                    >
                      <X size={10} />
                    </button>
                  </div>
                </div>
                <p className="line-clamp-3 leading-relaxed text-text-secondary">
                  {bookmark.content}
                </p>
                <div className="mt-2 text-[10px] text-text-secondary/55">
                  点击可跳转到原消息
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
