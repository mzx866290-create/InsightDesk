import { useMemo, useState } from 'react'
import type { Session } from '../../../api/client'
import type { SessionViewMode } from './sidebarConstants'
import {
  collectSessionTags,
  countSessionsByView,
  filterSessionsByView,
  getSessionEmptyStateMessage,
} from './sidebarModel'

interface UseSidebarSessionFiltersOptions {
  sessions: Session[]
}

export function useSidebarSessionFilters({
  sessions,
}: UseSidebarSessionFiltersOptions) {
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState<SessionViewMode>('all')
  const [tagFilter, setTagFilter] = useState<string | null>(null)

  const counts = useMemo(
    () => countSessionsByView(sessions),
    [sessions],
  )
  const allTags = useMemo(() => collectSessionTags(sessions), [sessions])
  const filteredSessions = useMemo(() => {
    return filterSessionsByView(sessions, viewMode, tagFilter)
  }, [sessions, viewMode, tagFilter])
  const emptyStateMessage = getSessionEmptyStateMessage(search, viewMode)

  return {
    search,
    viewMode,
    tagFilter,
    counts,
    allTags,
    filteredSessions,
    emptyStateMessage,
    setSearch,
    setViewMode,
    setTagFilter,
  }
}
