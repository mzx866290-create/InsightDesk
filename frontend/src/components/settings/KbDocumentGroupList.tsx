import React from 'react'
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Loader2,
  Trash2,
  X,
} from 'lucide-react'

import type { DocGroup } from './knowledgeBaseModalModel'

interface KbDocumentGroupListProps {
  groups: DocGroup[]
  expandedSources: ReadonlySet<string>
  deletingChunk: string | null
  deletingSource: string | null
  isFiltering: boolean
  onToggleSource: (source: string) => void
  onRequestDeleteChunk: (chunkId: string, label: string) => void
  onRequestDeleteSource: (source: string) => void
}

export const KbDocumentGroupList: React.FC<KbDocumentGroupListProps> = ({
  groups,
  expandedSources,
  deletingChunk,
  deletingSource,
  isFiltering,
  onToggleSource,
  onRequestDeleteChunk,
  onRequestDeleteSource,
}) => {
  if (groups.length === 0) {
    return (
      <div className="text-center py-10 text-text-secondary text-sm">
        {isFiltering ? '未找到匹配的文档' : '知识库暂无文档，请上传文件'}
      </div>
    )
  }

  const totalChunks = groups.reduce((sum, group) => sum + group.chunks.length, 0)

  return (
    <div className="space-y-1.5">
      {/* 统计当前筛选后的文档和分块数量。 */}
      <p className="text-xs text-text-muted">
        共 {groups.length} 个文档，{totalChunks} 个分块
      </p>

      {groups.map(group => {
        const isExpanded = expandedSources.has(group.source)

        return (
          <div key={group.source} className="border border-bg-border rounded-lg overflow-hidden">
            <div
              className="flex items-center gap-2 px-3 py-2.5 bg-bg-tertiary hover:bg-bg-hover cursor-pointer select-none"
              onClick={() => onToggleSource(group.source)}
            >
              {isExpanded ? (
                <ChevronDown size={13} className="text-text-muted shrink-0" />
              ) : (
                <ChevronRight size={13} className="text-text-muted shrink-0" />
              )}
              <FileText size={13} className="text-accent-blue shrink-0" />
              <span className="flex-1 text-sm text-text-primary font-medium truncate">{group.source}</span>
              <span className="text-xs text-text-muted shrink-0">{group.chunks.length} 块</span>
              <button
                onClick={e => {
                  e.stopPropagation()
                  onRequestDeleteSource(group.source)
                }}
                disabled={deletingSource === group.source}
                className="ml-1 p-1 rounded text-text-muted hover:text-accent-red hover:bg-accent-red/10 transition-colors shrink-0"
                title="删除该文档的所有分块"
              >
                {deletingSource === group.source
                  ? <Loader2 size={12} className="animate-spin" />
                  : <Trash2 size={12} />
                }
              </button>
            </div>

            {isExpanded && (
              <div className="divide-y divide-bg-border">
                {group.chunks.map(chunk => (
                  <div key={chunk.chunk_id} className="flex items-start gap-2 px-3 py-2 hover:bg-bg-hover group">
                    <span className="text-[10px] text-text-muted mt-0.5 shrink-0 w-6 text-right">{chunk.position}</span>
                    <p className="flex-1 text-xs text-text-secondary line-clamp-2">{chunk.preview}</p>
                    <span className="text-[10px] text-text-muted shrink-0">{chunk.char_count}字</span>
                    <button
                      onClick={() => onRequestDeleteChunk(chunk.chunk_id, chunk.preview.slice(0, 30))}
                      disabled={deletingChunk === chunk.chunk_id}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded text-text-muted hover:text-accent-red hover:bg-accent-red/10 transition-all shrink-0"
                    >
                      {deletingChunk === chunk.chunk_id
                        ? <Loader2 size={11} className="animate-spin" />
                        : <X size={11} />
                      }
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
