import React from 'react'
import { Loader2 } from 'lucide-react'
import { KbDocumentGroupList } from './KbDocumentGroupList'
import { KnowledgeBaseDeleteConfirmDialog } from './KnowledgeBaseDeleteConfirmDialog'
import { KnowledgeBaseDocumentsToolbar } from './KnowledgeBaseDocumentsToolbar'
import { useKnowledgeBaseDocumentsController } from './useKnowledgeBaseDocumentsController'

interface KnowledgeBaseDocumentsTabProps {
  onDeleted?: () => void
  onAdminAccessError?: (message: string | null) => void
}

export const KnowledgeBaseDocumentsTab: React.FC<KnowledgeBaseDocumentsTabProps> = ({
  onDeleted,
  onAdminAccessError,
}) => {
  const controller = useKnowledgeBaseDocumentsController({
    onDeleted,
    onAdminAccessError,
  })

  if (controller.loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={20} className="animate-spin text-accent-blue mr-2" />
        <span className="text-sm text-text-secondary">加载中...</span>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <KnowledgeBaseDocumentsToolbar
        searchQuery={controller.searchQuery}
        onSearchQueryChange={controller.setSearchQuery}
        onRefresh={controller.load}
      />

      {controller.error && (
        <div className="px-3 py-2 bg-accent-red/10 border border-accent-red/20 rounded-lg text-xs text-accent-red">{controller.error}</div>
      )}

      <KbDocumentGroupList
        groups={controller.filteredGroups}
        expandedSources={controller.expandedSources}
        deletingChunk={controller.deletingChunk}
        deletingSource={controller.deletingSource}
        isFiltering={controller.isFiltering}
        onToggleSource={controller.toggleSource}
        onRequestDeleteChunk={controller.requestDeleteChunk}
        onRequestDeleteSource={controller.requestDeleteSource}
      />

      {/* 删除确认对话框 */}
      <KnowledgeBaseDeleteConfirmDialog
        confirmDelete={controller.confirmDelete}
        deletingChunk={controller.deletingChunk}
        deletingSource={controller.deletingSource}
        onCancel={controller.cancelDelete}
        onConfirmChunk={controller.confirmDeleteChunk}
        onConfirmSource={controller.confirmDeleteSource}
      />
    </div>
  )
}
