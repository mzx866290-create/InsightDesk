import React, { useState } from 'react'
import { FileText, Globe, ChevronDown, ChevronUp, Eye } from 'lucide-react'
import type { SourceItem } from '../../api/client'
import { DocumentPreviewModal } from './DocumentPreviewModal'

interface CitationPanelProps {
  sources: SourceItem[]
  streaming?: boolean
}

export const CitationPanel: React.FC<CitationPanelProps> = ({ sources, streaming }) => {
  const [previewSource, setPreviewSource] = useState<SourceItem | null>(null)
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  if (!sources || sources.length === 0) return null

  const docSources = sources.filter((s) => s.type === 'doc')
  const webSources = sources.filter((s) => s.type === 'web')

  return (
    <>
      <div className="mt-4 space-y-1.5">
        {/* Section label */}
        <div className="flex items-center gap-1.5 mb-2">
          <div className="h-px flex-1 bg-bg-border/60" />
          <span className="text-[10px] font-medium text-text-secondary/60 uppercase tracking-wider px-2">
            引用来源 {streaming && <span className="animate-pulse">•</span>}
          </span>
          <div className="h-px flex-1 bg-bg-border/60" />
        </div>

        {/* Doc citations */}
        {docSources.length > 0 && (
          <div className="space-y-1.5">
            {docSources.map((src, i) => {
              const globalIdx = sources.indexOf(src)
              const citationNum = src.index ?? globalIdx + 1
              const isExpanded = expandedIdx === globalIdx

              return (
                <div
                  key={`doc-${i}`}
                  className="group relative rounded-lg border border-bg-border bg-bg-secondary/40 hover:bg-bg-secondary/70 hover:border-accent-blue/30 transition-all duration-150"
                >
                  <div className="flex items-start gap-2.5 px-3 py-2.5">
                    {/* Citation number badge */}
                    <span className="shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-accent-blue/15 text-accent-blue text-[10px] font-bold mt-0.5">
                      {citationNum}
                    </span>

                    <FileText size={13} className="text-accent-blue/60 shrink-0 mt-0.5" />

                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-text-primary/90 text-xs truncate leading-tight">
                        {src.title}
                      </p>
                      {src.snippet && (
                        <p
                          className={`text-text-secondary/70 mt-1 leading-relaxed text-[11px] ${
                            isExpanded ? '' : 'line-clamp-2'
                          }`}
                        >
                          {src.snippet}
                        </p>
                      )}
                      {src.snippet && src.snippet.length > 120 && (
                        <button
                          onClick={() => setExpandedIdx(isExpanded ? null : globalIdx)}
                          className="mt-1 flex items-center gap-1 text-[10px] text-accent-blue/70 hover:text-accent-blue transition-colors"
                        >
                          {isExpanded ? (
                            <><ChevronUp size={10} /> 收起</>
                          ) : (
                            <><ChevronDown size={10} /> 展开</>
                          )}
                        </button>
                      )}
                    </div>

                    {/* Preview button */}
                    <button
                      onClick={() => setPreviewSource(src)}
                      className="shrink-0 p-1 rounded-md text-text-secondary/40 hover:text-accent-blue hover:bg-accent-blue/10 opacity-0 group-hover:opacity-100 transition-all"
                      title="预览文档片段"
                    >
                      <Eye size={12} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Web citations */}
        {webSources.length > 0 && (
          <div className="space-y-1.5">
            {webSources.map((src, i) => {
              const globalIdx = sources.indexOf(src)
              const citationNum = src.index ?? globalIdx + 1
              const isExpanded = expandedIdx === globalIdx

              return (
                <div
                  key={`web-${i}`}
                  className="group relative rounded-lg border border-bg-border bg-bg-secondary/40 hover:bg-bg-secondary/70 hover:border-accent-green/30 transition-all duration-150"
                >
                  <div className="flex items-start gap-2.5 px-3 py-2.5">
                    <span className="shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-accent-green/15 text-accent-green text-[10px] font-bold mt-0.5">
                      {citationNum}
                    </span>

                    <Globe size={13} className="text-accent-green/60 shrink-0 mt-0.5" />

                    <div className="min-w-0 flex-1">
                      {src.url ? (
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-xs text-accent-blue hover:underline underline-offset-2 truncate block leading-tight"
                        >
                          {src.title}
                        </a>
                      ) : (
                        <p className="font-medium text-text-primary/90 text-xs truncate leading-tight">
                          {src.title}
                        </p>
                      )}
                      {src.snippet && (
                        <p
                          className={`text-text-secondary/70 mt-1 leading-relaxed text-[11px] ${
                            isExpanded ? '' : 'line-clamp-2'
                          }`}
                        >
                          {src.snippet}
                        </p>
                      )}
                      {src.url && (
                        <p className="text-text-secondary/30 mt-0.5 truncate text-[10px]">{src.url}</p>
                      )}
                      {src.snippet && src.snippet.length > 120 && (
                        <button
                          onClick={() => setExpandedIdx(isExpanded ? null : globalIdx)}
                          className="mt-1 flex items-center gap-1 text-[10px] text-accent-green/70 hover:text-accent-green transition-colors"
                        >
                          {isExpanded ? (
                            <><ChevronUp size={10} /> 收起</>
                          ) : (
                            <><ChevronDown size={10} /> 展开</>
                          )}
                        </button>
                      )}
                    </div>

                    <button
                      onClick={() => setPreviewSource(src)}
                      className="shrink-0 p-1 rounded-md text-text-secondary/40 hover:text-accent-green hover:bg-accent-green/10 opacity-0 group-hover:opacity-100 transition-all"
                      title="预览来源"
                    >
                      <Eye size={12} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Document preview modal */}
      {previewSource && (
        <DocumentPreviewModal
          source={previewSource}
          onClose={() => setPreviewSource(null)}
        />
      )}
    </>
  )
}
